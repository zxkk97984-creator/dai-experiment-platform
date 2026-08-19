"""One behavioral contract executed against every StorageBackend implementation."""

from __future__ import annotations

from io import BytesIO

import boto3
import pytest
from moto import mock_aws

from app.config import Settings
from app.storage import (
    InvalidStorageKey,
    LocalFilesystemStorage,
    S3CompatibleStorage,
    StorageArea,
    StorageConflict,
    StorageLimitExceeded,
    StorageNotFound,
    StorageRangeError,
    StorageService,
)


@pytest.fixture(params=["local", "s3"], ids=["local", "s3"])
def backend(request, tmp_path):
    if request.param == "local":
        yield LocalFilesystemStorage(tmp_path / "storage")
        return

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="contract-bucket")
        yield S3CompatibleStorage(client, bucket="contract-bucket")


def test_put_read_exists_and_head(backend):
    metadata = backend.put("documents/hello.txt", BytesIO(b"hello"))

    assert metadata.key == "documents/hello.txt"
    assert metadata.size == 5
    assert metadata.etag
    assert backend.exists("documents/hello.txt") is True
    assert backend.read("documents/hello.txt") == b"hello"
    assert backend.head("documents/hello.txt") == metadata


def test_put_overwrites_existing_object(backend):
    backend.put("documents/hello.txt", BytesIO(b"old"))

    metadata = backend.put("documents/hello.txt", BytesIO(b"new-value"))

    assert metadata.size == len(b"new-value")
    assert backend.read("documents/hello.txt") == b"new-value"


def test_open_read_is_forward_only_and_supports_range(backend):
    backend.put("documents/hello.txt", BytesIO(b"hello"))

    stream = backend.open_read("documents/hello.txt", offset=1, length=3)
    try:
        assert stream.read() == b"ell"
        assert not hasattr(stream, "seek")
    finally:
        stream.close()


def test_open_read_rejects_invalid_ranges(backend):
    backend.put("documents/hello.txt", BytesIO(b"hello"))

    with pytest.raises(StorageRangeError):
        backend.open_read("documents/hello.txt", offset=-1)
    with pytest.raises(StorageRangeError):
        backend.open_read("documents/hello.txt", offset=6)


def test_delete_is_idempotent_and_missing_reads_are_explicit(backend):
    backend.delete("missing.txt")

    with pytest.raises(StorageNotFound):
        backend.read("missing.txt")
    with pytest.raises(StorageNotFound):
        backend.head("missing.txt")

    backend.put("documents/hello.txt", BytesIO(b"hello"))
    backend.delete("documents/hello.txt")
    backend.delete("documents/hello.txt")
    assert backend.exists("documents/hello.txt") is False


def test_put_rejects_oversize_input_without_leaving_an_object(backend):
    with pytest.raises(StorageLimitExceeded):
        backend.put("too-large.txt", BytesIO(b"012345"), max_bytes=4)

    assert backend.exists("too-large.txt") is False


def test_copy_is_single_object_and_destination_conflicts_are_explicit(backend):
    backend.put("source.txt", BytesIO(b"source"))

    metadata = backend.copy("source.txt", "copied.txt")

    assert metadata.key == "copied.txt"
    assert backend.read("copied.txt") == b"source"
    with pytest.raises(StorageConflict):
        backend.copy("source.txt", "copied.txt")


def test_prefix_listing_returns_objects_not_directories(backend):
    backend.put("trees/source/a.txt", BytesIO(b"a"))
    backend.put("trees/source/nested/b.txt", BytesIO(b"bb"))

    assert backend.exists("trees/source") is False
    with pytest.raises(StorageNotFound):
        backend.head("trees/source")
    assert [item.key for item in backend.list_objects("trees/source")] == [
        "trees/source/a.txt",
        "trees/source/nested/b.txt",
    ]


@pytest.mark.parametrize(
    "key",
    [
        "../escape.txt",
        "a/../../escape.txt",
        "/absolute.txt",
        "a\\b.txt",
        "",
        ".",
        "./",
    ],
)
def test_invalid_keys_have_the_same_contract(backend, key):
    with pytest.raises(InvalidStorageKey):
        backend.exists(key)


def test_s3_physical_prefix_does_not_change_logical_keys():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="prefix-bucket")
        backend = S3CompatibleStorage(
            client,
            bucket="prefix-bucket",
            key_prefix="platform",
        )

        metadata = backend.put("covers/42/cover.png", BytesIO(b"cover"))

        assert metadata.key == "covers/42/cover.png"
        assert client.head_object(
            Bucket="prefix-bucket",
            Key="platform/covers/42/cover.png",
        )["ContentLength"] == 5
        assert [item.key for item in backend.list_objects("covers/42")] == [
            "covers/42/cover.png"
        ]


def test_local_key_prefix_can_list_namespace_root(tmp_path):
    backend = LocalFilesystemStorage(tmp_path / "covers", key_prefix="covers")
    backend.put("covers/42/cover.png", BytesIO(b"cover"))

    assert [item.key for item in backend.list_objects("covers")] == [
        "covers/42/cover.png"
    ]


def test_storage_service_selects_one_s3_backend_for_all_areas():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="service-bucket")
        settings = Settings(
            storage_backend="s3",
            storage_s3_bucket="service-bucket",
            storage_s3_access_key_id="testing",
            storage_s3_secret_access_key="testing",
        )
        service = StorageService.from_settings(settings)

        service.put(StorageArea.COVERS, "covers/42/cover.png", BytesIO(b"cover"))
        assert service.read(StorageArea.COVERS, "covers/42/cover.png") == b"cover"
        assert service.exists(StorageArea.VIDEOS, "lessons/7/video.mp4") is False
