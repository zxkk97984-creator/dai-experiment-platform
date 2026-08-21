"""HTTP contract tests for the V2 environment editor."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import EnvironmentBuildJob, EnvironmentDraft, EnvironmentProfile, EnvironmentVersion
from conftest import auth_header, create_user, login


pytestmark = pytest.mark.no_auto_env_seed

API = "/api/v1/environments"


def _configure_healthy_builder(test_settings, redis_client, *, heartbeat=True):
    """Model the services that are present in the V2 API integration tests."""

    test_settings.env_registry_repository = "registry.example/dai-env"
    test_settings.env_registry_allow_anonymous = True
    test_settings.env_python_base_images = {
        version: f"python:{version}-slim-bookworm@sha256:{'0' * 64}"
        for version in ("3.10", "3.11", "3.12")
    }
    test_settings.env_apt_snapshot_sources = {
        version: [
            "deb http://snapshot.debian.org/archive/debian/20260801T000000Z bookworm main"
        ]
        for version in ("3.10", "3.11", "3.12")
    }
    if heartbeat:
        redis_client.set(
            test_settings.env_builder_heartbeat_key,
            '{"owner_id":"test-builder","updated_at":1}',
            ex=test_settings.env_builder_heartbeat_ttl_seconds,
        )


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


def test_create_profile_rejects_duplicate_display_name(client, db_session_factory, test_settings):
    headers = _admin(client, db_session_factory, test_settings, "v2-api-admin-duplicate-name")
    first = client.post(
        f"{API}/profiles",
        headers=headers,
        json={"display_name": "重复环境", "description": "首次创建"},
    )
    assert first.status_code == 201, first.text
    assert first.json()["display_name"] == "重复环境"

    duplicate = client.post(
        f"{API}/profiles",
        headers=headers,
        json={"display_name": " 重复环境 ", "description": "再次创建"},
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["detail"]["code"] == "PROFILE_DISPLAY_NAME_CONFLICT"


def test_update_profile_rejects_duplicate_display_name(client, db_session_factory, test_settings):
    headers = _admin(client, db_session_factory, test_settings, "v2-api-admin-duplicate-update-name")
    first = client.post(
        f"{API}/profiles",
        headers=headers,
        json={"display_name": "已有环境", "description": "首次创建"},
    ).json()
    second = client.post(
        f"{API}/profiles",
        headers=headers,
        json={"display_name": "待改名环境", "description": "第二个环境"},
    ).json()

    duplicate = client.patch(
        f"{API}/profiles/{second['id']}",
        headers=headers,
        json={"display_name": "已有环境"},
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["detail"]["code"] == "PROFILE_DISPLAY_NAME_CONFLICT"
    unchanged = client.get(f"{API}/profiles/{second['id']}", headers=headers)
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["display_name"] == "待改名环境"


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
    _configure_healthy_builder(test_settings, redis_client)
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


def test_build_readiness_reports_worker_heartbeat_and_build_gate(
    client, db_session_factory, test_settings, redis_client
):
    _configure_healthy_builder(test_settings, redis_client, heartbeat=False)
    headers = _admin(client, db_session_factory, test_settings, "v2-api-admin-readiness")

    missing = client.get(f"{API}/build-readiness", headers=headers)
    assert missing.status_code == 200
    assert missing.json()["ready"] is False
    assert missing.json()["checks"]["worker"]["code"] == "BUILD_WORKER_NOT_READY"

    _configure_healthy_builder(test_settings, redis_client, heartbeat=True)
    ready = client.get(f"{API}/build-readiness", headers=headers)
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    assert ready.json()["checks"]["worker"]["status"] == "healthy"


def test_draft_build_does_not_create_job_without_worker_heartbeat(
    client, db_session_factory, test_settings, redis_client
):
    _configure_healthy_builder(test_settings, redis_client, heartbeat=False)
    headers = _admin(client, db_session_factory, test_settings, "v2-api-admin-no-worker")
    created = client.post(
        f"{API}/profiles",
        headers=headers,
        json={"display_name": "No Worker", "slug": "no-worker"},
    ).json()

    blocked = client.post(f"{API}/profiles/{created['id']}/draft/builds", headers=headers)
    assert blocked.status_code == 503
    assert blocked.json()["detail"]["code"] == "BUILD_SERVICE_UNAVAILABLE"
    assert "worker" in blocked.json()["detail"]["fields"]["checks"]
    with db_session_factory() as db:
        assert db.scalars(select(EnvironmentBuildJob)).all() == []


def test_publish_requires_expected_current_version_field(client, db_session_factory, test_settings):
    headers = _admin(client, db_session_factory, test_settings, "v2-api-publish-token")
    response = client.post(
        f"{API}/profiles/1/publications",
        headers=headers,
        json={"environment_version_id": 1},
    )
    assert response.status_code == 422
