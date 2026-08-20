"""HTTP contract tests for the V2 environment editor."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import EnvironmentBuildJob, EnvironmentDraft, EnvironmentProfile, EnvironmentVersion
from conftest import auth_header, create_user, login


pytestmark = pytest.mark.no_auto_env_seed

API = "/api/v1/environments"


def _admin(client, db_session_factory, test_settings, username="v2-api-admin"):
    test_settings.environment_editor_v2_enabled = True
    create_user(db_session_factory, username, "admin")
    token, _ = login(client, username)
    return auth_header(token)


def test_create_profile_enters_editor_with_default_draft(client, db_session_factory, test_settings):
    headers = _admin(client, db_session_factory, test_settings)
    response = client.post(
        f"{API}/profiles",
        headers=headers,
        json={"display_name": "数据分析环境", "description": "Pandas 作业"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["slug"].startswith("env-")
    assert body["draft"]["python_version"] == "3.12"
    assert body["draft"]["minimum_memory_mb"] == 256
    assert body["capabilities"]["can_edit_draft"] is True
    assert body["capabilities"]["can_abandon_draft"] is True


def test_draft_save_revision_conflict_and_editor_options(client, db_session_factory, test_settings):
    headers = _admin(client, db_session_factory, test_settings, "v2-api-admin-conflict")
    created = client.post(
        f"{API}/profiles",
        headers=headers,
        json={"display_name": "Data", "slug": "data-v2"},
    ).json()
    profile_id = created["id"]
    draft = client.get(f"{API}/profiles/{profile_id}/draft", headers=headers).json()
    body = {
        "revision": draft["revision"],
        "python_version": "3.11",
        "minimum_memory_mb": 768,
        "requested_spec": {
            "schema_version": 1,
            "python_packages": [{"name": "numpy", "version": None, "import_names": []}],
            "system_packages": [{"name": "ffmpeg", "version": None}],
        },
    }
    saved = client.put(f"{API}/profiles/{profile_id}/draft", headers=headers, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == draft["revision"] + 1

    conflict = client.put(f"{API}/profiles/{profile_id}/draft", headers=headers, json=body)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "DRAFT_REVISION_CONFLICT"
    assert conflict.json()["detail"]["retryable"] is False

    options = client.get(f"{API}/editor-options", headers=headers)
    assert options.status_code == 200
    assert options.json()["python_versions"] == ["3.10", "3.11", "3.12"]
    assert options.json()["max_python_packages"] == 100


def test_build_is_not_teacher_selectable_until_publish(client, db_session_factory, test_settings, redis_client):
    headers = _admin(client, db_session_factory, test_settings, "v2-api-admin-build")
    created = client.post(
        f"{API}/profiles",
        headers=headers,
        json={"display_name": "Buildable", "slug": "buildable"},
    ).json()
    profile_id = created["id"]
    build = client.post(f"{API}/profiles/{profile_id}/draft/builds", headers=headers)
    assert build.status_code == 202, build.text
    job_id = build.json()["id"]
    with db_session_factory() as db:
        version = db.scalar(select(EnvironmentVersion).where(EnvironmentVersion.id == build.json()["environment_version_id"]))
        version.status = "available"
        version.image_digest = "sha256:" + "a" * 64
        version.resolved_spec = {
            "schema_version": 1,
            "direct_python_packages": [],
            "system_packages": [],
        }
        job = db.get(EnvironmentBuildJob, job_id)
        job.status = "succeeded"
        job.phase = "done"
        draft = db.get(EnvironmentDraft, profile_id)
        draft.state = "ready"
        draft.active_build_job_id = None
        db.commit()

    before = client.get(f"{API}/available", headers=headers)
    assert before.status_code == 200
    assert before.json() == []

    publish = client.post(
        f"{API}/profiles/{profile_id}/publications",
        headers=headers,
        json={"environment_version_id": version.id, "expected_current_version_id": None},
    )
    assert publish.status_code == 201, publish.text
    assert publish.json()["action"] == "publish"

    after = client.get(f"{API}/available", headers=headers)
    assert after.status_code == 200
    assert len(after.json()) == 1
    assert after.json()[0]["environment_version_id"] == version.id
    assert "image_digest" not in after.json()[0]
    assert "system_packages" in after.json()[0]


def test_publish_requires_expected_current_version_field(client, db_session_factory, test_settings):
    headers = _admin(client, db_session_factory, test_settings, "v2-api-publish-token")
    response = client.post(
        f"{API}/profiles/1/publications",
        headers=headers,
        json={"environment_version_id": 1},
    )
    assert response.status_code == 422
