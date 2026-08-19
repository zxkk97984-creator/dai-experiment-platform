"""Storage Phase 5 reconcile and garbage-collection contracts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from io import BytesIO

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import func, select

from app.models import Course, StorageObject, StorageQuarantine
from app.services.storage_gc import StorageGarbageCollector
from app.services.storage_reconcile import (
    StorageFindingKind,
    StorageReconcileService,
)
from app.storage import (
    LocalFilesystemStorage,
    S3CompatibleStorage,
    StorageArea,
    StorageError,
    StorageObjectBackend,
    StorageObjectStatus,
    StorageService,
)


@pytest.fixture(params=["local", "s3"], ids=["local", "s3"])
def reconcile_context(request, tmp_path):
    if request.param == "local":
        backend = LocalFilesystemStorage(tmp_path / "storage")
        yield StorageService(
            {
                StorageArea.COVERS: backend,
                StorageArea.VIDEOS: backend,
                StorageArea.STUDIO: backend,
            },
            backend_name="local",
        )
        return

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="reconcile-bucket")
        backend = S3CompatibleStorage(client, bucket="reconcile-bucket")
        yield StorageService(
            {
                StorageArea.COVERS: backend,
                StorageArea.VIDEOS: backend,
                StorageArea.STUDIO: backend,
            },
            backend_name="s3",
        )


def _old(value: datetime) -> datetime:
    return value - timedelta(days=2)


def _create_object(
    db,
    storage: StorageService,
    *,
    area: StorageArea,
    key: str,
    payload: bytes,
    status: str = StorageObjectStatus.ACTIVE.value,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
    updated_at: datetime | None = None,
) -> StorageObject:
    storage.put(area, key, BytesIO(payload))
    obj = StorageObject(
        namespace={
            StorageArea.COVERS: "course-covers",
            StorageArea.VIDEOS: "lesson-videos",
            StorageArea.STUDIO: "studio-assets",
        }[area],
        object_key=key,
        backend=storage.backend_name,
        status=status,
        size_bytes=len(payload) if expected_size is None else expected_size,
        sha256=(hashlib.sha256(payload).hexdigest() if expected_sha256 is None else expected_sha256),
        metadata_json={"storage_area": area.value},
        deleted_at=(updated_at or datetime.now(timezone.utc)) if status == "deleted" else None,
    )
    db.add(obj)
    db.commit()
    if updated_at is not None:
        obj.updated_at = updated_at
        db.commit()
    db.refresh(obj)
    return obj


def _quarantine_until(db, now: datetime) -> None:
    for row in db.scalars(select(StorageQuarantine)).all():
        row.quarantine_until = now - timedelta(seconds=1)
    db.commit()


def test_dry_run_identifies_stale_staging_and_untracked_without_writes(
    db_session_factory, reconcile_context
):
    now = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
    with db_session_factory() as db:
        staging = _create_object(
            db,
            reconcile_context,
            area=StorageArea.COVERS,
            key="covers/1/stale.png",
            payload=b"stale",
            status=StorageObjectStatus.STAGING.value,
            updated_at=_old(now),
        )
        reconcile_context.put(
            StorageArea.COVERS, "covers/2/untracked.png", BytesIO(b"orphan")
        )

        report = StorageReconcileService(
            db,
            reconcile_context,
            stale_staging_after=timedelta(hours=1),
            quarantine_retention=timedelta(days=1),
        ).scan(now=now, dry_run=True)

        kinds = {finding.kind for finding in report.findings}
        assert StorageFindingKind.STALE_STAGING.value in kinds
        assert StorageFindingKind.UNTRACKED_PHYSICAL.value in kinds
        assert db.scalar(select(func.count(StorageQuarantine.id))) == 0
        assert db.get(StorageObject, staging.id).status == StorageObjectStatus.STAGING.value
        assert reconcile_context.exists(StorageArea.COVERS, "covers/2/untracked.png")


def test_quarantine_gc_is_retained_then_removes_stale_and_untracked_objects(
    db_session_factory, reconcile_context
):
    now = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
    with db_session_factory() as db:
        staging = _create_object(
            db,
            reconcile_context,
            area=StorageArea.VIDEOS,
            key="lessons/1/stale.mp4",
            payload=b"stale",
            status=StorageObjectStatus.STAGING.value,
            updated_at=_old(now),
        )
        reconcile_context.put(
            StorageArea.VIDEOS, "lessons/2/untracked.mp4", BytesIO(b"orphan")
        )
        reconciler = StorageReconcileService(
            db,
            reconcile_context,
            stale_staging_after=timedelta(hours=1),
            quarantine_retention=timedelta(days=1),
        )
        reconciler.scan(now=now, dry_run=False)
        assert db.scalar(select(func.count(StorageQuarantine.id))) == 2

        dry_result = StorageGarbageCollector(db, reconcile_context).collect(
            now=now, dry_run=True
        )
        assert dry_result.deleted_count == 0
        assert reconcile_context.exists(StorageArea.VIDEOS, "lessons/2/untracked.mp4")
        assert db.get(StorageObject, staging.id).status == StorageObjectStatus.STAGING.value

        _quarantine_until(db, now)
        result = StorageGarbageCollector(db, reconcile_context).collect(
            now=now, dry_run=False
        )
        assert result.deleted_count == 2
        assert not reconcile_context.exists(StorageArea.VIDEOS, "lessons/1/stale.mp4")
        assert not reconcile_context.exists(StorageArea.VIDEOS, "lessons/2/untracked.mp4")
        assert db.get(StorageObject, staging.id).status == StorageObjectStatus.FAILED.value

        repeat = StorageGarbageCollector(db, reconcile_context).collect(
            now=now + timedelta(minutes=1), dry_run=False
        )
        assert repeat.deleted_count == 0


def test_reconcile_is_idempotent_when_same_finding_is_seen_again(
    db_session_factory, reconcile_context
):
    now = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
    with db_session_factory() as db:
        reconcile_context.put(
            StorageArea.COVERS, "covers/8/repeated.png", BytesIO(b"orphan")
        )
        reconciler = StorageReconcileService(db, reconcile_context)
        first = reconciler.scan(now=now, dry_run=False)
        second = reconciler.scan(now=now + timedelta(minutes=1), dry_run=False)

        assert first.quarantined_count == 1
        assert second.quarantined_count == 1
        assert db.scalar(select(func.count(StorageQuarantine.id))) == 1
        quarantine = db.scalar(select(StorageQuarantine))
        assert quarantine.attempts == 0
        assert quarantine.status == "quarantined"


def test_active_object_referenced_after_scan_is_never_deleted(
    db_session_factory, reconcile_context
):
    now = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
    with db_session_factory() as db:
        obj = _create_object(
            db,
            reconcile_context,
            area=StorageArea.COVERS,
            key="covers/3/referenced.png",
            payload=b"cover",
            updated_at=_old(now),
        )
        reconciler = StorageReconcileService(
            db,
            reconcile_context,
            quarantine_retention=timedelta(days=1),
        )
        reconciler.scan(now=now, dry_run=False)
        _quarantine_until(db, now)

        course = Course(title="referenced", status="draft", visibility="class", default_score=100)
        course.cover = obj.object_key
        course.cover_object_id = obj.id
        db.add(course)
        db.commit()

        result = StorageGarbageCollector(db, reconcile_context).collect(
            now=now, dry_run=False
        )
        assert result.skipped_referenced_count >= 1
        assert reconcile_context.exists(StorageArea.COVERS, obj.object_key)
        assert db.get(StorageObject, obj.id).status == StorageObjectStatus.ACTIVE.value


def test_legacy_cover_key_is_protected_from_untracked_gc(
    db_session_factory, reconcile_context
):
    now = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
    with db_session_factory() as db:
        key = "covers/legacy/cover.png"
        reconcile_context.put(StorageArea.COVERS, key, BytesIO(b"legacy"))
        db.add(
            Course(
                title="legacy cover",
                status="draft",
                visibility="class",
                default_score=100,
                cover=key,
            )
        )
        db.commit()

        report = StorageReconcileService(db, reconcile_context).scan(
            now=now, dry_run=False
        )
        assert not any(
            finding.kind == StorageFindingKind.UNTRACKED_PHYSICAL.value
            for finding in report.findings
        )
        assert db.scalar(select(func.count(StorageQuarantine.id))) == 0
        assert reconcile_context.exists(StorageArea.COVERS, key)


def test_reconcile_reports_missing_deleted_size_and_sha_mismatch(
    db_session_factory, reconcile_context
):
    now = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
    with db_session_factory() as db:
        missing = StorageObject(
            namespace="course-covers",
            object_key="covers/4/missing.png",
            backend=reconcile_context.backend_name,
            status=StorageObjectStatus.ACTIVE.value,
            size_bytes=2,
            sha256=hashlib.sha256(b"xx").hexdigest(),
            metadata_json={"storage_area": "covers"},
        )
        db.add(missing)
        _create_object(
            db,
            reconcile_context,
            area=StorageArea.COVERS,
            key="covers/4/wrong-size.png",
            payload=b"actual",
            expected_size=2,
            expected_sha256=hashlib.sha256(b"actual").hexdigest(),
        )
        _create_object(
            db,
            reconcile_context,
            area=StorageArea.COVERS,
            key="covers/4/wrong-sha.png",
            payload=b"actual",
            expected_sha256=hashlib.sha256(b"other").hexdigest(),
        )
        _create_object(
            db,
            reconcile_context,
            area=StorageArea.COVERS,
            key="covers/4/deleted.png",
            payload=b"deleted",
            status=StorageObjectStatus.DELETED.value,
            updated_at=now,
        )
        db.commit()

        report = StorageReconcileService(db, reconcile_context).scan(
            now=now, dry_run=True, verify_sha256=True
        )
        findings = {(finding.kind, finding.object_key) for finding in report.findings}
        assert (StorageFindingKind.MISSING_PHYSICAL.value, missing.object_key) in findings
        assert (
            StorageFindingKind.SIZE_MISMATCH.value,
            "covers/4/wrong-size.png",
        ) in findings
        assert (
            StorageFindingKind.SHA256_MISMATCH.value,
            "covers/4/wrong-sha.png",
        ) in findings
        assert (
            StorageFindingKind.DELETED_PHYSICAL_PRESENT.value,
            "covers/4/deleted.png",
        ) in findings


def test_failed_physical_delete_is_retryable(
    db_session_factory, reconcile_context, monkeypatch
):
    now = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
    with db_session_factory() as db:
        reconcile_context.put(
            StorageArea.STUDIO, "templates/9/retry/orphan.py", BytesIO(b"orphan")
        )
        reconciler = StorageReconcileService(
            db,
            reconcile_context,
            quarantine_retention=timedelta(days=1),
        )
        reconciler.scan(now=now, dry_run=False)
        _quarantine_until(db, now)

        original_delete = reconcile_context.delete
        calls = {"count": 0}

        def flaky_delete(area, key):
            calls["count"] += 1
            if calls["count"] == 1:
                raise StorageError("transient delete failure")
            return original_delete(area, key)

        monkeypatch.setattr(reconcile_context, "delete", flaky_delete)
        first = StorageGarbageCollector(
            db, reconcile_context, retry_delay=timedelta(seconds=1)
        ).collect(now=now, dry_run=False)
        assert first.failed_count == 1
        quarantine = db.scalar(select(StorageQuarantine))
        assert quarantine.status == "failed"
        assert quarantine.attempts == 1
        assert reconcile_context.exists(StorageArea.STUDIO, "templates/9/retry/orphan.py")

        quarantine.quarantine_until = now - timedelta(seconds=1)
        db.commit()
        second = StorageGarbageCollector(db, reconcile_context).collect(
            now=now + timedelta(seconds=2), dry_run=False
        )
        assert second.deleted_count == 1
        assert not reconcile_context.exists(
            StorageArea.STUDIO, "templates/9/retry/orphan.py"
        )
