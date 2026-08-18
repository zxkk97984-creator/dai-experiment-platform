"""Local filesystem implementation of the single-object storage contract."""
from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from .backend import (
    InvalidStorageKey,
    StorageBackend,
    StorageConflict,
    StorageLimitExceeded,
    StorageMetadata,
    StorageNotFound,
    StorageRangeError,
    StorageReadStream,
)


_CHUNK_SIZE = 1024 * 1024
_STAGING_DIR = ".staging"


class _LimitedReadStream:
    """Expose a bounded, forward-only view over a local binary file."""

    def __init__(self, source: BinaryIO, length: int | None) -> None:
        self._source = source
        self._remaining = length

    def read(self, size: int = -1) -> bytes:
        if self._remaining == 0:
            return b""
        if self._remaining is not None and (size < 0 or size > self._remaining):
            size = self._remaining
        chunk = self._source.read(size)
        if self._remaining is not None:
            self._remaining -= len(chunk)
        return chunk

    def close(self) -> None:
        self._source.close()


class LocalFilesystemStorage(StorageBackend):
    """Store logical object keys below one private, validated filesystem root.

    ``key_prefix`` supports legacy logical keys such as ``covers/42/file.png``
    while keeping the existing physical layout at ``<cover-root>/42/file.png``.
    """

    def __init__(self, root: str | Path, *, key_prefix: str = "") -> None:
        self._root = Path(root).resolve()
        self._key_prefix = key_prefix.strip("/")

    def _relative_parts(self, key: str) -> tuple[str, ...]:
        if not isinstance(key, str) or not key or "\x00" in key:
            raise InvalidStorageKey("storage key must be a non-empty string")
        if "\\" in key or key.startswith("/") or "//" in key:
            raise InvalidStorageKey("storage key must use safe POSIX segments")

        parts = tuple(key.split("/"))
        if any(part in {"", ".", ".."} for part in parts):
            raise InvalidStorageKey("storage key contains an invalid path segment")
        if ":" in parts[0]:
            raise InvalidStorageKey("storage key cannot contain a drive prefix")

        if self._key_prefix:
            prefix_parts = tuple(self._key_prefix.split("/"))
            if parts[: len(prefix_parts)] != prefix_parts:
                raise InvalidStorageKey("storage key has an invalid namespace")
            parts = parts[len(prefix_parts) :]

        if not parts or parts[0] == _STAGING_DIR:
            raise InvalidStorageKey("storage key targets a reserved path")
        return parts

    def _resolve(self, key: str) -> Path:
        parts = self._relative_parts(key)
        candidate = (self._root / Path(*parts)).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise InvalidStorageKey("storage key escapes the storage root") from exc
        return candidate

    def _staging_root(self) -> Path:
        staging = self._root / _STAGING_DIR
        staging.mkdir(parents=True, exist_ok=True)
        return staging

    def _existing_file(self, key: str) -> Path:
        path = self._resolve(key)
        if not path.is_file():
            raise StorageNotFound(key)
        return path

    def _metadata(self, key: str, path: Path) -> StorageMetadata:
        stat_result = path.stat()
        etag_base = f"{stat_result.st_mtime}-{stat_result.st_size}".encode()
        etag = f'"{hashlib.md5(etag_base, usedforsecurity=False).hexdigest()}"'
        return StorageMetadata(
            key=key,
            size=stat_result.st_size,
            etag=etag,
            last_modified=datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc),
        )

    def put(
        self,
        key: str,
        source: BinaryIO,
        *,
        max_bytes: int | None = None,
    ) -> StorageMetadata:
        """Write one object and replace an existing object with the same key."""
        final = self._resolve(key)
        staging_file = self._staging_root() / f"{uuid.uuid4().hex}.part"
        total = 0
        try:
            with staging_file.open("wb") as output:
                while True:
                    chunk = source.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    total += len(chunk)
                    if max_bytes is not None and total > max_bytes:
                        raise StorageLimitExceeded(max_bytes, total)
                    output.write(chunk)
            final.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(staging_file, final)
            except (FileExistsError, IsADirectoryError) as exc:
                raise StorageConflict(key) from exc
            return self._metadata(key, final)
        finally:
            if staging_file.exists():
                try:
                    staging_file.unlink()
                except OSError:
                    pass

    def read(self, key: str) -> bytes:
        path = self._existing_file(key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise StorageNotFound(key) from exc

    def open_read(
        self,
        key: str,
        *,
        offset: int = 0,
        length: int | None = None,
    ) -> StorageReadStream:
        path = self._existing_file(key)
        if offset < 0 or (length is not None and length < 0):
            raise StorageRangeError("offset and length must be non-negative")
        try:
            size = path.stat().st_size
        except FileNotFoundError as exc:
            raise StorageNotFound(key) from exc
        if offset > size:
            raise StorageRangeError("offset is beyond the object size")
        try:
            source = path.open("rb")
            source.seek(offset)
        except FileNotFoundError as exc:
            raise StorageNotFound(key) from exc
        except Exception:
            if "source" in locals():
                source.close()
            raise
        return _LimitedReadStream(source, length)

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if not path.exists():
            return
        if not path.is_file():
            raise StorageConflict(f"storage key is not a single object: {key}")
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def copy(self, source_key: str, destination_key: str) -> StorageMetadata:
        source = self._existing_file(source_key)
        destination = self._resolve(destination_key)
        if destination.exists():
            raise StorageConflict(destination_key)

        staging = self._staging_root() / f"{uuid.uuid4().hex}.part"
        try:
            shutil.copyfile(source, staging)
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(staging, destination)
            except (FileExistsError, IsADirectoryError) as exc:
                raise StorageConflict(destination_key) from exc
            return self._metadata(destination_key, destination)
        except FileNotFoundError as exc:
            raise StorageNotFound(source_key) from exc
        finally:
            if staging.exists():
                try:
                    staging.unlink()
                except OSError:
                    pass

    def head(self, key: str) -> StorageMetadata:
        path = self._existing_file(key)
        try:
            return self._metadata(key, path)
        except FileNotFoundError as exc:
            raise StorageNotFound(key) from exc

    def list_objects(self, prefix: str) -> tuple[StorageMetadata, ...]:
        """Enumerate object keys below a logical prefix for Bundle services."""
        base = self._resolve(prefix)
        if base.is_file():
            return (self._metadata(prefix, base),)
        if not base.exists():
            return ()
        if not base.is_dir():
            return ()

        objects: list[StorageMetadata] = []
        for candidate in base.rglob("*"):
            relative_to_root = candidate.relative_to(self._root)
            if _STAGING_DIR in relative_to_root.parts:
                continue
            if candidate.is_symlink():
                raise InvalidStorageKey("storage tree cannot contain symlinks")
            if not candidate.is_file():
                continue
            try:
                candidate.resolve().relative_to(self._root)
            except ValueError as exc:
                raise InvalidStorageKey("storage object escapes the storage root") from exc
            relative = candidate.relative_to(self._root).as_posix()
            logical_key = (
                f"{self._key_prefix}/{relative}" if self._key_prefix else relative
            )
            objects.append(self._metadata(logical_key, candidate))
        return tuple(sorted(objects, key=lambda item: item.key))
