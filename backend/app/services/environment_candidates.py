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
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import InvalidSdistFilename, InvalidWheelFilename
from packaging.utils import parse_sdist_filename, parse_wheel_filename
from packaging.version import InvalidVersion, Version

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


def _python_requirement_allows(requires_python: str | None, python_version: str) -> bool:
    if not requires_python:
        return True
    try:
        return SpecifierSet(requires_python).contains(Version(python_version), prereleases=True)
    except (InvalidSpecifier, InvalidVersion, TypeError):
        # Invalid upstream metadata must not be advertised as installable.
        return False


def _wheel_supports_python(tags, python_version: str) -> bool:
    minor = python_version.replace(".", "")
    accepted = {"py3", f"py{minor}", f"cp{minor}", f"pp{minor}"}
    return any(
        str(tag.interpreter).lower() in accepted
        or str(tag.interpreter).lower().startswith(f"cp{minor}")
        or str(tag.interpreter).lower().startswith(f"pp{minor}")
        for tag in tags
    )


def _parse_distribution_filename(
    filename: str,
    project: str,
    python_version: str,
    requires_python: str | None = None,
) -> tuple[str, bool] | None:
    """Return a normalized version and Python compatibility for a file."""

    try:
        name, version, _build, tags = parse_wheel_filename(filename)
        if normalize_pip_name(str(name)) != project:
            return None
        compatible = _wheel_supports_python(tags, python_version) and _python_requirement_allows(
            requires_python, python_version
        )
        return str(version), compatible
    except (InvalidWheelFilename, ValueError):
        pass
    try:
        name, version = parse_sdist_filename(filename)
        if normalize_pip_name(str(name)) != project:
            return None
        return str(version), _python_requirement_allows(requires_python, python_version)
    except (InvalidSdistFilename, ValueError):
        return None


class _SimpleVersionParser(HTMLParser):
    def __init__(self, project: str, python_version: str):
        super().__init__()
        self.project = project
        self.python_version = python_version
        self.versions: dict[str, bool] = {}
        self.saw_project_file = False

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() != "a":
            return
        attributes = dict(attrs)
        href = attributes.get("href", "")
        if "#" in href:
            href = href.split("#", 1)[0]
        filename = href.rstrip("/").rsplit("/", 1)[-1]
        parsed = _parse_distribution_filename(
            filename,
            self.project,
            self.python_version,
            attributes.get("data-requires-python"),
        )
        if parsed is None:
            return
        self.saw_project_file = True
        version, compatible = parsed
        if compatible:
            self.versions[version] = True


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


def _safe_proxy_url(proxy_url: str | None) -> str | None:
    if not proxy_url:
        return None
    value = proxy_url.strip()
    parsed = urlsplit(value)
    if (
        any(character.isspace() for character in value)
        or parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Python 包源代理配置无效或包含凭据")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


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
    proxy_url: str | None = None,
) -> dict:
    """Search one exact PEP 503 project name.

    Fuzzy search is intentionally served by the local catalog.  A valid full
    project name may be checked against the platform Simple API, with a short
    timeout and no credential-bearing URL in the returned payload.
    """

    normalized = normalize_pip_name(query)
    source = _safe_index_url(index_url)
    proxy = _safe_proxy_url(proxy_url)
    response = httpx.get(
        f"{source}/{normalized}/",
        headers={"Accept": "text/html, application/vnd.pypi.simple.v1+json"},
        timeout=timeout_seconds,
        follow_redirects=True,
        proxy=proxy,
        trust_env=False,
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

    versions: dict[str, bool] = {}
    saw_project_file = False
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type:
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Simple API JSON 根对象无效")
            for file in payload.get("files", []):
                if not isinstance(file, dict):
                    continue
                filename = str(file.get("filename", ""))
                parsed = _parse_distribution_filename(
                    filename,
                    normalized,
                    python_version,
                    file.get("requires-python") or file.get("requires_python"),
                )
                if parsed is None:
                    continue
                saw_project_file = True
                version, compatible = parsed
                # A yanked release is not a useful candidate for a new
                # environment unless no non-yanked file exists; leave that
                # policy to pip and simply omit yanked files from the picker.
                if file.get("yanked"):
                    continue
                if compatible:
                    versions[version] = True
        except (TypeError, ValueError, json.JSONDecodeError):
            versions.clear()
            saw_project_file = False
    if not versions and "json" not in content_type:
        parser = _SimpleVersionParser(normalized, python_version)
        parser.feed(response.text)
        versions = parser.versions
        saw_project_file = parser.saw_project_file

    return {
        "manager": "pip",
        "name": normalized,
        "versions": sorted(versions, key=_version_sort_key, reverse=True),
        "compatible": bool(versions) if saw_project_file else None,
        "denied": False,
        "indexing": False,
    }
