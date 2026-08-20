"""Service-level tests for the V2 profile/draft lifecycle."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    EnvironmentBuildJob,
    EnvironmentDraft,
    EnvironmentProfile,
    EnvironmentVersion,
    PackageCatalog,
    ProfileVersionPackage,
)
from app.services import environment_editor_service as service
from app.services.environment_service import (
    require_runnable_version,
    require_teacher_selectable_version,
    resolve_run_image_ref,
)


pytestmark = pytest.mark.no_auto_env_seed


def _detail(exc: HTTPException) -> dict:
    assert isinstance(exc.detail, dict)
    return exc.detail


def _settings(test_settings):
    test_settings.environment_editor_v2_enabled = True
    return test_settings


def _package(db, package_id: int, name: str, version: str) -> PackageCatalog:
    package = PackageCatalog(
        id=package_id,
        normalized_name=name,
        pip_name=name,
        locked_version=version,
        import_names=[name],
        category_tags=[],
        source_key="pypi",
    )
    db.add(package)
    db.flush()
    return package


def test_create_profile_creates_initial_draft_with_defaults(db_session_factory, test_settings):
    with db_session_factory() as db:
        profile, draft = service.create_profile_with_draft(
            db,
            display_name="数据分析环境",
            description="用于数据处理",
            slug=None,
            actor_id=None,
            settings=_settings(test_settings),
        )

        assert profile.slug.startswith("env-")
        assert profile.current_version_id is None
        assert draft.profile_id == profile.id
        assert draft.revision == 1
        assert draft.state == "editing"
        assert draft.python_version == "3.12"
        assert draft.minimum_memory_mb == 256
        assert draft.requested_spec["python_packages"] == []


def test_clone_current_version_uses_resolved_direct_versions(db_session_factory, test_settings):
    with db_session_factory() as db:
        profile = EnvironmentProfile(slug="data", display_name="Data", status="active")
        db.add(profile)
        db.flush()
        version = EnvironmentVersion(
            profile_id=profile.id,
            version_number=1,
            status="available",
            base_image_ref="python:3.12-slim@sha256:" + "a" * 64,
            image_digest="sha256:" + "b" * 64,
            python_version="3.12",
            minimum_memory_mb=512,
            manifest_sha256="c" * 64,
            requested_spec={
                "schema_version": 1,
                "python_packages": [{"name": "numpy", "version": None, "import_names": []}],
                "system_packages": [],
            },
            resolved_spec={
                "schema_version": 1,
                "direct_python_packages": [
                    {
                        "name": "numpy",
                        "requested_version": None,
                        "resolved_version": "2.1.3",
                        "import_names": ["numpy"],
                        "hashes": ["sha256:" + "d" * 64],
                    }
                ],
                "system_packages": [],
            },
        )
        db.add(version)
        db.flush()
        profile.current_version_id = version.id
        db.commit()

        draft = service.create_or_get_draft(db, profile.id, actor_id=None, settings=_settings(test_settings))

        assert draft.source_version_id == version.id
        assert draft.python_version == "3.12"
        assert draft.minimum_memory_mb == 512
        assert draft.requested_spec["python_packages"] == [
            {"name": "numpy", "version": "2.1.3", "import_names": ["numpy"]}
        ]


def test_save_draft_revision_conflict_and_active_build_guard(db_session_factory, test_settings):
    with db_session_factory() as db:
        profile, draft = service.create_profile_with_draft(
            db,
            display_name="Data",
            description=None,
            slug="data",
            actor_id=None,
            settings=_settings(test_settings),
        )
        with pytest.raises(HTTPException) as conflict:
            service.save_draft(
                db,
                profile.id,
                revision=99,
                python_version="3.11",
                minimum_memory_mb=768,
                requested_spec={"schema_version": 1, "python_packages": [], "system_packages": []},
                actor_id=None,
            )
        assert _detail(conflict.value)["code"] == "DRAFT_REVISION_CONFLICT"

        draft.state = "building"
        db.commit()
        with pytest.raises(HTTPException) as active:
            service.save_draft(
                db,
                profile.id,
                revision=draft.revision,
                python_version="3.11",
                minimum_memory_mb=768,
                requested_spec={"schema_version": 1, "python_packages": [], "system_packages": []},
                actor_id=None,
            )
        assert _detail(active.value)["code"] == "DRAFT_BUILD_ACTIVE"


def test_build_creates_immutable_candidate_and_retries_without_new_version(
    db_session_factory, test_settings
):
    with db_session_factory() as db:
        profile, draft = service.create_profile_with_draft(
            db,
            display_name="Data",
            description=None,
            slug="data",
            actor_id=None,
            settings=_settings(test_settings),
        )
        package_spec = {
            "schema_version": 1,
            "python_packages": [{"name": "numpy", "version": None, "import_names": []}],
            "system_packages": [{"name": "ffmpeg", "version": None}],
        }
        draft = service.save_draft(
            db,
            profile.id,
            revision=draft.revision,
            python_version="3.11",
            minimum_memory_mb=768,
            requested_spec=package_spec,
            actor_id=None,
        )
        version, job = service.start_draft_build(db, profile.id, actor_id=None, settings=test_settings)
        assert version.status == "queued"
        assert version.python_version == "3.11"
        assert version.requested_spec["system_packages"][0]["name"] == "ffmpeg"
        assert job.phase == "queued"
        assert draft.revision == 2

        version.status = "failed"
        job.status = "failed"
        job.phase = "done"
        draft.state = "failed"
        draft.active_build_job_id = None
        db.commit()
        assert service.can_retry_build(db, job.id) is True

        retry_version, retry_job = service.retry_draft_build(
            db, job.id, actor_id=None, settings=test_settings
        )
        assert retry_version.id == version.id
        assert retry_job.retry_of_id == job.id
        assert retry_job.attempt_number == 2
        assert retry_version.status == "queued"
        assert db.scalar(select(EnvironmentVersion).where(EnvironmentVersion.id == version.id)).id == version.id


def test_unchanged_clone_cannot_create_a_new_version(db_session_factory, test_settings):
    with db_session_factory() as db:
        profile = EnvironmentProfile(slug="unchanged", display_name="Unchanged", status="active")
        db.add(profile)
        db.flush()
        version = EnvironmentVersion(
            profile_id=profile.id,
            version_number=1,
            status="available",
            base_image_ref="python:3.12-slim@sha256:" + "a" * 64,
            image_digest="sha256:" + "b" * 64,
            python_version="3.12",
            minimum_memory_mb=256,
            manifest_sha256="c" * 64,
            requested_spec={"schema_version": 1, "python_packages": [], "system_packages": []},
            resolved_spec={"direct_python_packages": [], "system_packages": []},
        )
        db.add(version)
        db.flush()
        profile.current_version_id = version.id
        db.commit()
        draft = service.create_or_get_draft(db, profile.id, actor_id=None, settings=_settings(test_settings))

        with pytest.raises(HTTPException) as exc:
            service.start_draft_build(db, profile.id, actor_id=None, settings=_settings(test_settings))
        assert _detail(exc.value)["code"] == "NO_ENVIRONMENT_CHANGES"
        assert draft.source_version_id == version.id


def test_editing_failed_candidate_requires_new_version_and_old_failure_is_not_retryable(
    db_session_factory, test_settings
):
    with db_session_factory() as db:
        profile, draft = service.create_profile_with_draft(
            db,
            display_name="Data",
            description=None,
            slug="data",
            actor_id=None,
            settings=_settings(test_settings),
        )
        version, job = service.start_draft_build(db, profile.id, actor_id=None, settings=test_settings)
        version.status = "failed"
        job.status = "failed"
        job.phase = "done"
        draft.state = "failed"
        draft.active_build_job_id = None
        db.commit()

        updated = service.save_draft(
            db,
            profile.id,
            revision=draft.revision,
            python_version="3.12",
            minimum_memory_mb=512,
            requested_spec={
                "schema_version": 1,
                "python_packages": [],
                "system_packages": [{"name": "ffmpeg", "version": None}],
            },
            actor_id=None,
        )
        assert updated.candidate_version_id is None
        assert service.can_retry_build(db, job.id) is False

        next_version, next_job = service.start_draft_build(db, profile.id, actor_id=None, settings=test_settings)
        assert next_version.id != version.id
        assert next_version.version_number == version.version_number + 1
        assert next_job.retry_of_id is None


def test_teacher_selection_and_historical_runtime_gates_are_separate(db_session_factory):
    with db_session_factory() as db:
        profile = EnvironmentProfile(slug="data", display_name="Data", status="active")
        db.add(profile)
        db.flush()
        old = EnvironmentVersion(
            profile_id=profile.id,
            version_number=1,
            status="available",
            base_image_ref="python:3.12-slim@sha256:" + "a" * 64,
            image_digest="sha256:" + "1" * 64,
            python_version="3.12",
            minimum_memory_mb=256,
            manifest_sha256="b" * 64,
        )
        current = EnvironmentVersion(
            profile_id=profile.id,
            version_number=2,
            status="available",
            base_image_ref="python:3.12-slim@sha256:" + "c" * 64,
            image_digest="sha256:" + "2" * 64,
            python_version="3.12",
            minimum_memory_mb=256,
            manifest_sha256="d" * 64,
        )
        db.add_all([old, current])
        db.flush()
        profile.current_version_id = current.id
        db.commit()

        with pytest.raises(HTTPException) as not_selectable:
            require_teacher_selectable_version(db, old.id)
        assert _detail(not_selectable.value)["code"] == "VERSION_NOT_AVAILABLE"
        assert require_runnable_version(db, old.id).id == old.id
        profile.status = "inactive"
        db.commit()
        assert resolve_run_image_ref(db, old.id) == old.image_digest


def test_publish_and_rollback_are_audited_and_remove_candidate_draft(
    db_session_factory, test_settings
):
    with db_session_factory() as db:
        profile, draft = service.create_profile_with_draft(
            db,
            display_name="Data",
            description=None,
            slug="data-publish",
            actor_id=None,
            settings=_settings(test_settings),
        )
        first, first_job = service.start_draft_build(
            db, profile.id, actor_id=None, settings=test_settings
        )
        first.status = "available"
        first.image_digest = "sha256:" + "1" * 64
        first.resolved_spec = {
            "schema_version": 1,
            "direct_python_packages": [],
            "system_packages": [],
        }
        first_job.status = "succeeded"
        draft.state = "ready"
        draft.active_build_job_id = None
        db.commit()

        publication = service.publish_version(
            db,
            profile.id,
            version_id=first.id,
            expected_current_version_id=None,
            actor_id=None,
        )
        assert publication.action == "publish"
        assert db.get(EnvironmentDraft, profile.id) is None
        assert db.get(EnvironmentProfile, profile.id).current_version_id == first.id

        second_draft = service.create_or_get_draft(
            db, profile.id, actor_id=None, settings=test_settings
        )
        second_draft = service.save_draft(
            db,
            profile.id,
            revision=second_draft.revision,
            python_version="3.12",
            minimum_memory_mb=512,
            requested_spec=second_draft.requested_spec,
            actor_id=None,
        )
        second, second_job = service.start_draft_build(
            db, profile.id, actor_id=None, settings=test_settings
        )
        second.status = "available"
        second.image_digest = "sha256:" + "2" * 64
        second.resolved_spec = {
            "schema_version": 1,
            "direct_python_packages": [],
            "system_packages": [],
        }
        second_job.status = "succeeded"
        second_draft.state = "ready"
        second_draft.active_build_job_id = None
        db.commit()
        service.publish_version(
            db,
            profile.id,
            version_id=second.id,
            expected_current_version_id=first.id,
            actor_id=None,
        )

        rollback = service.publish_version(
            db,
            profile.id,
            version_id=first.id,
            expected_current_version_id=second.id,
            actor_id=None,
        )
        assert rollback.action == "rollback"
        assert db.get(EnvironmentProfile, profile.id).current_version_id == first.id


def test_historical_teacher_summary_is_safe_and_works_for_archived_profile(
    db_session_factory,
):
    with db_session_factory() as db:
        profile = EnvironmentProfile(slug="legacy-summary", display_name="Legacy", status="inactive")
        db.add(profile)
        db.flush()
        version = EnvironmentVersion(
            profile_id=profile.id,
            version_number=1,
            status="available",
            base_image_ref="python:3.12-slim@sha256:" + "a" * 64,
            image_digest="sha256:" + "b" * 64,
            python_version="3.12",
            minimum_memory_mb=512,
            manifest_sha256="c" * 64,
            resolved_spec={
                "direct_python_packages": [
                    {"name": "numpy", "resolved_version": "2.1.3", "import_names": ["numpy"]}
                ],
                "system_packages": [{"name": "ffmpeg", "resolved_version": "7.0"}],
            },
        )
        db.add(version)
        db.commit()

        option = service.teacher_option_for_version(db, version.id)
        assert option.environment_version_id == version.id
        assert option.packages[0].locked_version == "2.1.3"
        assert option.system_packages[0].name == "ffmpeg"
        assert not hasattr(option, "image_digest")
