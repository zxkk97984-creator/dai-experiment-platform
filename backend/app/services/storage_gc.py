"""Retention-aware, reference-safe storage garbage collection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StorageObject, StorageQuarantine
from app.services.storage_object_service import StorageObjectService
from app.services.storage_reconcile import (
    StorageFindingKind,
    _aware,
    business_references,
    legacy_references,
)
from app.storage import (
    StorageArea,
    StorageError,
    StorageObjectStatus,
    StorageQuarantineStatus,
    StorageService,
)


logger = logging.getLogger("storage_gc")


@dataclass(frozen=True)
class StorageCollectionResult:
    dry_run: bool
    eligible_count: int
    planned_count: int
    deleted_count: int
    resolved_count: int
    failed_count: int
    skipped_referenced_count: int
    records: tuple[dict[str, Any], ...] = field(default_factory=tuple)


_DELETE_KINDS = {
    StorageFindingKind.UNTRACKED_PHYSICAL.value,
    StorageFindingKind.UNREFERENCED_ACTIVE.value,
    StorageFindingKind.STALE_STAGING.value,
    StorageFindingKind.STALE_FAILED.value,
    StorageFindingKind.STALE_DELETING.value,
    StorageFindingKind.DELETED_PHYSICAL_PRESENT.value,
}


def _utc_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return _aware(current, datetime.now(timezone.utc))


class StorageGarbageCollector:
    """Collect only expired quarantine findings after a fresh ref check."""

    def __init__(
        self,
        db: Session,
        storage: StorageService,
        *,
        retry_delay: timedelta = timedelta(minutes=15),
        stale_staging_after: timedelta = timedelta(hours=1),
        stale_failed_after: timedelta = timedelta(days=1),
        stale_deleting_after: timedelta = timedelta(hours=1),
    ) -> None:
        if retry_delay <= timedelta(0):
            raise ValueError("retry_delay must be positive")
        self.db = db
        self.storage = storage
        self.retry_delay = retry_delay
        self.stale_staging_after = stale_staging_after
        self.stale_failed_after = stale_failed_after
        self.stale_deleting_after = stale_deleting_after

    def collect(
        self,
        *,
        now: datetime | None = None,
        dry_run: bool = True,
        limit: int | None = None,
    ) -> StorageCollectionResult:
        current_time = _utc_now(now)
        statement = (
            select(StorageQuarantine)
            .where(
                StorageQuarantine.status.in_(
                    [
                        StorageQuarantineStatus.QUARANTINED.value,
                        StorageQuarantineStatus.FAILED.value,
                    ]
                ),
                StorageQuarantine.quarantine_until <= current_time,
            )
            .order_by(StorageQuarantine.id)
        )
        if limit is not None:
            if limit <= 0:
                raise ValueError("limit must be positive")
            statement = statement.limit(limit)
        rows = self.db.scalars(statement).all()
        references = business_references(self.db)
        legacy = legacy_references(self.db)
        records: list[dict[str, Any]] = []
        planned = deleted = resolved = failed = skipped_referenced = 0

        for quarantine in rows:
            if quarantine.kind not in _DELETE_KINDS:
                continue
            planned += 1
            area = self._area(quarantine.area)
            if area is None or quarantine.backend != self.storage.backend_name:
                records.append(
                    {
                        "id": quarantine.id,
                        "action": "skip_backend_or_area",
                        "object_key": quarantine.object_key,
                    }
                )
                continue

            obj = self.db.get(StorageObject, quarantine.object_id) if quarantine.object_id else None
            if obj is None:
                obj = self.db.scalar(
                    select(StorageObject).where(
                        StorageObject.backend == quarantine.backend,
                        StorageObject.object_key == quarantine.object_key,
                    )
                )

            object_refs: tuple[str, ...] = ()
            if obj is not None:
                related_objects = self.db.scalars(
                    select(StorageObject).where(
                        StorageObject.backend == quarantine.backend,
                        StorageObject.object_key == quarantine.object_key,
                    )
                ).all()
                object_refs = tuple(
                    sorted(
                        {
                            reference
                            for related in related_objects
                            for reference in references.get(related.id, ())
                        }
                    )
                )
            legacy_refs = legacy.get((area.value, quarantine.object_key), ())
            if area == StorageArea.STUDIO:
                legacy_refs = tuple(
                    sorted(
                        set(legacy_refs)
                        | {
                            label
                            for (legacy_area, prefix), labels in legacy.items()
                            if legacy_area == area.value
                            and prefix.endswith("/")
                            and quarantine.object_key.startswith(prefix)
                            for label in labels
                        }
                    )
                )
            all_refs = tuple(sorted(set(object_refs) | set(legacy_refs)))
            if all_refs:
                skipped_referenced += 1
                records.append(
                    {
                        "id": quarantine.id,
                        "action": "skip_referenced",
                        "object_key": quarantine.object_key,
                        "references": all_refs,
                    }
                )
                if not dry_run:
                    self._record_retry(
                        quarantine,
                        current_time,
                        "business reference appeared during collection",
                    )
                continue

            if dry_run:
                records.append(
                    {
                        "id": quarantine.id,
                        "action": "would_delete",
                        "object_key": quarantine.object_key,
                    }
                )
                continue

            try:
                if obj is not None:
                    self._prepare_metadata_for_delete(obj, quarantine.kind)
                    self.db.commit()

                self.storage.delete(area, quarantine.object_key)

                if obj is not None and obj.status in {
                    StorageObjectStatus.DELETING.value,
                    StorageObjectStatus.ACTIVE.value,
                }:
                    StorageObjectService(self.db, self.storage).mark_deleted(obj.id)
                if obj is not None and obj.status == StorageObjectStatus.STAGING.value:
                    StorageObjectService(self.db, self.storage).mark_failed(obj.id)
                self.db.commit()
                self._resolve(quarantine, current_time)
                self.db.commit()
                deleted += 1
                resolved += 1
                records.append(
                    {
                        "id": quarantine.id,
                        "action": "deleted",
                        "object_key": quarantine.object_key,
                    }
                )
            except Exception as exc:  # physical providers can fail transiently
                self.db.rollback()
                current = self.db.get(StorageQuarantine, quarantine.id)
                if current is not None:
                    self._record_retry(current, current_time, str(exc)[:500])
                    self.db.commit()
                failed += 1
                records.append(
                    {
                        "id": quarantine.id,
                        "action": "retry",
                        "object_key": quarantine.object_key,
                        "error": type(exc).__name__,
                    }
                )

        if not dry_run:
            self.db.commit()
        return StorageCollectionResult(
            dry_run=dry_run,
            eligible_count=len(rows),
            planned_count=planned,
            deleted_count=deleted,
            resolved_count=resolved,
            failed_count=failed,
            skipped_referenced_count=skipped_referenced,
            records=tuple(records),
        )

    @staticmethod
    def _area(value: str) -> StorageArea | None:
        try:
            return StorageArea(value)
        except ValueError:
            return None

    def _prepare_metadata_for_delete(self, obj: StorageObject, kind: str) -> None:
        service = StorageObjectService(self.db, self.storage)
        if obj.status == StorageObjectStatus.ACTIVE.value and kind in {
            StorageFindingKind.UNREFERENCED_ACTIVE.value,
            StorageFindingKind.UNTRACKED_PHYSICAL.value,
            StorageFindingKind.SIZE_MISMATCH.value,
            StorageFindingKind.SHA256_MISMATCH.value,
        }:
            service.mark_deleting(obj.id)
        elif obj.status == StorageObjectStatus.STAGING.value:
            service.mark_failed(obj.id)

    def _resolve(self, quarantine: StorageQuarantine, now: datetime) -> None:
        quarantine.status = StorageQuarantineStatus.RESOLVED.value
        quarantine.resolved_at = now
        quarantine.last_error = None

    def _record_retry(
        self,
        quarantine: StorageQuarantine,
        now: datetime,
        error: str,
    ) -> None:
        quarantine.status = StorageQuarantineStatus.FAILED.value
        quarantine.attempts += 1
        quarantine.last_error = error
        quarantine.quarantine_until = now + self.retry_delay
        quarantine.resolved_at = None
