"""Pure and mocked-worker tests for the V2 resolver/build pipeline."""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import EnvironmentBuildJob, EnvironmentDraft, EnvironmentProfile, EnvironmentVersion
from app.services.environment_builder_v2 import (
    V2BuildResult,
    _docker_proxy_args,
    _validate_image,
    canonical_v2_manifest,
    render_v2_dockerfile,
)
from app.services.environment_editor_service import start_draft_build
from app.worker import environment_builder_worker as worker


pytestmark = pytest.mark.no_auto_env_seed


def _v2_settings(test_settings):
    test_settings.environment_editor_v2_enabled = True
    test_settings.env_python_base_images = {
        "3.10": "python:3.10-slim-bookworm@sha256:" + "0" * 64,
        "3.11": "python:3.11-slim-bookworm@sha256:" + "1" * 64,
        "3.12": "python:3.12-slim-bookworm@sha256:" + "2" * 64,
    }
    return test_settings


def test_explicit_proxy_is_passed_to_networked_v2_containers(test_settings):
    settings = _v2_settings(test_settings)
    settings.env_build_http_proxy = "http://proxy.example:8080"
    assert _docker_proxy_args(settings) == [
        "-e", "HTTP_PROXY=http://proxy.example:8080",
        "-e", "HTTPS_PROXY=http://proxy.example:8080",
        "-e", "http_proxy=http://proxy.example:8080",
        "-e", "https_proxy=http://proxy.example:8080",
    ]
    settings.env_build_http_proxy = None
    assert _docker_proxy_args(settings) == []


def test_v2_manifest_and_dockerfile_are_canonical_and_safe(test_settings):
    settings = _v2_settings(test_settings)
    spec = {
        "schema_version": 1,
        "python_packages": [
            {"name": "numpy", "version": None, "import_names": []},
            {"name": "pandas", "version": "2.2.3", "import_names": ["pandas"]},
        ],
        "system_packages": [{"name": "ffmpeg", "version": None}],
    }
    manifest_a = canonical_v2_manifest(
        base_image_ref=settings.env_python_base_images["3.12"],
        python_version="3.12",
        minimum_memory_mb=256,
        requested_spec=spec,
        settings=settings,
    )
    manifest_b = canonical_v2_manifest(
        base_image_ref=settings.env_python_base_images["3.12"],
        python_version="3.12",
        minimum_memory_mb=256,
        requested_spec={**spec, "python_packages": list(reversed(spec["python_packages"]))},
        settings=settings,
    )
    assert manifest_a["manifest_sha256"] == manifest_b["manifest_sha256"]
    dockerfile = render_v2_dockerfile(manifest_a, pip_lock=[{"name": "pandas", "version": "2.2.3", "hashes": ["sha256:" + "a" * 64]}])
    assert "FROM python:3.12-slim-bookworm@sha256:" in dockerfile
    assert "--no-install-recommends" in dockerfile
    assert "--require-hashes" in dockerfile
    assert "pandas==2.2.3" not in dockerfile
    assert "RUN echo" not in dockerfile  # no user-provided shell content is accepted


def test_v2_validation_script_is_valid_python(monkeypatch, test_settings):
    settings = _v2_settings(test_settings)
    manifest = canonical_v2_manifest(
        base_image_ref=settings.env_python_base_images["3.12"],
        python_version="3.12",
        minimum_memory_mb=256,
        requested_spec={
            "schema_version": 1,
            "python_packages": [],
            "system_packages": [{"name": "ffmpeg", "version": None}],
        },
        settings=settings,
    )
    calls = []
    report = {"imports": ["ipykernel", "pytest"], "pip_check": {"ok": True}, "apt": []}
    encoded = base64.b64encode(json.dumps(report).encode()).decode()

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1] == "run":
            return SimpleNamespace(returncode=0, stdout=f"DAI_VALIDATION_BASE64={encoded}\n", stderr="")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"Id": "sha256:" + "a" * 64, "Size": 1234}),
            stderr="",
        )

    monkeypatch.setattr("app.services.environment_builder_v2.subprocess.run", fake_run)
    _validate_image("dai-env:test", manifest, settings, timeout=5)
    validation_script = calls[0][-1]
    compile(validation_script, "<v2-validation-container>", "exec")
    assert "dpkg-query" in validation_script
    # The generated program is Python, not JSON.  A JSON ``null`` in the
    # apt request snapshot compiles but raises NameError only inside Docker.
    assert "'version': None" in validation_script
    assert "'version': null" not in validation_script


def test_v2_worker_records_phases_and_releases_draft(db_session_factory, test_settings, monkeypatch):
    settings = _v2_settings(test_settings)
    with db_session_factory() as db:
        profile = EnvironmentProfile(slug="data", display_name="Data", status="active")
        db.add(profile)
        db.flush()
        draft = EnvironmentDraft(
            profile_id=profile.id,
            revision=1,
            state="editing",
            python_version="3.12",
            minimum_memory_mb=256,
            requested_spec={"schema_version": 1, "python_packages": [], "system_packages": []},
        )
        db.add(draft)
        db.commit()
        version, job = start_draft_build(db, profile.id, actor_id=None, settings=settings)
        assert worker.claim_build_job(db, job.id, "worker-v2", worker.utc_now()) is True

        phases: list[str] = []

        def fake_build(*args, **kwargs):
            for phase in ("preflight", "resolving_system", "resolving_python", "building", "validating", "finalizing"):
                phases.append(phase)
                kwargs["on_phase"](phase)
            return V2BuildResult(
                image_digest="sha256:" + "f" * 64,
                image_size_bytes=1234,
                resolved_spec={
                    "schema_version": 1,
                    "resolution_quality": "resolved",
                    "direct_python_packages": [],
                    "python_lock": [],
                    "system_packages": [],
                    "import_names": ["ipykernel", "pytest"],
                    "pip_check": {"ok": True},
                    "lock_sha256": "a" * 64,
                },
                result_summary={"image_size_bytes": 1234, "warnings": []},
                dockerfile_sha256="b" * 64,
            )

        monkeypatch.setattr("app.worker.environment_builder_worker.execute_v2_build", fake_build)
        result = worker.process_v2_build(db, settings, "worker-v2", job.id)
        assert result == "succeeded"
        db.expire_all()
        version = db.get(EnvironmentVersion, version.id)
        job = db.get(EnvironmentBuildJob, job.id)
        draft = db.get(EnvironmentDraft, profile.id)
        assert version.status == "available"
        assert version.resolved_spec["resolution_quality"] == "resolved"
        assert job.phase == "done"
        assert job.result_summary["image_size_bytes"] == 1234
        assert draft.state == "ready"
        assert draft.active_build_job_id is None
