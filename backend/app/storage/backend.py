"""Stable contracts shared by application storage backends.

The business services deal in logical storage keys.  Backends own the
translation from those keys to a physical storage implementation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Protocol, runtime_checkable


class StorageError(RuntimeError):
    """Base class for expected storage failures."""


class InvalidStorageKey(StorageError):
    """The logical key is absolute, traverses the root, or is malformed."""


class StorageNotFound(StorageError):
    """A requested object does not exist."""


class StorageConflict(StorageError):
    """The destination already exists or cannot be replaced safely."""


class StorageLimitExceeded(StorageError):
    """A streamed object exceeded its configured size limit."""

    def __init__(self, limit: int, actual: int) -> None:
        self.limit = limit
        self.actual = actual
        super().__init__(f"storage object exceeds {limit} bytes: {actual}")


class StorageRangeError(StorageError):
    """The requested byte range cannot be read from an object."""


@dataclass(frozen=True)
class StorageMetadata:
    """Metadata that is safe for business code to consume."""

    key: str
    size: int
    etag: str | None = None
    last_modified: datetime | None = None


@runtime_checkable
class StorageReadStream(Protocol):
    """A closeable, forward-only binary stream returned by a storage backend."""

    def read(self, size: int = -1) -> bytes:
        ...

    def close(self) -> None:
        ...


@runtime_checkable
class StorageObjectLister(Protocol):
    """Optional object-prefix enumeration used by Bundle/Asset services.

    Prefix enumeration is deliberately separate from the single-object core
    contract.  It does not imply directories or atomic tree operations.
    """

    def list_objects(self, prefix: str) -> tuple[StorageMetadata, ...]:
        ...


class StorageBackend(ABC):
    """Storage contract for single logical objects."""

    @abstractmethod
    def put(
        self,
        key: str,
        source: BinaryIO,
        *,
        max_bytes: int | None = None,
    ) -> StorageMetadata:
        """Store one object, replacing an existing object with the same key."""

    @abstractmethod
    def read(self, key: str) -> bytes:
        """Read one complete object into memory."""

    @abstractmethod
    def open_read(
        self,
        key: str,
        *,
        offset: int = 0,
        length: int | None = None,
    ) -> StorageReadStream:
        """Open a forward-only read stream for an optional byte slice.

        Callers own and must close the returned stream.  The stream does not
        promise ``seek`` or repeatable reads; byte ranges are expressed to the
        backend so network object stores do not need local file descriptors.
        """

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return whether one object exists at the logical key."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete one object; a missing object is ignored."""

    @abstractmethod
    def copy(
        self,
        source_key: str,
        destination_key: str,
    ) -> StorageMetadata:
        """Copy one object; an existing destination raises StorageConflict."""

    @abstractmethod
    def head(self, key: str) -> StorageMetadata:
        """Return metadata or raise StorageNotFound."""
