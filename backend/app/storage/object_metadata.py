"""Storage object metadata vocabulary shared by ORM and lifecycle services."""

from enum import StrEnum


class StorageObjectBackend(StrEnum):
    """Backend identifiers stored in ``storage_objects.backend``."""

    LOCAL = "local"
    S3 = "s3"


class StorageObjectStatus(StrEnum):
    """Persisted lifecycle states for a storage object metadata row."""

    STAGING = "staging"
    ACTIVE = "active"
    DELETING = "deleting"
    DELETED = "deleted"
    FAILED = "failed"
