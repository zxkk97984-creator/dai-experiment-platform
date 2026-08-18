from __future__ import annotations

from io import BytesIO

import pytest

from app.services.studio_asset_service import StudioAssetBundleService
from app.storage import (
    InvalidStorageKey,
    LocalFilesystemStorage,
    StorageArea,
    StorageConflict,
    StorageService,
)


@pytest.fixture()
def bundle_service(tmp_path):
    storage = StorageService(
        {StorageArea.STUDIO: LocalFilesystemStorage(tmp_path / "studio")}
    )
    return StudioAssetBundleService(storage), storage


def test_bundle_writes_objects_without_directory_object(bundle_service):
    bundle, storage = bundle_service

    bundle.put(
        "templates/1/draft-r1-token",
        (("assets/data.csv", b"x,y\n1,2\n"), ("notes/readme.txt", b"read me")),
    )

    assert storage.exists(StorageArea.STUDIO, "templates/1/draft-r1-token") is False
    objects = storage.list_objects(StorageArea.STUDIO, "templates/1/draft-r1-token")
    assert [item.key for item in objects] == [
        "templates/1/draft-r1-token/assets/data.csv",
        "templates/1/draft-r1-token/notes/readme.txt",
    ]


def test_bundle_rejects_duplicate_or_dot_entries_without_partial_objects(bundle_service):
    bundle, storage = bundle_service

    with pytest.raises(StorageConflict):
        bundle.put(
            "templates/1/draft-r1-duplicate",
            (("assets/data.csv", b"a"), ("assets/data.csv", b"b")),
        )

    assert storage.list_objects(
        StorageArea.STUDIO, "templates/1/draft-r1-duplicate"
    ) == ()

    with pytest.raises(InvalidStorageKey):
        bundle.put("templates/1/draft-r1-dot", ((".", b"bad"),))


def test_bundle_copy_and_delete_are_composed_from_single_object_operations(bundle_service):
    bundle, storage = bundle_service
    source = "templates/1/draft-r1-source"
    destination = "templates/1/versions/1"
    bundle.put(source, (("assets/data.csv", b"data"),))

    bundle.copy(source, destination)

    assert storage.read(
        StorageArea.STUDIO, f"{destination}/assets/data.csv"
    ) == b"data"
    with pytest.raises(StorageConflict):
        bundle.copy(source, destination)

    bundle.delete(destination)
    bundle.delete(destination)
    assert storage.list_objects(StorageArea.STUDIO, destination) == ()
