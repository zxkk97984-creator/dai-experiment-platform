"""Package metadata lookup for the V2 environment editor.

The editor treats search as a convenience only: the worker remains the
authoritative resolver.  This module therefore returns a cacheable, public
candidate shape and never persists a source URL or credentials.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import uuid
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.services.import_policy import normalize_pip_name
from app.services.environment_spec import validate_apt_name


def apt_candidate_cache_key(python_version: str, normalized_name: str) -> str:
    return f"environment:v2:apt-candidate:{python_version}:{normalized_name}"


def get_cached_apt_candidate(redis_client, *, python_version: str, normalized_name: str) -> dict | None:
    """Read worker-produced apt metadata without making the request path run apt."""

    try:
        raw = redis_client.get(apt_candidate_cache_key(python_version, normalized_name))
        if not raw:
            return None
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    except Exception:  # noqa: BLE001 - Redis is an optional search cache
        return None
    if not isinstance(value, dict) or value.get("manager") != "apt":
        return None
    return value


def parse_apt_dumpavail(output: str, deny_patterns: list[str] | None = None) -> list[dict]:
    """Convert ``apt-cache dumpavail`` stanzas to public cache entries."""

    records: dict[str, dict] = {}
    current: dict[str, str] = {}

    def flush() -> None:
        name = current.get("Package", "").split(":", 1)[0]
        if not name:
            current.clear()
            return
        try:
            validate_apt_name(name)
        except ValueError:
            current.clear()
            return
        item = records.setdefault(
            name,
            {
                "manager": "apt",
                "name": name,
                "versions": [],
                "description": current.get("Description", ""),
                "compatible": True,
                "denied": False,
                "indexing": False,
            },
        )
        version = current.get("Version")
        if version and version not in item["versions"]:
            item["versions"].append(version)
        if not item["description"] and current.get("Description"):
            item["description"] = current["Description"]
        current.clear()

    for line in output.splitlines():
        if not line.strip():
            flush()
            continue
        if line.startswith("Package:"):
            if current.get("Package"):
                flush()
            current["Package"] = line.split(":", 1)[1].strip()
        elif line.startswith("Version:"):
            current["Version"] = line.split(":", 1)[1].strip()
        elif line.startswith("Description:"):
            current["Description"] = line.split(":", 1)[1].strip()
    flush()

    patterns = deny_patterns or []
    for item in records.values():
        item["versions"].sort(reverse=True)
        if any(re.fullmatch(pattern, item["name"]) for pattern in patterns):
            item["denied"] = True
            item["deny_reason"] = "平台安全策略禁止安装"
    return sorted(records.values(), key=lambda item: item["name"])


def refresh_apt_candidate_cache(
    redis_client,
    settings,
    *,
    python_version: str,
    timeout_seconds: int = 120,
) -> int:
    """Refresh one Python-version-specific apt candidate cache in the Worker."""

    base_image = settings.env_python_base_images.get(python_version)
    sources = settings.env_apt_snapshot_sources.get(python_version)
    if not base_image or not sources:
        return 0

    from app.services.environment_builder_v2 import (
        _docker_proxy_args,
        _docker_network_arg,
        _safe_apt_sources,
        _subprocess_env,
    )

    safe_sources = _safe_apt_sources(sources)
    source_script = (
        "rm -f /etc/apt/sources.list /etc/apt/sources.list.d/* && printf '%s\\n' "
        + " ".join(shlex.quote(source) for source in safe_sources)
        + " > /etc/apt/sources.list.d/dai-snapshot.list && "
    )
    container_name = f"dai-v2-apt-index-{uuid.uuid4().hex[:20]}"
    command = [
        "docker", "run", "--rm", "--name", container_name,
        "--network", _docker_network_arg(settings),
        *_docker_proxy_args(settings),
        base_image, "sh", "-c", source_script + "apt-get update -qq && apt-cache dumpavail",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=_subprocess_env(settings),
        )
    except subprocess.TimeoutExpired:
        # Killing the Docker CLI does not necessarily stop the daemon-side
        # container.  Remove the named child explicitly or repeated indexing
        # timeouts can leak containers and hold apt resources indefinitely.
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                text=True,
                timeout=30,
                env=_subprocess_env(settings),
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise
    if result.returncode != 0:
        raise RuntimeError("apt 索引刷新失败")
    records = parse_apt_dumpavail(result.stdout, settings.env_apt_deny_patterns)
    for candidate in records:
        redis_client.setex(
            apt_candidate_cache_key(python_version, candidate["name"]),
            6 * 60 * 60,
            json.dumps(candidate, ensure_ascii=False),
        )
    return len(records)


class _SimpleVersionParser(HTMLParser):
    def __init__(self, project: str):
        super().__init__()
        self.project = project
        self.versions: set[str] = set()

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href", "")
        if "#" in href:
            href = href.split("#", 1)[0]
        value = href.rstrip("/").rsplit("/", 1)[-1]
        prefix = f"{self.project}-"
        if value.startswith(prefix):
            remainder = re.sub(r"\.(?:tar\.gz|zip|whl)$", "", value[len(prefix) :])
            candidate = remainder.split("-", 1)[0]
            if re.fullmatch(r"[0-9][A-Za-z0-9.!+~_]*", candidate):
                self.versions.add(candidate)


def _safe_index_url(index_url: str | None) -> str:
    value = (index_url or "https://pypi.org/simple").strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Python 包源配置无效")
    # Private credentials belong in the worker's secret mechanism, never in a
    # search request URL or a cached result.  The first version has no private
    # package repository support, so fail closed if credentials are embedded.
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Python 包源不能在 URL 中携带凭据")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _version_sort_key(value: str):
    try:
        from packaging.version import Version

        parsed = Version(value)
        return (0, parsed, value)
    except Exception:  # noqa: BLE001 - malformed upstream links are ignored later
        return (1, value, value)


def search_pip_candidates(
    *,
    query: str,
    python_version: str,
    index_url: str | None,
    timeout_seconds: float = 3.0,
) -> dict:
    """Search one exact PEP 503 project name.

    Fuzzy search is intentionally served by the local catalog.  A valid full
    project name may be checked against the platform Simple API, with a short
    timeout and no credential-bearing URL in the returned payload.
    """

    normalized = normalize_pip_name(query)
    source = _safe_index_url(index_url)
    response = httpx.get(
        f"{source}/{normalized}/",
        headers={"Accept": "text/html, application/vnd.pypi.simple.v1+json"},
        timeout=timeout_seconds,
        follow_redirects=True,
    )
    if response.status_code == 404:
        return {
            "manager": "pip",
            "name": normalized,
            "versions": [],
            "compatible": False,
            "denied": False,
            "indexing": False,
        }
    response.raise_for_status()

    versions: set[str] = set()
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type:
        try:
            payload = response.json()
            for file in payload.get("files", []):
                filename = str(file.get("filename", ""))
                # Simple JSON file names are parsed conservatively; the final
                # pip resolver still decides wheel/Python compatibility.
                stem = filename.rsplit("-", 4)
                if len(stem) >= 5:
                    versions.add(stem[1])
        except (TypeError, ValueError, json.JSONDecodeError):
            versions.clear()
    if not versions:
        parser = _SimpleVersionParser(normalized)
        parser.feed(response.text)
        versions = parser.versions

    return {
        "manager": "pip",
        "name": normalized,
        "versions": sorted(versions, key=_version_sort_key, reverse=True),
        "compatible": None,
        "denied": False,
        "indexing": False,
    }
