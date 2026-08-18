"""StorageObject metadata lifecycle and single-object integrity checks.

This service only manages database metadata and observes an already configured
StorageService.  It deliberately does not try to make a database transaction
and a filesystem/object-store write atomic.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import StorageObject
from app.storage import (
    StorageArea,
    StorageObjectBackend,
    StorageObjectStatus,
    StorageNotFound,
    StorageService,
)


class StorageObjectError(Exception):
    """Base class for metadata service errors."""


class StorageObjectNotFound(StorageObjectError):
    """The metadata row does not exist."""


class StorageObjectConflict(StorageObjectError):
    """The logical namespace/key already has a metadata row."""


class StorageObjectStateError(StorageObjectError):
    """A lifecycle operation is not valid for the current state."""


class StorageObjectValidationError(StorageObjectError):
    """Metadata input is not a valid logical object description."""


class StorageIntegrityStatus(StrEnum):
    OK = "ok"
    MISSING = "missing"
    SIZE_MISMATCH = "size_mismatch"
    SHA256_MISMATCH = "sha256_mismatch"
    DELETED_PHYSICAL_PRESENT = "deleted_physical_present"


@dataclass(frozen=True)
class StorageIntegrityReport:
    object_id: int
    status: str
    is_consistent: bool
    physical_exists: bool
    expected_size: int | None
    actual_size: int | None
    expected_sha256: str | None
    actual_sha256: str | None


_ALLOWED_BACKENDS = {
    StorageObjectBackend.LOCAL.value,
    StorageObjectBackend.S3.value,
}
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_ALLOWED_TRANSITIONS = {
    StorageObjectStatus.STAGING.value: {
        StorageObjectStatus.ACTIVE.value,
        StorageObjectStatus.FAILED.value,
    },
    StorageObjectStatus.ACTIVE.value: {StorageObjectStatus.DELETING.value},
    StorageObjectStatus.DELETING.value: {
        StorageObjectStatus.DELETED.value,
        StorageObjectStatus.FAILED.value,
    },
    StorageObjectStatus.FAILED.value: set(),
    StorageObjectStatus.DELETED.value: set(),
}


def _validate_namespace(namespace: str) -> str:
    if not isinstance(namespace, str) or not namespace or namespace.strip() != namespace:
        raise StorageObjectValidationError("namespace must be a non-empty trimmed string")
    if len(namespace) > 64 or namespace in {".", ".."} or any(
        char in namespace for char in ("/", "\\", "\x00")
    ):
        raise StorageObjectValidationError("namespace is not a valid logical namespace")
    return namespace


def _validate_object_key(object_key: str) -> str:
    if not isinstance(object_key, str) or not object_key or object_key.strip() != object_key:
        raise StorageObjectValidationError("object_key must be a non-empty trimmed string")
    if "\x00" in object_key or "\\" in object_key:
        raise StorageObjectValidationError("object_key must use safe logical path separators")
    if object_key in {".", "./"} or object_key.startswith("/") or object_key.endswith("/"):
        raise StorageObjectValidationError("object_key must identify a single object")
    if len(object_key) >= 2 and object_key[1] == ":" and object_key[0].isalpha():
        raise StorageObjectValidationError("absolute drive paths are not valid object keys")
    parts = object_key.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise StorageObjectValidationError("object_key contains an unsafe path segment")
    if len(object_key) > 500:
        raise StorageObjectValidationError("object_key is too long")
    return object_key


def _validate_backend(backend: str | StorageObjectBackend) -> str:
    value = backend.value if isinstance(backend, StorageObjectBackend) else backend
    if not isinstance(value, str) or value not in _ALLOWED_BACKENDS:
        raise StorageObjectValidationError("unsupported storage object backend")
    return value


def _validate_size(size_bytes: int | None) -> int | None:
    if size_bytes is None:
        return None
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        raise StorageObjectValidationError("size_bytes must be a non-negative integer")
    return size_bytes


def _validate_sha256(sha256: str | None) -> str | None:
    if sha256 is None:
        return None
    if not isinstance(sha256, str) or _SHA256_RE.fullmatch(sha256) is None:
        raise StorageObjectValidationError("sha256 must be a 64-character hexadecimal digest")
    return sha256.lower()


class StorageObjectService:
    """Metadata service with caller-owned SQLAlchemy transaction boundaries."""

    def __init__(self, db: Session, storage: StorageService | None = None) -> None:
        self.db = db
        self.storage = storage

    def get(self, object_id: int) -> StorageObject:
        obj = self.db.get(StorageObject, object_id)
        if obj is None:
            raise StorageObjectNotFound(f"storage object {object_id} does not exist")
        return obj

    def create_staging(
        self,
        *,
        namespace: str,
        object_key: str,
        backend: str | StorageObjectBackend = StorageObjectBackend.LOCAL,
        original_filename: str | None = None,
        content_type: str | None = None,
        size_bytes: int | None = None,
        sha256: str | None = None,
        etag: str | None = None,
        metadata_json: Mapping[str, Any] | None = None,
        created_by_id: int | None = None,
    ) -> StorageObject:
        namespace = _validate_namespace(namespace)
        object_key = _validate_object_key(object_key)
        backend = _validate_backend(backend)
        size_bytes = _validate_size(size_bytes)
        sha256 = _validate_sha256(sha256)
        if metadata_json is not None and not isinstance(metadata_json, Mapping):
            raise StorageObjectValidationError("metadata_json must be a JSON object")

        existing = self.db.scalar(
            select(StorageObject).where(
                StorageObject.namespace == namespace,
                StorageObject.object_key == object_key,
            )
        )
        if existing is not None:
            raise StorageObjectConflict(
                f"storage object {namespace}/{object_key} already exists"
            )

        obj = StorageObject(
            namespace=namespace,
            object_key=object_key,
            backend=backend,
            status=StorageObjectStatus.STAGING.value,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            sha256=sha256,
            etag=etag,
            metadata_json=dict(metadata_json or {}),
            created_by_id=created_by_id,
        )
        try:
            # Do not open a nested transaction here.  In SQLite's legacy
            # transaction mode, releasing a savepoint created by
            # ``begin_nested`` can make a standalone flush visible even when
            # the caller subsequently rolls back.  This service deliberately
            # has caller-owned transaction boundaries, so a plain flush keeps
            # the metadata row atomic with the business binding.
            self.db.add(obj)
            self.db.flush()
        except IntegrityError as exc:
            raise StorageObjectConflict(
                f"storage object {namespace}/{object_key} already exists"
            ) from exc
        return obj

    def activate(
        self,
        object_id: int,
        *,
        size_bytes: int | None = None,
        sha256: str | None = None,
        etag: str | None = None,
    ) -> StorageObject:
        obj = self.get(object_id)
        if obj.status == StorageObjectStatus.ACTIVE.value:
            return obj
        self._require_transition(obj, StorageObjectStatus.ACTIVE.value)
        resolved_size = _validate_size(size_bytes if size_bytes is not None else obj.size_bytes)
        if resolved_size is None:
            raise StorageObjectValidationError("active objects require size_bytes")
        obj.size_bytes = resolved_size
        obj.sha256 = _validate_sha256(sha256 if sha256 is not None else obj.sha256)
        if etag is not None:
            obj.etag = etag
        self._set_status(obj, StorageObjectStatus.ACTIVE.value)
        return obj

    def mark_failed(self, object_id: int) -> StorageObject:
        obj = self.get(object_id)
        if obj.status == StorageObjectStatus.FAILED.value:
            return obj
        self._require_transition(obj, StorageObjectStatus.FAILED.value)
        self._set_status(obj, StorageObjectStatus.FAILED.value)
        return obj

    def mark_deleting(self, object_id: int) -> StorageObject:
        obj = self.get(object_id)
        if obj.status in {
            StorageObjectStatus.DELETING.value,
            StorageObjectStatus.DELETED.value,
        }:
            return obj
        self._require_transition(obj, StorageObjectStatus.DELETING.value)
        self._set_status(obj, StorageObjectStatus.DELETING.value)
        return obj

    def mark_deleted(self, object_id: int) -> StorageObject:
        obj = self.get(object_id)
        if obj.status == StorageObjectStatus.DELETED.value:
            return obj
        self._require_transition(obj, StorageObjectStatus.DELETED.value)
        obj.deleted_at = datetime.now(timezone.utc)
        self._set_status(obj, StorageObjectStatus.DELETED.value)
        return obj

    def check_integrity(
        self,
        object_id: int,
        *,
        area: StorageArea | str,
        verify_sha256: bool = False,
    ) -> StorageIntegrityReport:
        if self.storage is None:
            raise StorageObjectValidationError("integrity checks require a StorageService")
        obj = self.get(object_id)
        try:
            physical = self.storage.head(area, obj.object_key)
        except StorageNotFound:
            return StorageIntegrityReport(
                object_id=obj.id,
                status=StorageIntegrityStatus.MISSING.value,
                is_consistent=False,
                physical_exists=False,
                expected_size=obj.size_bytes,
                actual_size=None,
                expected_sha256=obj.sha256,
                actual_sha256=None,
            )

        if obj.status == StorageObjectStatus.DELETED.value:
            return StorageIntegrityReport(
                object_id=obj.id,
                status=StorageIntegrityStatus.DELETED_PHYSICAL_PRESENT.value,
                is_consistent=False,
                physical_exists=True,
                expected_size=obj.size_bytes,
                actual_size=physical.size,
                expected_sha256=obj.sha256,
                actual_sha256=None,
            )

        if obj.size_bytes is not None and physical.size != obj.size_bytes:
            return StorageIntegrityReport(
                object_id=obj.id,
                status=StorageIntegrityStatus.SIZE_MISMATCH.value,
                is_consistent=False,
                physical_exists=True,
                expected_size=obj.size_bytes,
                actual_size=physical.size,
                expected_sha256=obj.sha256,
                actual_sha256=None,
            )

        actual_sha256 = None
        if verify_sha256 and obj.sha256:
            actual_sha256 = self._sha256(area, obj.object_key)
            if actual_sha256 != obj.sha256:
                return StorageIntegrityReport(
                    object_id=obj.id,
                    status=StorageIntegrityStatus.SHA256_MISMATCH.value,
                    is_consistent=False,
                    physical_exists=True,
                    expected_size=obj.size_bytes,
                    actual_size=physical.size,
                    expected_sha256=obj.sha256,
                    actual_sha256=actual_sha256,
                )

        return StorageIntegrityReport(
            object_id=obj.id,
            status=StorageIntegrityStatus.OK.value,
            is_consistent=True,
            physical_exists=True,
            expected_size=obj.size_bytes,
            actual_size=physical.size,
            expected_sha256=obj.sha256,
            actual_sha256=actual_sha256,
        )

    def _require_transition(self, obj: StorageObject, target: str) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(obj.status)
        if allowed is None or target not in allowed:
            raise StorageObjectStateError(
                f"cannot transition storage object {obj.id} from {obj.status} to {target}"
            )

    @staticmethod
    def _set_status(obj: StorageObject, status: str) -> None:
        obj.status = status
        obj.version += 1

    def _sha256(self, area: StorageArea | str, object_key: str) -> str:
        assert self.storage is not None
        stream = self.storage.open_read(area, object_key)
        digest = hashlib.sha256()
        try:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        finally:
            stream.close()
        return digest.hexdigest()
