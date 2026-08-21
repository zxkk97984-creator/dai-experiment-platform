"""Pure and mocked-worker tests for the V2 resolver/build pipeline."""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import EnvironmentBuildJob, EnvironmentDraft, EnvironmentProfile, EnvironmentVersion
from app.services.environment_builder_v2 import (
    PublishedImage,
    V2BuildFailure,
    V2BuildResult,
    _publish_image_to_registry,
    _docker_proxy_args,
    _safe_apt_sources,
    _resolve_in_base_image,
    _load_registry_docker_config,
    _subprocess_env,
    registry_auth_check,
    _validate_preflight,
    _validate_image,
    canonical_lock_sha256,
    canonical_v2_manifest,
    is_pullable_registry_reference,
    render_v2_dockerfile,
)
from app.services.environment_editor_service import start_draft_build
from app.worker import environment_builder_worker as worker


pytestmark = pytest.mark.no_auto_env_seed


def _v2_settings(test_settings):
    test_settings.environment_editor_v2_enabled = True
    # Unit tests use mocked Registry calls; production defaults remain
    # fail-closed and require the Docker config Secret.
    test_settings.env_registry_allow_anonymous = True
    test_settings.env_python_base_images = {
        "3.10": "python:3.10-slim-bookworm@sha256:" + "0" * 64,
        "3.11": "python:3.11-slim-bookworm@sha256:" + "1" * 64,
        "3.12": "python:3.12-slim-bookworm@sha256:" + "2" * 64,
    }
    return test_settings


def test_v2_preflight_requires_registry_for_real_build(monkeypatch, test_settings):
    settings = _v2_settings(test_settings)
    manifest = canonical_v2_manifest(
        base_image_ref=settings.env_python_base_images["3.12"],
        python_version="3.12",
        minimum_memory_mb=256,
        requested_spec={"schema_version": 1, "python_packages": [], "system_packages": []},
        settings=settings,
    )
    monkeypatch.setattr("app.services.environment_builder_v2.shutil.which", lambda name: "/usr/bin/docker")
    with pytest.raises(V2BuildFailure) as exc_info:
        _validate_preflight(manifest, settings)
    assert exc_info.value.code == "BUILD_SERVICE_UNAVAILABLE"
    assert exc_info.value.detail["dependency"] == "registry"


@pytest.mark.parametrize(
    "source",
    [
        "deb http://user:pass@snapshot.debian.org/archive/debian/20260801T000000Z bookworm main",
        "deb [trusted=yes] http://snapshot.debian.org/archive/debian/20260801T000000Z bookworm main",
        "deb https://mirror.example/archive/debian/20260801T000000Z bookworm main",
        "deb file:///tmp/debian bookworm main",
    ],
)
def test_apt_source_must_be_platform_snapshot_without_credentials(source):
    with pytest.raises(V2BuildFailure) as exc_info:
        _safe_apt_sources([source])
    assert exc_info.value.code == "BUILD_SERVICE_UNAVAILABLE"


def test_apt_denylist_covers_container_aliases(monkeypatch, test_settings):
    settings = _v2_settings(test_settings)
    settings.env_registry_repository = "registry.example/dai-env"
    settings.env_apt_snapshot_sources = {
        version: ["deb http://snapshot.debian.org/archive/debian/20260801T000000Z bookworm main"]
        for version in ("3.10", "3.11", "3.12")
    }
    manifest = canonical_v2_manifest(
        base_image_ref=settings.env_python_base_images["3.12"],
        python_version="3.12",
        minimum_memory_mb=256,
        requested_spec={
            "schema_version": 1,
            "python_packages": [],
            "system_packages": [{"name": "docker.io", "version": None}],
        },
        settings=settings,
    )
    monkeypatch.setattr("app.services.environment_builder_v2.shutil.which", lambda name: "/usr/bin/docker")
    with pytest.raises(V2BuildFailure) as exc_info:
        _validate_preflight(manifest, settings)
    assert exc_info.value.code == "APT_PACKAGE_DENIED"


def test_registry_publish_pushes_and_pull_verifies_digest(monkeypatch, test_settings):
    settings = _v2_settings(test_settings)
    settings.env_registry_repository = "registry.example/dai-env"
    manifest = {"manifest_sha256": "a" * 64}
    digest = "sha256:" + "b" * 64
    reference = f"{settings.env_registry_repository}@{digest}"
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] in (["docker", "tag"], ["docker", "push"]):
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"RepoDigests": [reference], "Size": 123}),
            stderr="",
        )

    monkeypatch.setattr("app.services.environment_builder_v2._run_capture", fake_run)
    published = _publish_image_to_registry("dai-env:local", manifest, settings, timeout=10)
    assert isinstance(published, PublishedImage)
    assert published.reference == reference
    assert published.tag == f"{settings.env_registry_repository}:v2-{'a' * 64}"
    assert is_pullable_registry_reference(published.reference)
    assert ["docker", "push", published.tag] in calls
    assert ["docker", "pull", published.reference] in calls


