"""Opt-in real Docker smoke tests for the fail-closed Judge sandbox."""
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import Settings
from app.worker.judge_worker import _run_docker_pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("DAI_RUN_DOCKER_SMOKE") != "1",
    reason="set DAI_RUN_DOCKER_SMOKE=1 to run real Docker Judge smoke tests",
)


def test_real_judge_container_runs_hidden_test():
    settings = Settings()
    with tempfile.TemporaryDirectory(prefix="dai-judge-smoke-") as temp_dir:
        workdir = Path(temp_dir)
        (workdir / "user_code.py").write_text(
            "def add(a, b):\n    return a + b\n",
            encoding="utf-8",
        )
        (workdir / "test_user_code.py").write_text(
            "from user_code import add\n\n"
            "def test_add():\n"
            "    assert add(20, 22) == 42\n",
            encoding="utf-8",
        )

        stdout, stderr, returncode, _elapsed = _run_docker_pytest(
            workdir,
            settings,
            timeout_seconds=5,
            memory_limit_mb=128,
        )

    assert returncode == 0, f"{stdout}\n{stderr}"
    assert "passed" in stdout


def test_real_judge_timeout_leaves_no_container():
    settings = Settings()
    container_name = "dai-judge-smoke-timeout"

    with tempfile.TemporaryDirectory(prefix="dai-judge-timeout-") as temp_dir:
        workdir = Path(temp_dir)
        (workdir / "test_user_code.py").write_text(
            "while True:\n    pass\n",
            encoding="utf-8",
        )

        with patch("app.worker.judge_worker.secrets.token_hex", return_value="smoke-timeout"):
            _stdout, _stderr, returncode, _elapsed = _run_docker_pytest(
                workdir,
                settings,
                timeout_seconds=1,
                memory_limit_mb=128,
            )

    assert returncode == 124
    inspect = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"name=^{container_name}$"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert inspect.stdout.strip() == ""
