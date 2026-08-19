"""Phase 3 Studio asset manifest and export regression tests."""

from __future__ import annotations

from io import BytesIO
import zipfile

import nbformat
import pytest
from fastapi.testclient import TestClient

from app.models import (
    NotebookTemplate,
    NotebookTemplateVersion,
    StorageObject,
    StorageObjectStatus,
    StudioAssetManifest,
    StudioAssetManifestEntry,
)
from app.services.studio_asset_service import StudioAssetBundleService
from app.services.storage_object_service import StorageIntegrityStatus, StorageObjectService
from app.storage import StorageArea, StorageService
from test_studio import (
    _headers,
    _notebook_bytes,
    _zip_bytes,
    studio_context as studio_context_fixture,
)


API = "/api/v1"


@pytest.fixture
def studio_context(request):
    """Reuse the Studio domain fixture without making it a test module dependency."""
    return request.getfixturevalue("studio_context_fixture")


def _asset_zip() -> bytes:
    return _zip_bytes(
        [
            ("notebook.ipynb", _notebook_bytes(), None),
            ("assets/image.png", b"PNGDATA", None),
            ("assets/data.csv", b"x,y\n1,2\n", None),
        ]
    )


def _template_from_import(client, ctx, filename: str = "lesson.zip"):
    response = client.post(
        f"{API}/studio/templates/import",
        headers=_headers(ctx, "studio_teacher"),
        data={"name": "Manifest template", "lesson_id": str(ctx["lesson_id"])},
        files={"file": (filename, _asset_zip(), "application/zip")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _zip_names_and_contents(payload: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_import_draft_publish_reopen_and_export_preserves_all_assets(
    client, db_session_factory, studio_context, test_settings
):
    ctx = studio_context
    imported = _template_from_import(client, ctx)
    template_id = imported["id"]

    assert {asset["relative_path"] for asset in imported["draft_assets"]} == {
        "assets/image.png",
        "assets/data.csv",
    }
    assert imported["draft_asset_manifest_id"] is not None

    with db_session_factory() as db:
        manifest = db.query(StudioAssetManifest).filter_by(template_id=template_id).one()
        entries = (
            db.query(StudioAssetManifestEntry)
            .filter_by(manifest_id=manifest.id)
            .order_by(StudioAssetManifestEntry.relative_path)
            .all()
        )
        assert len(entries) == 2
        for entry in entries:
            obj = db.get(StorageObject, entry.storage_object_id)
            assert obj is not None
            assert obj.status == StorageObjectStatus.ACTIVE.value
            assert obj.namespace == "studio-assets"
            assert obj.object_key.startswith(f"templates/{template_id}/draft-")
            assert obj.sha256
            assert obj.metadata_json == {"storage_area": "studio"}
            assert obj.size_bytes == len(
                b"PNGDATA" if entry.relative_path.endswith("image.png") else b"x,y\n1,2\n"
            )
            report = StorageObjectService(
                db, StorageService.from_settings(test_settings)
            ).check_integrity(obj.id, area=StorageArea.STUDIO, verify_sha256=True)
            assert report.status == StorageIntegrityStatus.OK.value
            assert report.is_consistent

    published = client.post(
        f"{API}/studio/templates/{template_id}/publish",
        headers=_headers(ctx, "studio_teacher"),
    )
    assert published.status_code == 201, published.text
    version = published.json()
    assert {asset["relative_path"] for asset in version["assets"]} == {
        "assets/image.png",
        "assets/data.csv",
    }
    assert version["asset_manifest_id"] is not None

    reopened = client.get(
        f"{API}/studio/templates/{template_id}",
        headers=_headers(ctx, "studio_teacher"),
    )
    assert reopened.status_code == 200, reopened.text
    assert {
        asset["relative_path"]
        for asset in reopened.json()["current_version"]["assets"]
    } == {"assets/image.png", "assets/data.csv"}

    for query in ("scope=draft", f"version_id={version['id']}"):
        exported = client.get(
            f"{API}/studio/templates/{template_id}/export?{query}",
            headers=_headers(ctx, "studio_teacher"),
        )
        assert exported.status_code == 200, exported.text
        assert exported.headers["content-type"].startswith("application/zip")
        names = _zip_names_and_contents(exported.content)
        assert set(names) == {
            "notebook.ipynb",
            "assets/image.png",
            "assets/data.csv",
        }
        assert nbformat.reads(names["notebook.ipynb"].decode(), as_version=4).cells
        assert names["assets/image.png"] == b"PNGDATA"
        assert names["assets/data.csv"] == b"x,y\n1,2\n"

    with db_session_factory() as db:
        version_row = db.get(NotebookTemplateVersion, version["id"])
        assert version_row is not None
        version_manifest = (
            db.query(StudioAssetManifest).filter_by(version_id=version_row.id).one()
        )
        version_objects = (
            db.query(StorageObject)
            .join(StudioAssetManifestEntry)
            .filter(StudioAssetManifestEntry.manifest_id == version_manifest.id)
            .all()
        )
        assert len(version_objects) == 2
        assert all(obj.status == StorageObjectStatus.ACTIVE.value for obj in version_objects)
        for obj in version_objects:
            report = StorageObjectService(
                db, StorageService.from_settings(test_settings)
            ).check_integrity(obj.id, area=StorageArea.STUDIO, verify_sha256=True)
            assert report.is_consistent

    assert StorageService.from_settings(test_settings).list_objects(
        StorageArea.STUDIO, f"templates/{template_id}/versions/1"
    )


def test_duplicate_asset_path_is_rejected_before_template_or_storage_creation(
    client, db_session_factory, studio_context, test_settings
):
    ctx = studio_context
    payload = _zip_bytes(
        [
            ("notebook.ipynb", _notebook_bytes(), None),
            ("assets/data.csv", b"first", None),
            ("assets/data.csv", b"second", None),
        ]
    )
    with db_session_factory() as db:
        templates_before = db.query(NotebookTemplate).count()
        objects_before = db.query(StorageObject).count()

    response = client.post(
        f"{API}/studio/templates/import",
        headers=_headers(ctx, "studio_teacher"),
        data={"name": "Duplicate asset", "lesson_id": str(ctx["lesson_id"])},
        files={"file": ("duplicate.zip", payload, "application/zip")},
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "ZIP_DUPLICATE_ASSET"
    with db_session_factory() as db:
        assert db.query(NotebookTemplate).count() == templates_before
        assert db.query(StorageObject).count() == objects_before
    assert StorageService.from_settings(test_settings).list_objects(
        StorageArea.STUDIO, "templates"
    ) == ()


def test_publish_failure_rolls_back_version_manifest_and_destination_objects(
    client, app, db_session_factory, studio_context, test_settings, monkeypatch
):
    ctx = studio_context
    imported = _template_from_import(client, ctx, "publish-failure.zip")
    template_id = imported["id"]

    from sqlalchemy.orm import Session as ORMSession

    original_commit = ORMSession.commit

    def fail_commit(self, *args, **kwargs):
        raise RuntimeError("publish database unavailable")

    monkeypatch.setattr(ORMSession, "commit", fail_commit)
    quiet_client = TestClient(app, raise_server_exceptions=False)
    try:
        response = quiet_client.post(
            f"{API}/studio/templates/{template_id}/publish",
            headers=_headers(ctx, "studio_teacher"),
        )
    finally:
        quiet_client.close()
    assert response.status_code == 500
    monkeypatch.setattr(ORMSession, "commit", original_commit)

    with db_session_factory() as db:
        assert db.query(NotebookTemplateVersion).filter_by(template_id=template_id).count() == 0
        assert db.query(StudioAssetManifest).filter(
            StudioAssetManifest.version_id.is_not(None)
        ).count() == 0
        draft = db.query(StudioAssetManifest).filter_by(template_id=template_id).one()
        assert len(draft.entries) == 2

    assert StorageService.from_settings(test_settings).list_objects(
        StorageArea.STUDIO, f"templates/{template_id}/versions/1"
    ) == ()


def test_legacy_directory_assets_are_read_and_exported_without_manifest(
    client, db_session_factory, studio_context, test_settings
):
    ctx = studio_context
    created = client.post(
        f"{API}/studio/templates",
        headers=_headers(ctx, "studio_teacher"),
        json={"name": "Legacy assets", "lesson_id": ctx["lesson_id"]},
    )
    assert created.status_code == 201, created.text
    template_id = created.json()["id"]
    prefix = f"templates/{template_id}/legacy-assets"
    storage = StorageService.from_settings(test_settings)
    StudioAssetBundleService(storage).put(
        prefix,
        (("assets/legacy.csv", b"legacy\n"),),
    )
    with db_session_factory() as db:
        template = db.get(NotebookTemplate, template_id)
        db.query(StudioAssetManifest).filter_by(template_id=template_id).delete()
        template.draft_assets_dir = prefix
        db.commit()

    detail = client.get(
        f"{API}/studio/templates/{template_id}",
        headers=_headers(ctx, "studio_teacher"),
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["draft_asset_manifest_id"] is None
    assert detail.json()["draft_assets"] == [
        {
            "relative_path": "assets/legacy.csv",
            "storage_object_id": None,
            "content_type": "text/csv",
            "size_bytes": 7,
            "sha256": None,
        }
    ]

    exported = client.get(
        f"{API}/studio/templates/{template_id}/export?scope=draft",
        headers=_headers(ctx, "studio_teacher"),
    )
    assert exported.status_code == 200, exported.text
    names = _zip_names_and_contents(exported.content)
    assert names["assets/legacy.csv"] == b"legacy\n"