def test_persisted_lock_skips_resolution(monkeypatch, test_settings):
    settings = _v2_settings(test_settings)
    settings.env_registry_repository = "registry.example/dai-env"
    manifest = canonical_v2_manifest(
        base_image_ref=settings.env_python_base_images["3.12"],
        python_version="3.12",
        minimum_memory_mb=256,
        requested_spec={"schema_version": 1, "python_packages": [], "system_packages": []},
        settings=settings,
    )
    lock = [
        {"name": "ipykernel", "version": "6.29.5", "hashes": ["sha256:" + "c" * 64]},
        {"name": "pytest", "version": "8.3.4", "hashes": ["sha256:" + "d" * 64]},
    ]
    monkeypatch.setattr("app.services.environment_builder_v2._validate_preflight", lambda *args: None)
    monkeypatch.setattr(
        "app.services.environment_builder_v2._resolve_in_base_image",
        lambda *args, **kwargs: pytest.fail("persisted lock must avoid resolver"),
    )
    monkeypatch.setattr("app.services.environment_builder._load_kernel_runner", lambda: "print('runner')")
    monkeypatch.setattr("app.services.environment_builder_v2._run_docker_build", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.services.environment_builder_v2._validate_image",
        lambda *args, **kwargs: (
            {"imports": [], "pip_check": {"ok": True}, "apt": [], "direct_apt": [], "warnings": []},
            "sha256:" + "d" * 64,
            123,
        ),
    )
    monkeypatch.setattr(
        "app.services.environment_builder_v2._publish_image_to_registry",
        lambda *args, **kwargs: PublishedImage(
            reference="registry.example/dai-env@sha256:" + "e" * 64,
            tag="registry.example/dai-env:v2-" + "a" * 64,
            digest="sha256:" + "e" * 64,
            size_bytes=123,
        ),
    )
    result = __import__("app.services.environment_builder_v2", fromlist=["execute_v2_build"]).execute_v2_build(
        manifest, settings, pip_lock=lock
    )
    assert result.resolved_spec["lock_sha256"] == canonical_lock_sha256(lock)
    assert result.image_digest.startswith("registry.example/dai-env@sha256:")


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


def test_docker_subprocess_environment_isolated_from_host_proxy(test_settings, monkeypatch):
    settings = _v2_settings(test_settings)
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7890")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7890")
    env = _subprocess_env(settings)
    assert env["DOCKER_CONFIG"] == "/tmp/dai-v2-docker-config"
    assert "HTTP_PROXY" not in env
    assert "HTTPS_PROXY" not in env


def test_registry_config_secret_is_reduced_to_auths_only(test_settings, tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "auths": {"registry.example": {"auth": base64.b64encode(b"u:p").decode()}},
            }
        ),
        encoding="utf-8",
    )
    settings = _v2_settings(test_settings)
    settings.env_registry_allow_anonymous = False
    settings.env_registry_docker_config = str(config_file)
    assert _load_registry_docker_config(settings, required=True) == {
        "auths": {"registry.example": {"auth": base64.b64encode(b"u:p").decode()}},
    }
    assert registry_auth_check(settings)["status"] == "configured"


@pytest.mark.parametrize("forbidden", [{"credsStore": "desktop"}, {"proxies": {}}])
def test_registry_config_rejects_helpers_and_proxy_blocks(test_settings, tmp_path, forbidden):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"auths": {}, **forbidden}), encoding="utf-8")
    settings = _v2_settings(test_settings)
    settings.env_registry_allow_anonymous = False
    settings.env_registry_docker_config = str(config_file)
    with pytest.raises(V2BuildFailure) as exc_info:
        _load_registry_docker_config(settings, required=True)
    assert exc_info.value.detail["dependency"] == "registry_auth"


