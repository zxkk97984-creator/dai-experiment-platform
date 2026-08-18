"""Studio asset bundle orchestration over single-object storage operations."""
from __future__ import annotations

from io import BytesIO

from app.storage import (
    InvalidStorageKey,
    StorageArea,
    StorageConflict,
    StorageError,
    StorageNotFound,
    StorageService,
)


def _validate_bundle_key(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise InvalidStorageKey(f"{label} must be a non-empty key")
    if "\\" in value or value.startswith("/") or value.endswith("/") or "//" in value:
        raise InvalidStorageKey(f"{label} must use safe POSIX segments")
    parts = tuple(value.split("/"))
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise InvalidStorageKey(f"{label} contains an invalid path segment")
    if ":" in parts[0]:
        raise InvalidStorageKey(f"{label} cannot contain a drive prefix")
    return "/".join(parts)


def _object_key(prefix: str, relative: str) -> str:
    return f"{prefix}/{relative}"


class StudioAssetBundleService:
    """Manage Studio bundles without exposing directory operations to Storage.

    A bundle is a logical key prefix containing multiple independent objects.
    The service cleans up objects after a failed multi-object operation, but it
    deliberately does not promise cross-backend atomicity.
    """

    area = StorageArea.STUDIO

    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    def put(
        self,
        prefix: str,
        entries: tuple[tuple[str, bytes], ...] | list[tuple[str, bytes]],
    ) -> str:
        prefix = _validate_bundle_key(prefix, label="bundle prefix")
        normalized: list[tuple[str, bytes]] = []
        seen: set[str] = set()
        for relative, content in entries:
            relative = _validate_bundle_key(relative, label="bundle entry")
            if relative in seen:
                raise StorageConflict(f"duplicate bundle entry: {relative}")
            if not isinstance(content, bytes):
                raise TypeError("bundle entry content must be bytes")
            seen.add(relative)
            normalized.append((relative, content))

        if self._storage.list_objects(self.area, prefix):
            raise StorageConflict(prefix)

        written: list[str] = []
        try:
            for relative, content in normalized:
                key = _object_key(prefix, relative)
                self._storage.put(self.area, key, BytesIO(content))
                written.append(key)
        except Exception:
            self._delete_written(written)
            raise
        return prefix

    def copy(self, source_prefix: str, destination_prefix: str) -> str:
        source_prefix = _validate_bundle_key(source_prefix, label="source bundle prefix")
        destination_prefix = _validate_bundle_key(
            destination_prefix, label="destination bundle prefix"
        )
        source_objects = self._storage.list_objects(self.area, source_prefix)
        if not source_objects:
            raise StorageNotFound(source_prefix)
        if self._storage.list_objects(self.area, destination_prefix):
            raise StorageConflict(destination_prefix)

        source_root = f"{source_prefix}/"
        copied: list[str] = []
        try:
            for source in source_objects:
                if not source.key.startswith(source_root):
                    raise StorageError("bundle listing returned an invalid object key")
                relative = source.key[len(source_root) :]
                destination = _object_key(destination_prefix, relative)
                self._storage.copy(self.area, source.key, destination)
                copied.append(destination)
        except Exception:
            self._delete_written(copied)
            raise
        return destination_prefix

    def delete(self, prefix: str) -> None:
        prefix = _validate_bundle_key(prefix, label="bundle prefix")
        for metadata in self._storage.list_objects(self.area, prefix):
            self._storage.delete(self.area, metadata.key)

    def _delete_written(self, keys: list[str]) -> None:
        for key in keys:
            try:
                self._storage.delete(self.area, key)
            except StorageError:
                # Preserve the original write/copy error; cleanup is best effort.
                pass
