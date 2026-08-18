"""Shared helpers for binding newly uploaded business files to StorageObject.

The helpers deliberately keep the database transaction boundary with the API
handler.  A physical object is written before this module creates metadata, and
old objects are retired only after the business row has been committed.
"""

from __future__ import annotations

import hashlib
import logging

from sqlalchemy.orm import Session

from app.models import StorageObject
from app.services.storage_object_service import (
    StorageObjectNotFound,
    StorageObjectService,
)
from app.storage import StorageArea, StorageError, StorageService


def register_active_object(
    db: Session,
    storage: StorageService,
    *,
    area: StorageArea,
    namespace: str,
    object_key: str,
    original_filename: str,
    content_type: str,
    size_bytes: int,
    created_by_id: int | None,
) -> StorageObject:
    """Create and activate metadata for an already-written physical object."""
    physical = storage.head(area, object_key)
    digest = _sha256(storage, area, object_key)
    service = StorageObjectService(db, storage)
    obj = service.create_staging(
        namespace=namespace,
        object_key=object_key,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=digest,
        etag=physical.etag,
        metadata_json={"storage_area": area.value},
        created_by_id=created_by_id,
    )
    service.activate(
        obj.id,
        size_bytes=size_bytes,
        sha256=digest,
        etag=physical.etag,
    )
    return obj


def retire_bound_object(
    db: Session,
    storage: StorageService,
    *,
    object_id: int | None,
    area: StorageArea,
    legacy_key: str | None,
    logger_name: str,
) -> None:
    """Retire one bound object, or clean a pre-Phase-2B legacy key.

    This function is called after the owning Course/Lesson row is committed.
    It intentionally leaves metadata in ``deleting`` if physical deletion
    fails, allowing a later reconciler to retry safely.
    """
    logger = logging.getLogger(logger_name)
    if object_id is None:
        _delete_legacy_key(storage, area, legacy_key, logger)
        return

    service = StorageObjectService(db, storage)
    try:
        obj = service.get(object_id)
    except StorageObjectNotFound:
        logger.error("bound storage object is missing: id=%s key=%s", object_id, legacy_key)
        _delete_legacy_key(storage, area, legacy_key, logger)
        return

    # A legacy/manual update may have changed the business key without
    # clearing the nullable binding.  Never delete the physical object of a
    # mismatched metadata row; leave it for a later orphan reconciliation and
    # only apply the legacy-key cleanup rules to the key currently on the row.
    if legacy_key is not None and obj.object_key != legacy_key:
        logger.warning(
            "storage object binding key mismatch: id=%s metadata_key=%s business_key=%s",
            object_id,
            obj.object_key,
            legacy_key,
        )
        _delete_legacy_key(storage, area, legacy_key, logger)
        return

    try:
        service.mark_deleting(object_id)
        db.commit()
    except Exception:
        db.rollback()
        logger.error("failed to mark storage object deleting: id=%s", object_id, exc_info=True)
        return

    try:
        storage.delete(area, obj.object_key)
    except StorageError:
        logger.error(
            "failed to remove retired storage object: id=%s key=%s",
            object_id,
            obj.object_key,
            exc_info=True,
        )
        return

    try:
        service.mark_deleted(object_id)
        db.commit()
    except Exception:
        db.rollback()
        logger.error("failed to mark storage object deleted: id=%s", object_id, exc_info=True)


def _sha256(storage: StorageService, area: StorageArea, object_key: str) -> str:
    stream = storage.open_read(area, object_key)
    digest = hashlib.sha256()
    try:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    finally:
        stream.close()
    return digest.hexdigest()


def _delete_legacy_key(
    storage: StorageService,
    area: StorageArea,
    key: str | None,
    logger: logging.Logger,
) -> None:
    if not key:
        return
    if area == StorageArea.COVERS and not key.startswith("covers/"):
        return
    try:
        storage.delete(area, key)
    except StorageError:
        logger.error("failed to remove legacy storage key: %s", key, exc_info=True)
