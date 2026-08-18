from __future__ import annotations

import inspect
from io import BytesIO

import pytest

from app.storage import backend as storage_backend_module
from app.storage import (
    InvalidStorageKey,
    LocalFilesystemStorage,
    StorageConflict,
    StorageLimitExceeded,
    StorageNotFound,
    StorageRangeError,
    StorageService,
)


@pytest.fixture()
def storage(tmp_path):
    backend = LocalFilesystemStorage(tmp_path / "storage")
    return StorageService({"files": backend})


def test_put_read_exists_and_head(storage):
    metadata = storage.put("files", "documents/hello.txt", BytesIO(b"hello"))

    assert metadata.key == "documents/hello.txt"
    assert metadata.size == 5
    assert storage.exists("files", "documents/hello.txt") is True
    assert storage.read("files", "documents/hello.txt") == b"hello"
    assert storage.head("files", "documents/hello.txt") == metadata


def test_storage_core_contract_is_object_only_and_http_agnostic():
    backend_source = inspect.getsource(storage_backend_module)

    assert not hasattr(storage_backend_module.StorageBackend, "file_response")
    assert not hasattr(storage_backend_module.StorageBackend, "put_tree")
    assert not hasattr(storage_backend_module.StorageBackend, "open")
    assert not hasattr(StorageService, "file_response")
    assert not hasattr(StorageService, "put_tree")
    assert not hasattr(LocalFilesystemStorage, "file_response")
    assert not hasattr(LocalFilesystemStorage, "put_tree")
    assert "FileResponse" not in backend_source
    assert "fastapi" not in backend_source.lower()
    assert "starlette" not in backend_source.lower()

    metadata_fields = set(storage_backend_module.StorageMetadata.__dataclass_fields__)
    assert {"key", "size"}.issubset(metadata_fields)
    assert "is_dir" not in metadata_fields


def test_put_overwrites_existing_object(storage):
    storage.put("files", "documents/hello.txt", BytesIO(b"old"))

    metadata = storage.put("files", "documents/hello.txt", BytesIO(b"new-value"))

    assert metadata.size == len(b"new-value")
    assert storage.read("files", "documents/hello.txt") == b"new-value"


def test_open_read_returns_non_seekable_contract_and_supports_backend_range(storage):
    storage.put("files", "documents/hello.txt", BytesIO(b"hello"))

    stream = storage.open_read("files", "documents/hello.txt", offset=1, length=3)
    try:
        assert stream.read() == b"ell"
        assert not hasattr(stream, "seek")
    finally:
        stream.close()


def test_open_read_rejects_ranges_outside_object(storage):
    storage.put("files", "documents/hello.txt", BytesIO(b"hello"))

    with pytest.raises(StorageRangeError):
        storage.open_read("files", "documents/hello.txt", offset=-1)
    with pytest.raises(StorageRangeError):
        storage.open_read("files", "documents/hello.txt", offset=6)


def test_delete_is_idempotent_and_missing_reads_are_explicit(storage):
    storage.delete("files", "missing.txt")

    with pytest.raises(StorageNotFound):
        storage.read("files", "missing.txt")
    with pytest.raises(StorageNotFound):
        storage.head("files", "missing.txt")

    storage.put("files", "documents/hello.txt", BytesIO(b"hello"))
    storage.delete("files", "documents/hello.txt")
    storage.delete("files", "documents/hello.txt")
    assert storage.exists("files", "documents/hello.txt") is False


def test_put_cleans_staging_after_success_and_size_failure(storage, tmp_path):
    storage.put("files", "ok.txt", BytesIO(b"ok"))
    staging = tmp_path / "storage" / ".staging"
    assert list(staging.iterdir()) == []

    with pytest.raises(StorageLimitExceeded):
        storage.put("files", "too-large.txt", BytesIO(b"012345"), max_bytes=4)

    assert list(staging.iterdir()) == []
    assert storage.exists("files", "too-large.txt") is False


def test_copy_file_is_safe_and_destination_conflicts_are_explicit(storage):
    storage.put("files", "source.txt", BytesIO(b"source"))
    storage.copy("files", "source.txt", "copied.txt")
    assert storage.read("files", "copied.txt") == b"source"

    with pytest.raises(StorageConflict):
        storage.copy("files", "source.txt", "copied.txt")


def test_object_exists_and_head_do_not_treat_prefix_as_a_directory(storage):
    storage.put("files", "trees/source/a.txt", BytesIO(b"a"))

    assert storage.exists("files", "trees/source") is False
    with pytest.raises(StorageNotFound):
        storage.head("files", "trees/source")

    objects = storage.list_objects("files", "trees/source")
    assert [(item.key, item.size) for item in objects] == [("trees/source/a.txt", 1)]


@pytest.mark.parametrize(
    "key",
    [
        "../escape.txt",
        "a/../../escape.txt",
        "/absolute.txt",
        "a\\b.txt",
        ".staging/secret.txt",
        "C:/absolute.txt",
        "",
        ".",
        "./",
    ],
)
def test_rejects_invalid_keys(storage, key):
    with pytest.raises(InvalidStorageKey):
        storage.exists("files", key)


def test_rejects_symlink_escape_from_storage_root(storage, tmp_path):
    root = tmp_path / "storage"
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "link").parent.mkdir(parents=True, exist_ok=True)
        (root / "link").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("当前文件系统不支持符号链接")

    with pytest.raises(InvalidStorageKey):
        storage.exists("files", "link/secret.txt")
