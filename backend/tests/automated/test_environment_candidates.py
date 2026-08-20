from __future__ import annotations

import subprocess

import pytest

from app.services.environment_candidates import (
    get_cached_apt_candidate,
    parse_apt_dumpavail,
    search_pip_candidates,
)


pytestmark = pytest.mark.no_auto_env_seed


class _Response:
    status_code = 200
    headers = {"content-type": "text/html"}
    text = """
    <html><body>
      <a href="/packages/numpy-2.1.3-cp312-cp312-manylinux.whl#sha256=1">numpy-2.1.3</a>
      <a href="/packages/numpy-2.1.2.tar.gz#sha256=2">numpy-2.1.2</a>
    </body></html>
    """

    def raise_for_status(self):
        return None


def test_simple_api_candidate_search_returns_versions_without_source_url(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return _Response()

    monkeypatch.setattr("app.services.environment_candidates.httpx.get", fake_get)
    result = search_pip_candidates(
        query="NumPy",
        python_version="3.12",
        index_url="https://packages.example/simple/",
    )

    assert result["name"] == "numpy"
    assert result["versions"] == ["2.1.3", "2.1.2"]
    assert "source" not in result
    assert calls[0][0] == "https://packages.example/simple/numpy/"


def test_candidate_search_rejects_credential_bearing_source(monkeypatch):
    with pytest.raises(ValueError, match="凭据"):
        search_pip_candidates(
            query="numpy",
            python_version="3.12",
            index_url="https://user:secret@example/simple",
        )


def test_apt_candidate_cache_is_read_without_exposing_cache_key_or_source():
    class _Redis:
        def get(self, key):
            assert key == "environment:v2:apt-candidate:3.12:ffmpeg"
            return '{"manager":"apt","name":"ffmpeg","versions":["7.0"],"indexing":false}'

    result = get_cached_apt_candidate(_Redis(), python_version="3.12", normalized_name="ffmpeg")
    assert result == {
        "manager": "apt",
        "name": "ffmpeg",
        "versions": ["7.0"],
        "indexing": False,
    }


def test_apt_dumpavail_parser_groups_versions_and_marks_denylist():
    result = parse_apt_dumpavail(
        """Package: ffmpeg
Version: 7.0
Description: multimedia framework

Package: ffmpeg
Version: 6.1
Description: older description

Package: sudo
Version: 1.0
Description: privilege tool
""",
        [r"^sudo$"]
    )

    assert result[0]["name"] == "ffmpeg"
    assert result[0]["versions"] == ["7.0", "6.1"]
    assert result[1]["denied"] is True
    assert result[1]["deny_reason"] == "平台安全策略禁止安装"


def test_apt_candidate_timeout_removes_daemon_container(monkeypatch):
    calls = []

    class _Settings:
        env_python_base_images = {"3.11": "python@sha256:" + "a" * 64}
        env_apt_snapshot_sources = {"3.11": ["deb http://snapshot.example/debian trixie main"]}
        env_apt_deny_patterns = []
        env_build_network_mode = "default"
        env_build_http_proxy = None

    class _Redis:
        def setex(self, *args):
            raise AssertionError("timeout must not write candidate cache")

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1] == "run":
            raise subprocess.TimeoutExpired(command, 1)
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("app.services.environment_candidates.subprocess.run", fake_run)
    with pytest.raises(subprocess.TimeoutExpired):
        from app.services.environment_candidates import refresh_apt_candidate_cache

        refresh_apt_candidate_cache(_Redis(), _Settings(), python_version="3.11", timeout_seconds=1)

    container_name = calls[0][4]
    assert calls[0][1:5] == ["run", "--rm", "--name", container_name]
    assert calls[1][:3] == ["docker", "rm", "-f"]
    assert calls[1][3] == container_name
