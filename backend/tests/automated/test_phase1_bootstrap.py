"""Phase 1 regression tests for the supported migration/bootstrap entrypoint."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
SEED_PATH = REPO_ROOT / "scripts" / "seed-basic-environment-mysql.py"
BOOTSTRAP_PATH = REPO_ROOT / "scripts" / "bootstrap_database.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
COMPOSE_PATH = REPO_ROOT / "docker-compose.prod.yml"
DEV_UP_PATH = REPO_ROOT / "scripts" / "dev-up.sh"
README_PATH = REPO_ROOT / "README.md"


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("phase1_seed", SEED_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_production_bootstrap_requires_basic_digest_before_database_work():
    module = _load_seed_module()

    with pytest.raises(ValueError, match="DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST"):
        module.resolve_image_digest(environment="production", raw_digest="")


@pytest.mark.parametrize("placeholder", ["0", "1"])
def test_production_bootstrap_rejects_placeholder_basic_digest(placeholder: str):
    module = _load_seed_module()

    with pytest.raises(ValueError, match="占位"):
        module.resolve_image_digest(
            environment="production", raw_digest=f"sha256:{placeholder * 64}"
        )


def test_disposable_bootstrap_generates_explicit_digest_not_accepted_as_production():
    module = _load_seed_module()

    disposable = module.resolve_image_digest(
        environment="development", raw_digest=""
    )

    assert module.is_disposable_digest(disposable)
    with pytest.raises(ValueError, match="disposable"):
        module.resolve_image_digest(
            environment="production", raw_digest=disposable
        )


def test_seed_script_uses_shared_fail_closed_digest_policy():
    seed_source = SEED_PATH.read_text(encoding="utf-8")

    assert "resolve_image_digest" in seed_source
    assert "is_disposable_digest" in seed_source


def test_docker_smoke_is_explicitly_disposable_and_uses_bootstrap_entrypoint():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    smoke = workflow.split("  docker-smoke:", 1)[1]

    assert "DAI_ENVIRONMENT: development" in smoke
    assert "DAI_MIGRATION_MODE: disposable" in smoke
    assert "DAI_ENVIRONMENT: production" not in smoke
    assert "bootstrap_database.py" in smoke
    assert "alembic upgrade b4c5d6e7f890" not in smoke
    assert "alembic upgrade head" not in smoke


def test_compose_forwards_production_basic_digest_to_bootstrap_container():
    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    migrate = compose.split("  migrate:", 1)[1].split("  api:", 1)[0]

    assert "DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST:" in migrate


def _bootstrap_env(db_path: Path, *, environment: str = "development") -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "DAI_DATABASE_URL": f"sqlite:///{db_path}",
            "DAI_ENVIRONMENT": environment,
            "DAI_MIGRATION_MODE": "production" if environment == "production" else "disposable",
            "DAI_SECRET_KEY": "phase1-bootstrap-test-secret",
            "PYTHONPATH": str(BACKEND_ROOT),
        }
    )
    return env


def test_bootstrap_callers_use_one_supported_entrypoint():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    dev_up = DEV_UP_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")

    for source in (workflow, compose, dev_up, readme):
        assert "bootstrap_database.py" in source
        assert "alembic upgrade b4c5d6e7f890" not in source
        assert "alembic upgrade head" not in source


def test_dev_up_forces_disposable_environment_for_every_child_process():
    """开发入口不能把 backend/.env 的 production 模式带入 disposable bootstrap。"""
    dev_up = DEV_UP_PATH.read_text(encoding="utf-8")

    assert "export DAI_ENVIRONMENT=development" in dev_up
    assert "export DAI_MIGRATION_MODE=disposable" in dev_up
    assert "disposable 两阶段迁移" in dev_up


def test_empty_sqlite_bootstrap_reaches_head_and_repeats_without_work(tmp_path: Path):
    db_path = tmp_path / "bootstrap.db"
    env = _bootstrap_env(db_path)

    first = subprocess.run(
        [sys.executable, str(BOOTSTRAP_PATH)],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert first.returncode == 0, f"首次 bootstrap 失败:\n{first.stdout}\n{first.stderr}"
    assert "b4c5d6e7f890" in first.stdout

    second = subprocess.run(
        [sys.executable, str(BOOTSTRAP_PATH)],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert second.returncode == 0, f"重复 bootstrap 失败:\n{second.stdout}\n{second.stderr}"
    assert "无需迁移" in second.stdout


def test_production_bootstrap_rejects_missing_digest_before_database_connection(tmp_path: Path):
    db_path = tmp_path / "production-bootstrap.db"
    env = _bootstrap_env(db_path, environment="production")

    result = subprocess.run(
        [sys.executable, str(BOOTSTRAP_PATH)],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST" in result.stderr
    assert not db_path.exists()