def test_resolver_source_failure_is_not_reported_as_missing_apt_package(monkeypatch, test_settings):
    settings = _v2_settings(test_settings)
    settings.env_registry_repository = "registry.example/dai-env"
    manifest = canonical_v2_manifest(
        base_image_ref=settings.env_python_base_images["3.12"],
        python_version="3.12",
        minimum_memory_mb=256,
        requested_spec={"schema_version": 1, "python_packages": [], "system_packages": []},
        settings=settings,
    )
    monkeypatch.setattr(
        "app.services.environment_builder_v2._run_capture",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="Could not connect to pypi.example:443 (Connection refused)",
        ),
    )
    with pytest.raises(V2BuildFailure) as exc_info:
        _resolve_in_base_image(manifest, settings, timeout=5)
    assert exc_info.value.code == "BUILD_SERVICE_UNAVAILABLE"


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
            lock = [
                {"name": "ipykernel", "version": "6.29.5", "hashes": ["sha256:" + "0" * 64]},
                {"name": "pytest", "version": "8.3.4", "hashes": ["sha256:" + "1" * 64]},
            ]
            kwargs["on_resolution_lock"](lock, canonical_lock_sha256(lock))
            return V2BuildResult(
                image_digest="registry.example/dai-env@sha256:" + "f" * 64,
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
        assert version.resolution_lock["python_lock"][0]["name"] == "ipykernel"
        assert version.resolution_lock_sha256 == canonical_lock_sha256(version.resolution_lock["python_lock"])
        assert job.phase == "done"
        assert job.result_summary["image_size_bytes"] == 1234
        assert draft.state == "ready"
        assert draft.active_build_job_id is None


def test_v2_claim_persists_mode_and_unique_lease_token(
    db_session_factory, test_settings
):
    settings = _v2_settings(test_settings)
    with db_session_factory() as db:
        profile = EnvironmentProfile(slug="lease", display_name="Lease", status="active")
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
        _version, job = start_draft_build(db, profile.id, actor_id=None, settings=settings)
        assert job.build_mode == "v2"
        assert job.lease_token is None

        assert worker.claim_build_job(db, job.id, "worker-a", worker.utc_now()) is True
        db.refresh(job)
        assert job.build_mode == "v2"
        assert job.lease_token
        assert len(job.lease_token) >= 32


def test_old_worker_cannot_finalize_after_lease_reclaimed(
    db_session_factory, test_settings, monkeypatch
):
    settings = _v2_settings(test_settings)
    with db_session_factory() as db_a:
        profile = EnvironmentProfile(slug="lease-reclaim", display_name="Lease", status="active")
        db_a.add(profile)
        db_a.flush()
        draft = EnvironmentDraft(
            profile_id=profile.id,
            revision=1,
            state="editing",
            python_version="3.12",
            minimum_memory_mb=256,
            requested_spec={"schema_version": 1, "python_packages": [], "system_packages": []},
        )
        db_a.add(draft)
        db_a.commit()
        version, job = start_draft_build(db_a, profile.id, actor_id=None, settings=settings)
        assert worker.claim_build_job(db_a, job.id, "worker-a", worker.utc_now()) is True
        old_token = job.lease_token

        with db_session_factory() as db_b:
            stale = db_b.get(EnvironmentBuildJob, job.id)
            stale.lease_until = worker.utc_now()
            db_b.commit()
            stats = worker.recover_stale_builds(db_b, settings, worker.utc_now())
            assert stats["requeued"] == 1
            assert worker.claim_build_job(db_b, job.id, "worker-b", worker.utc_now()) is True
            db_b.refresh(stale)
            assert stale.lease_token != old_token

        def fake_build(*args, **kwargs):
            return V2BuildResult(
                image_digest="registry.example/dai-env@sha256:" + "e" * 64,
                image_size_bytes=1234,
                resolved_spec={"schema_version": 1, "python_lock": [], "system_packages": [], "lock_sha256": "a" * 64},
                result_summary={"image_size_bytes": 1234},
                dockerfile_sha256="b" * 64,
            )

        monkeypatch.setattr("app.worker.environment_builder_worker.execute_v2_build", fake_build)
        result = worker.process_v2_build(db_a, settings, "worker-a", job.id)
        assert result in {"lease_lost", "building"}
        db_a.expire_all()
        assert db_a.get(EnvironmentVersion, version.id).status != "available"


def test_persisted_build_mode_wins_over_runtime_feature_flag(
    db_session_factory, test_settings, monkeypatch
):
    settings = _v2_settings(test_settings)
    with db_session_factory() as db:
        profile = EnvironmentProfile(slug="mode", display_name="Mode", status="active")
        db.add(profile)
        db.flush()
        db.add(
            EnvironmentDraft(
                profile_id=profile.id,
                revision=1,
                state="editing",
                python_version="3.12",
                minimum_memory_mb=256,
                requested_spec={"schema_version": 1, "python_packages": [], "system_packages": []},
            )
        )
        db.commit()
        _version, job = start_draft_build(db, profile.id, actor_id=None, settings=settings)
        assert worker.claim_build_job(db, job.id, "worker-v2", worker.utc_now()) is True

        settings.environment_editor_v2_enabled = False
        calls = []

        def fake_v2(*args, **kwargs):
            calls.append("v2")
            return "dispatched"

        monkeypatch.setattr(worker, "process_v2_build", fake_v2)
        assert worker.process_build(db, settings, "worker-v2", job.id) == "dispatched"
        assert calls == ["v2"]
