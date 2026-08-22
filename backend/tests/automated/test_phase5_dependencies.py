"""Phase 5 production-image dependency boundary regressions."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"
DEV_ONLY = {"pytest", "fakeredis", "moto", "ruff", "radon"}


def _package_names(path: Path) -> set[str]:
    names = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        names.add(line.split("[", 1)[0].split("==", 1)[0].lower())
    return names


def test_production_requirements_exclude_test_and_audit_tools():
    runtime = _package_names(BACKEND / "requirements.txt")
    development = _package_names(BACKEND / "requirements-dev.txt")

    assert runtime.isdisjoint(DEV_ONLY)
    assert DEV_ONLY <= development


def test_ci_installs_complete_backend_test_requirements():
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "pip install -r requirements-dev.txt" in workflow
    assert "pip install pytest fakeredis" not in workflow


def test_backend_image_installs_runtime_requirements_only():
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY requirements-dev.txt" not in dockerfile
    assert "pip install --no-cache-dir -r requirements.txt" in dockerfile
