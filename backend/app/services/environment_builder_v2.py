"""Secure, reproducible resolver/build primitives for environment editor V2.

The public functions keep dependency resolution inside the selected base image
and make the generated Dockerfile a pure function of platform configuration and
validated declarations.  The Docker execution path is intentionally small and
argv-only so it can be replaced by a BuildKit runner without changing the
domain state machine.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.config import Settings
from app.services.environment_spec import (
    apt_snapshot_key,
    normalize_requested_spec,
    pip_source_key,
)
from app.services.import_policy import normalize_pip_name, validate_locked_version


class V2BuildFailure(Exception):
    def __init__(self, message: str, code: str = "BUILD_FAILED", detail: dict | None = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


class V2BuildTimeout(V2BuildFailure):
    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(message, code="BUILD_TIMEOUT", detail=detail)


@dataclass(frozen=True)
class PublishedImage:
    reference: str
    tag: str
    digest: str
    size_bytes: int


@dataclass(frozen=True)
class V2BuildResult:
    image_digest: str
    image_size_bytes: int
    resolved_spec: dict
    result_summary: dict
    dockerfile_sha256: str
    image_tag: str | None = None


_IMAGE_DIGEST_RE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_REGISTRY_REF_RE = re.compile(r"^[a-z0-9][a-z0-9./:_-]*@sha256:[0-9a-f]{64}$")
_REGISTRY_REPOSITORY_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::[0-9]{1,5})?"
    r"(?:/[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?)*$"
)
_APT_SAFE_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
_PIP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_PROXY_LOOPBACK_RE = re.compile(r"^https?://(?:127\.0\.0\.1|localhost|\[::1\])(?::\d+)?(?:/|$)", re.I)
_APT_SOURCE_RE = re.compile(r"^deb(?:-src)?(?:\s|\[).+$")
_APT_SNAPSHOT_HOST = "snapshot.debian.org"


def is_pullable_registry_reference(value: str | None) -> bool:
    if not value or not _REGISTRY_REF_RE.fullmatch(value):
        return False
    repository, digest = value.rsplit("@", 1)
    return bool(
        is_valid_registry_repository(repository)
        and digest.startswith("sha256:")
    )


def is_valid_registry_repository(value: str | None) -> bool:
    return bool(
        value
        and _REGISTRY_REPOSITORY_RE.fullmatch(value)
        and all(part not in {".", ".."} for part in value.split("/"))
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def platform_runner_sha256() -> str:
    from app.services.environment_builder import _load_kernel_runner

    return hashlib.sha256(_load_kernel_runner().encode("utf-8")).hexdigest()


def build_config_fingerprint(python_version: str, settings: Settings) -> str:
    """Hash the non-secret V2 resolver/build inputs used by a worker.

    The fingerprint is persisted with a job so a worker can fail closed when
    the API and worker are running different platform configurations.  Source
    URLs and proxy values are represented by stable source keys/presence only;
    credentials are never persisted.
    """

    payload = {
        "schema_version": 1,
        "python_version": python_version,
        "base_image_ref": settings.env_python_base_images.get(python_version),
        "platform_python_packages": dict(sorted(settings.env_platform_python_packages.items())),
        "platform_bundle_version": settings.env_platform_bundle_version,
        "platform_runner_sha256": platform_runner_sha256(),
        "pip_source_key": pip_source_key(settings.env_pip_index_url),
        "apt_snapshot_key": apt_snapshot_key(
            python_version, settings.env_apt_snapshot_sources.get(python_version)
        ),
        "build_network_mode": settings.env_build_network_mode,
        "explicit_proxy": bool(settings.env_build_http_proxy),
        "registry_repository": settings.env_registry_repository,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def canonical_lock_sha256(pip_lock: list[dict]) -> str:
    """Hash the normalized pip lock that becomes the immutable build input."""

    normalized = []
    for entry in pip_lock:
        name, version, hashes = _validate_lock_entry(entry)
        normalized.append({"name": name, "version": version, "hashes": hashes})
    normalized.sort(key=lambda item: (item["name"], item["version"], item["hashes"]))
    return hashlib.sha256(_canonical_json(normalized).encode("utf-8")).hexdigest()


def canonical_v2_manifest(
    *,
    base_image_ref: str,
    python_version: str,
    minimum_memory_mb: int,
    requested_spec: dict,
    settings: Settings,
) -> dict:
    """Return a stable manifest and hash for one immutable version snapshot."""

    if not _IMAGE_DIGEST_RE.fullmatch(base_image_ref):
        raise V2BuildFailure(
            "基础镜像必须固定到 digest",
            code="BUILD_SERVICE_UNAVAILABLE",
            detail={"field": "base_image_ref"},
        )
    spec = normalize_requested_spec(requested_spec)
    try:
        source_key = pip_source_key(settings.env_pip_index_url)
    except ValueError as exc:
        raise V2BuildFailure("Python 包源配置无效", code="BUILD_SERVICE_UNAVAILABLE") from exc
    payload = {
        "schema_version": 1,
        "base_image_ref": base_image_ref,
        "python_version": python_version,
        "minimum_memory_mb": minimum_memory_mb,
        "requested_spec": spec,
        "platform_python_packages": dict(sorted(settings.env_platform_python_packages.items())),
        "platform_bundle_version": settings.env_platform_bundle_version,
        "platform_runner_sha256": platform_runner_sha256(),
        "pip_source_key": source_key,
        "apt_snapshot_key": apt_snapshot_key(
            python_version, settings.env_apt_snapshot_sources.get(python_version)
        ),
    }
    payload["manifest_sha256"] = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return payload


def _hash_value(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"


def _validate_lock_entry(entry: dict) -> tuple[str, str, list[str]]:
    name = str(entry.get("name", ""))
    version = str(entry.get("version", ""))
    try:
        name = normalize_pip_name(name)
        version = validate_locked_version(version)
    except ValueError as exc:
        raise V2BuildFailure("pip lock 包条目格式无效", code="PIP_RESOLUTION_FAILED") from exc
    if not _PIP_NAME_RE.fullmatch(name):
        raise V2BuildFailure("pip lock 包条目格式无效", code="PIP_RESOLUTION_FAILED")
    hashes = entry.get("hashes") or []
    if not isinstance(hashes, list) or not hashes:
        raise V2BuildFailure(
            f"包 {name} 没有可验证下载哈希",
            code="PIP_RESOLUTION_FAILED",
            detail={"package": name},
        )
    normalized_hashes = []
    for digest in hashes:
        digest = _hash_value(str(digest))
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise V2BuildFailure("pip lock 哈希格式无效", code="PIP_RESOLUTION_FAILED")
        normalized_hashes.append(digest)
    return name, version, sorted(set(normalized_hashes))


def build_pip_lock_from_report(report: dict) -> list[dict]:
    """Convert pip's installation report into a hash-required platform lock."""

    if not isinstance(report, dict) or not isinstance(report.get("install"), list):
        raise V2BuildFailure("pip installation report 格式无效", code="PIP_RESOLUTION_FAILED")
    lock = []
    seen_names = set()
    for item in report["install"]:
        if not isinstance(item, dict):
            raise V2BuildFailure("pip installation report 条目无效", code="PIP_RESOLUTION_FAILED")
        metadata = item.get("metadata") or {}
        download = item.get("download_info") or {}
        archive = download.get("archive_info") or {}
        hashes = archive.get("hashes") or {}
        if not metadata.get("name") or not metadata.get("version") or not hashes.get("sha256"):
            raise V2BuildFailure(
                "pip report 缺少名称、版本或 sha256 下载哈希",
                code="PIP_RESOLUTION_FAILED",
                detail={"report_item": item.get("metadata", {})},
            )
        try:
            normalized_name = normalize_pip_name(str(metadata["name"]))
            if normalized_name in seen_names:
                raise ValueError(f"duplicate distribution: {normalized_name}")
            seen_names.add(normalized_name)
            lock.append(
                {
                    "name": normalized_name,
                    "version": validate_locked_version(str(metadata["version"])),
                    "hashes": [_hash_value(str(hashes["sha256"]))],
                }
            )
        except ValueError as exc:
            raise V2BuildFailure(
                "pip installation report 包条目格式无效",
                code="PIP_RESOLUTION_FAILED",
                detail={"package": metadata.get("name")},
            ) from exc
    lock.sort(key=lambda item: (item["name"].lower().replace("_", "-"), item["version"]))
    return lock


def _requirement_line(entry: dict) -> str:
    name, version, hashes = _validate_lock_entry(entry)
    rendered = f"{name}=={version}"
    for digest in hashes:
        rendered += f" --hash={digest}"
    return rendered


def _safe_pip_index_url(index_url: str | None) -> str | None:
    if not index_url:
        return None
    from urllib.parse import urlsplit, urlunsplit

    parsed = urlsplit(index_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise V2BuildFailure("Python 包源配置无效", code="BUILD_SERVICE_UNAVAILABLE")
    if parsed.username is not None or parsed.password is not None:
        raise V2BuildFailure(
            "Python 包源凭据必须通过 Worker secret 提供",
            code="BUILD_SERVICE_UNAVAILABLE",
        )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _safe_apt_sources(sources: list[str] | None) -> list[str]:
    if not sources:
        return []
    clean = []
    for source in sources:
        if not isinstance(source, str) or "\n" in source or "\r" in source:
            raise V2BuildFailure("Debian 快照源配置无效", code="BUILD_SERVICE_UNAVAILABLE")
        source = source.strip()
        if not _APT_SOURCE_RE.fullmatch(source):
            raise V2BuildFailure("Debian 快照源配置无效", code="BUILD_SERVICE_UNAVAILABLE")
        try:
            parts = shlex.split(source, comments=False, posix=True)
        except ValueError as exc:
            raise V2BuildFailure("Debian 快照源配置无效", code="BUILD_SERVICE_UNAVAILABLE") from exc
        if len(parts) < 4 or parts[0] not in {"deb", "deb-src"}:
            raise V2BuildFailure("Debian 快照源配置无效", code="BUILD_SERVICE_UNAVAILABLE")
        uri_index = 1
        if parts[uri_index].startswith("["):
            options = parts[uri_index].strip("[]").split()
            if not options or any(
                option.lower().startswith(("trusted=", "signed-by=", "auth-conf="))
                for option in options
            ):
                raise V2BuildFailure(
                    "Debian 快照源不允许 trusted、凭据或自定义签名配置",
                    code="BUILD_SERVICE_UNAVAILABLE",
                )
            if any(option.lower() != "check-valid-until=no" for option in options):
                raise V2BuildFailure("Debian 快照源选项不受平台允许", code="BUILD_SERVICE_UNAVAILABLE")
            uri_index += 1
        parsed = urlsplit(parts[uri_index])
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname != _APT_SNAPSHOT_HOST
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or ".." in parsed.path.split("/")
            or not parsed.path.startswith("/archive/")
        ):
            raise V2BuildFailure(
                "Debian 快照源必须是平台固定的 snapshot.debian.org archive 路径",
                code="BUILD_SERVICE_UNAVAILABLE",
            )
        clean.append(source)
    return clean


def render_v2_dockerfile(
    manifest: dict,
    *,
    pip_lock: list[dict],
    pip_index_url: str | None = None,
    apt_snapshot_sources: list[str] | None = None,
) -> str:
    """Render the only Dockerfile accepted by the V2 worker."""

    base_image_ref = manifest["base_image_ref"]
    if not _IMAGE_DIGEST_RE.fullmatch(base_image_ref):
        raise V2BuildFailure("基础镜像引用无效", code="BUILD_SERVICE_UNAVAILABLE")
    requested = normalize_requested_spec(manifest["requested_spec"])
    safe_pip_index_url = _safe_pip_index_url(pip_index_url)
    safe_apt_sources = _safe_apt_sources(apt_snapshot_sources)
    pip_index_option = (
        f" --index-url {shlex.quote(safe_pip_index_url)}"
        if safe_pip_index_url
        else ""
    )
    apt_lines = []
    for item in requested["system_packages"]:
        name = item["name"]
        if not _APT_SAFE_RE.fullmatch(name):
            raise V2BuildFailure("系统包名无效", code="APT_PACKAGE_DENIED")
        value = name if item.get("version") is None else f"{name}={item['version']}"
        apt_lines.append(shlex.quote(value))
    # Validate every lock entry here, but keep the lock itself in the build
    # context.  Appending requirement lines to a Dockerfile would make them
    # invalid Dockerfile instructions after the final WORKDIR command.
    for entry in pip_lock:
        _requirement_line(entry)
    lines = [
        "# 自动生成——环境编辑器 V2 canonical Dockerfile",
        f"FROM {base_image_ref}",
        "ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1",
    ]
    if apt_lines:
        apt_prefix = "RUN "
        if safe_apt_sources:
            apt_prefix += (
                "rm -f /etc/apt/sources.list /etc/apt/sources.list.d/* && printf '%s\\n' "
                + " ".join(shlex.quote(source) for source in safe_apt_sources)
                + " > /etc/apt/sources.list.d/dai-snapshot.list && "
            )
        lines.append(
            apt_prefix
            + "apt-get update && apt-get install -y --no-install-recommends \\\n    "
            + " \\\n    ".join(apt_lines)
            + " && rm -rf /var/lib/apt/lists/* /etc/apt/sources.list.d/dai-snapshot.list"
        )
    lines += [
        "COPY pip.lock /opt/dai/pip.lock",
        f"RUN python -m pip install --no-cache-dir{pip_index_option} --require-hashes -r /opt/dai/pip.lock",
        "COPY kernel_runner.py /opt/dai/kernel_runner.py",
        "RUN test -s /opt/dai/kernel_runner.py && python -m py_compile /opt/dai/kernel_runner.py",
        "RUN useradd --uid 1000 --create-home student && mkdir -p /course /work /tmp && chown -R student:student /course /work /tmp",
        "USER student",
        "WORKDIR /work",
    ]
    return "\n".join(lines) + "\n"


_REGISTRY_CONFIG_ALLOWED_KEYS = {"auths"}
_REGISTRY_AUTH_ALLOWED_KEYS = {"auth", "identitytoken"}


def _load_registry_docker_config(settings: Settings, *, required: bool = False) -> dict:
    """Load and reduce the operator-provided Docker config Secret.

    Docker supports credential helpers, ``credsStore`` and a ``proxies``
    block in config.json.  None of those are safe inputs for this worker:
    helpers may execute arbitrary host binaries and proxies can silently
    reintroduce a loopback route into build containers.  Only standard base64
    ``auth``/``identitytoken`` entries are copied into the isolated config.
    """

    path = Path(getattr(settings, "env_registry_docker_config", "/run/secrets/config.json"))
    allow_anonymous = bool(getattr(settings, "env_registry_allow_anonymous", False))
    if not path.is_file():
        if required and not allow_anonymous:
            raise V2BuildFailure(
                "Registry Docker config Secret 未挂载",
                code="BUILD_SERVICE_UNAVAILABLE",
                detail={"phase": "preflight", "dependency": "registry_auth"},
            )
        return {"auths": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V2BuildFailure(
            "Registry Docker config Secret 无法读取",
            code="BUILD_SERVICE_UNAVAILABLE",
            detail={"phase": "preflight", "dependency": "registry_auth"},
        ) from exc
    if not isinstance(raw, dict):
        raise V2BuildFailure(
            "Registry Docker config Secret 格式无效",
            code="BUILD_SERVICE_UNAVAILABLE",
            detail={"phase": "preflight", "dependency": "registry_auth"},
        )
    forbidden = set(raw) - _REGISTRY_CONFIG_ALLOWED_KEYS
    if forbidden:
        raise V2BuildFailure(
            "Registry Docker config 只允许 auths，不允许凭据助手或代理配置",
            code="BUILD_SERVICE_UNAVAILABLE",
            detail={"phase": "preflight", "dependency": "registry_auth"},
        )
    auths = raw.get("auths", {})
    if not isinstance(auths, dict):
        raise V2BuildFailure(
            "Registry Docker config auths 格式无效",
            code="BUILD_SERVICE_UNAVAILABLE",
            detail={"phase": "preflight", "dependency": "registry_auth"},
        )
    sanitized: dict[str, dict[str, str]] = {}
    for registry, entry in auths.items():
        if not isinstance(registry, str) or not registry.strip() or not isinstance(entry, dict):
            raise V2BuildFailure(
                "Registry Docker config auths 条目无效",
                code="BUILD_SERVICE_UNAVAILABLE",
                detail={"phase": "preflight", "dependency": "registry_auth"},
            )
        unsupported = set(entry) - _REGISTRY_AUTH_ALLOWED_KEYS
        if unsupported:
            raise V2BuildFailure(
                "Registry Docker config auths 只允许 auth 或 identitytoken",
                code="BUILD_SERVICE_UNAVAILABLE",
                detail={"phase": "preflight", "dependency": "registry_auth"},
            )
        values = {
            key: value
            for key, value in entry.items()
            if key in _REGISTRY_AUTH_ALLOWED_KEYS and isinstance(value, str) and value
        }
        if values:
            sanitized[registry] = values
    if required and not allow_anonymous and not sanitized:
        raise V2BuildFailure(
            "Registry Docker config Secret 未提供可用 auths",
            code="BUILD_SERVICE_UNAVAILABLE",
            detail={"phase": "preflight", "dependency": "registry_auth"},
        )
    return {"auths": sanitized}


def registry_auth_check(settings: Settings) -> dict[str, str]:
    """Return a readiness-safe status without exposing credential material."""

    try:
        config = _load_registry_docker_config(settings, required=True)
    except V2BuildFailure as exc:
        return {
            "status": "misconfigured",
            "code": "REGISTRY_AUTH_REQUIRED",
            "message": str(exc),
        }
    if getattr(settings, "env_registry_allow_anonymous", False):
        return {
            "status": "configured",
            "message": "已显式允许匿名 Registry 访问",
        }
    return {
        "status": "configured",
        "message": f"Registry 只读认证 Secret 已挂载（{len(config['auths'])} 个 Registry）",
    }


def _write_isolated_docker_config(settings: Settings) -> str:
    """Copy only safe auths into a private temporary Docker config directory."""

    config = _load_registry_docker_config(settings, required=False)
    config_dir = Path("/tmp/dai-v2-docker-config")
    config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    config_file.write_text(
        json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    try:
        os.chmod(config_file, 0o600)
    except OSError:
        pass
    return str(config_dir)


def _subprocess_env(settings: Settings) -> dict[str, str]:
    """Only pass a minimal environment to Docker; never inherit host proxies."""

    # Docker CLI can also inject ``~/.docker/config.json``'s ``proxies`` block
    # into containers.  Use an isolated config directory so clearing process
    # environment variables is sufficient to prevent the historical loopback
    # proxy from reappearing through the CLI configuration.
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "DOCKER_CONFIG": _write_isolated_docker_config(settings),
    }
    if settings.env_build_http_proxy:
        env["HTTP_PROXY"] = settings.env_build_http_proxy
        env["HTTPS_PROXY"] = settings.env_build_http_proxy
        env["http_proxy"] = settings.env_build_http_proxy
        env["https_proxy"] = settings.env_build_http_proxy
    return env


def _docker_proxy_args(settings: Settings) -> list[str]:
    """Pass only the explicitly configured proxy into networked build helpers."""

    proxy = settings.env_build_http_proxy
    if not proxy:
        return []
    return [
        "-e", f"HTTP_PROXY={proxy}",
        "-e", f"HTTPS_PROXY={proxy}",
        "-e", f"http_proxy={proxy}",
        "-e", f"https_proxy={proxy}",
    ]


def _run_capture(
    command: list[str],
    *,
    timeout: int,
    env: dict[str, str] | None = None,
    lease_check=None,
    register_process=None,
    unregister_process=None,
):
    """Run a Docker helper while allowing an expired lease to kill it."""

    if lease_check is None and register_process is None and unregister_process is None:
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            _cleanup_named_container(command, env)
            raise V2BuildTimeout("Docker 子进程超过构建时限") from exc
        except OSError as exc:
            raise V2BuildFailure(
                "Docker 子进程无法启动",
                code="BUILD_SERVICE_UNAVAILABLE",
                detail={"command": command[:3], "error": str(exc)[:300]},
            ) from exc
        except BaseException:
            _cleanup_named_container(command, env)
            raise

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    if register_process is not None:
        register_process(process)
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            _cleanup_named_container(command, env)
            raise V2BuildTimeout("Docker 子进程超过构建时限")
    finally:
        if unregister_process is not None:
            unregister_process(process)
    if lease_check is not None:
        lease_check()
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _cleanup_named_container(command: list[str], env: dict[str, str] | None = None) -> None:
    """Stop a daemon-side ``docker run`` child after the CLI has timed out."""

    try:
        name_index = command.index("--name")
        container_name = command[name_index + 1]
    except (ValueError, IndexError):
        return
    try:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _validate_build_proxy(proxy: str | None) -> None:
    if not proxy:
        return
    if any(character.isspace() for character in proxy):
        raise V2BuildFailure("构建代理配置无效", code="BUILD_SERVICE_UNAVAILABLE")
    parsed = urlsplit(proxy)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise V2BuildFailure("构建代理必须是 HTTP(S) URL", code="BUILD_SERVICE_UNAVAILABLE")
    if parsed.username is not None or parsed.password is not None:
        raise V2BuildFailure(
            "构建代理凭据必须通过平台 secret 机制提供",
            code="BUILD_SERVICE_UNAVAILABLE",
        )


def _validate_preflight(manifest: dict, settings: Settings) -> None:
    if shutil.which("docker") is None:
        raise V2BuildFailure("Worker 未发现 Docker", code="BUILD_SERVICE_UNAVAILABLE")
    repository = settings.env_registry_repository
    if not is_valid_registry_repository(repository):
        raise V2BuildFailure(
            "V2 构建必须配置合法的 Registry repository",
            code="BUILD_SERVICE_UNAVAILABLE",
            detail={"phase": "preflight", "dependency": "registry"},
        )
    _load_registry_docker_config(settings, required=True)
    platform_names = {normalize_pip_name(name) for name in settings.env_platform_python_packages}
    missing_platform = {name for name in ("ipykernel", "pytest") if name not in platform_names}
    if missing_platform:
        raise V2BuildFailure(
            "平台固定依赖缺失，不能构建环境镜像",
            code="BUILD_SERVICE_UNAVAILABLE",
            detail={"phase": "preflight", "missing_platform_packages": sorted(missing_platform)},
        )
    proxy = settings.env_build_http_proxy or ""
    _validate_build_proxy(proxy)
    if _PROXY_LOOPBACK_RE.match(proxy) and settings.env_build_network_mode != "host":
        raise V2BuildFailure(
            "构建代理指向宿主机回环地址，但当前 Docker 网络不是 host",
            code="BUILD_PROXY_UNREACHABLE",
        )
    for item in manifest["requested_spec"]["system_packages"]:
        if not _APT_SAFE_RE.fullmatch(item["name"]):
            raise V2BuildFailure("系统包名被拒绝", code="APT_PACKAGE_DENIED")
        if any(re.fullmatch(pattern, item["name"]) for pattern in settings.env_apt_deny_patterns):
            raise V2BuildFailure(
                f"系统包 {item['name']} 被平台安全策略禁止",
                code="APT_PACKAGE_DENIED",
                detail={"package": item["name"]},
            )
    if manifest["requested_spec"]["system_packages"]:
        sources = settings.env_apt_snapshot_sources.get(manifest["python_version"])
        _safe_apt_sources(sources)
        if not sources:
            raise V2BuildFailure(
                "系统包构建缺少平台 Debian 快照源",
                code="BUILD_SERVICE_UNAVAILABLE",
                detail={"python_version": manifest["python_version"]},
            )


def _docker_network_arg(settings: Settings) -> str:
    return settings.env_build_network_mode


def _decode_report(output: str) -> dict:
    marker = "DAI_PIP_REPORT_BASE64="
    for line in output.splitlines()[::-1]:
        if line.startswith(marker):
            try:
                return json.loads(base64.b64decode(line[len(marker) :]).decode("utf-8"))
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise V2BuildFailure("无法读取 pip installation report", code="PIP_RESOLUTION_FAILED") from exc
    raise V2BuildFailure("构建容器未返回 pip installation report", code="PIP_RESOLUTION_FAILED")


def _resolve_in_base_image(
    manifest: dict,
    settings: Settings,
    timeout: int,
    *,
    lease_check=None,
    register_process=None,
    unregister_process=None,
) -> dict:
    requirements = []
    for item in manifest["requested_spec"]["python_packages"]:
        requirements.append(item["name"] if item["version"] is None else f"{item['name']}=={item['version']}")
    requirements.extend(
        f"{name}=={version}" for name, version in sorted(settings.env_platform_python_packages.items())
    )
    requirement_args = " ".join(shlex.quote(item) for item in requirements)
    pip_index_url = _safe_pip_index_url(settings.env_pip_index_url)
    pip_index_option = f" --index-url {shlex.quote(pip_index_url)}" if pip_index_url else ""
    apt_args = []
    for item in manifest["requested_spec"]["system_packages"]:
        apt_args.append(shlex.quote(item["name"] if item["version"] is None else f"{item['name']}={item['version']}"))
    apt_script = ""
    container_name = f"dai-v2-resolve-{manifest['manifest_sha256'][:20]}"
    if apt_args:
        sources = _safe_apt_sources(settings.env_apt_snapshot_sources.get(manifest["python_version"]))
        source_script = (
            "rm -f /etc/apt/sources.list /etc/apt/sources.list.d/* && printf '%s\\n' "
            + " ".join(shlex.quote(source) for source in sources)
            + " > /etc/apt/sources.list.d/dai-snapshot.list && "
        )
        apt_script = (
            source_script
            + "apt-get update && apt-get install -y --no-install-recommends "
            + " ".join(apt_args)
            + " && rm -rf /var/lib/apt/lists/* /etc/apt/sources.list.d/dai-snapshot.list && "
        )
    script = (
        apt_script
        + "python -m pip install --quiet --dry-run --ignore-installed --no-input "
        + pip_index_option
        + " --report /tmp/dai-pip-report.json "
        + requirement_args
        + " && python -c "
        + shlex.quote(
            "import base64; print('DAI_PIP_REPORT_BASE64=' + base64.b64encode(open('/tmp/dai-pip-report.json','rb').read()).decode())"
        )
    )
    try:
        result = _run_capture(
            [
                "docker",
                "run",
                "--rm",
                "--name",
                container_name,
                "--network",
                _docker_network_arg(settings),
                "--cpus",
                str(settings.env_build_cpu_limit),
                "--memory",
                f"{settings.env_build_memory_mb}m",
                "--pids-limit",
                str(settings.env_build_pids_limit),
                "--cap-drop",
                "ALL",
                # apt 在 root 解析阶段仍需切换到 _apt 并维护缓存目录；
                # 只恢复这些能力，最终验证容器继续保持 drop-all。
                "--cap-add",
                "CHOWN",
                "--cap-add",
                "SETUID",
                "--cap-add",
                "SETGID",
                "--cap-add",
                "DAC_OVERRIDE",
                "--security-opt",
                "no-new-privileges",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=512m",
                *_docker_proxy_args(settings),
                manifest["base_image_ref"],
                "sh",
                "-c",
                script,
            ],
            timeout=timeout,
            env=_subprocess_env(settings),
            lease_check=lease_check,
            register_process=register_process,
            unregister_process=unregister_process,
        )
    except V2BuildTimeout as exc:
        _cleanup_named_container(["docker", "run", "--name", container_name], _subprocess_env(settings))
        raise V2BuildTimeout("依赖解析超过构建时限", detail={"phase": "resolving"}) from exc
    if result.returncode != 0:
        stderr = result.stderr or ""
        lowered = stderr.lower()
        source_failure_markers = (
            "could not connect",
            "connection refused",
            "temporary failure resolving",
            "failed to fetch",
            "network is unreachable",
            "proxyerror",
        )
        if any(marker in lowered for marker in source_failure_markers):
            error_code = "BUILD_SERVICE_UNAVAILABLE"
        elif "No matching distribution" in stderr or "Could not find a version" in stderr:
            error_code = "PIP_PACKAGE_NOT_FOUND"
        elif "ResolutionImpossible" in stderr or "conflict" in lowered:
            error_code = "DEPENDENCY_CONFLICT"
        elif "E: Unable to locate package" in stderr:
            error_code = "APT_PACKAGE_NOT_FOUND"
        else:
            error_code = "PIP_RESOLUTION_FAILED" if "pip" in stderr.lower() else "APT_PACKAGE_NOT_FOUND"
        raise V2BuildFailure(
            "pip/apt 解析失败",
            code=error_code,
            detail={"stderr": stderr[-1000:]},
        )
    return _decode_report(result.stdout)


def _run_docker_build(
    context: Path,
    tag: str,
    settings: Settings,
    timeout: int,
    *,
    lease_check=None,
    register_process=None,
    unregister_process=None,
) -> None:
    _validate_build_proxy(settings.env_build_http_proxy)
    command = [
        "docker",
        "build",
        f"--network={_docker_network_arg(settings)}",
        "--ulimit",
        f"nproc={settings.env_build_pids_limit}:{settings.env_build_pids_limit}",
        "-t",
        tag,
        "-f",
        str(context / "Dockerfile"),
        str(context),
    ]
    if settings.env_build_http_proxy:
        # HTTP_PROXY/HTTPS_PROXY are BuildKit predefined proxy args.  They are
        # consumed by the build without being written into the Dockerfile;
        # credentials are rejected above because V2 has no secret input from
        # the administrator.
        command[2:2] = [
            "--build-arg",
            f"HTTP_PROXY={settings.env_build_http_proxy}",
            "--build-arg",
            f"HTTPS_PROXY={settings.env_build_http_proxy}",
        ]
    try:
        result = _run_capture(
            command,
            timeout=timeout,
            env=_subprocess_env(settings),
            lease_check=lease_check,
            register_process=register_process,
            unregister_process=unregister_process,
        )
    except V2BuildTimeout as exc:
        try:
            subprocess.run(
                ["docker", "image", "rm", "--force", tag],
                capture_output=True,
                text=True,
                timeout=30,
                env=_subprocess_env(settings),
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise V2BuildTimeout("Docker 构建超过构建时限", detail={"phase": "building"}) from exc
    if result.returncode != 0:
        raise V2BuildFailure("Docker 镜像构建失败", code="BUILD_FAILED", detail={"stderr": result.stderr[-1000:]})


def _validate_image(
    tag: str,
    manifest: dict,
    settings: Settings,
    timeout: int,
    *,
    lease_check=None,
    register_process=None,
    unregister_process=None,
) -> tuple[dict, str, int]:
    import_names = {"ipykernel", "pytest"}
    for item in manifest["requested_spec"]["python_packages"]:
        import_names.update(item.get("import_names") or [])
    required_distributions = set(settings.env_platform_python_packages)
    required_distributions.update(
        item["name"] for item in manifest["requested_spec"]["python_packages"]
    )
    required_system_packages = manifest["requested_spec"]["system_packages"]
    script = f"""
import base64
import importlib
import importlib.metadata
import json
import re
import subprocess

requested_imports = {repr(sorted(import_names))}
required_distributions = {repr(sorted(required_distributions))}
required_system_packages = {repr(required_system_packages)}
for name in requested_imports:
    importlib.import_module(name)
for distribution in required_distributions:
    importlib.metadata.version(distribution)
for package in required_system_packages:
    format_string = chr(36) + "{{Status}} " + chr(36) + "{{Version}} " + chr(36) + "{{Architecture}}"
    command = ["dpkg-query", "-W", "-f=" + format_string, package["name"]]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.startswith("install ok installed "):
        raise RuntimeError("apt package is not installed: " + package["name"])
    installed_version = result.stdout.split()[3] if len(result.stdout.split()) > 3 else ""
    if package.get("version") and installed_version != package["version"]:
        raise RuntimeError("apt package version mismatch: " + package["name"])
subprocess.run(["python", "-m", "pip", "check"], check=True)
pip_version = subprocess.check_output(["python", "-m", "pip", "--version"], text=True).strip()
compile(open("/opt/dai/kernel_runner.py", encoding="utf-8").read(), "/opt/dai/kernel_runner.py", "exec")
from jupyter_client import BlockingKernelClient
BlockingKernelClient()
mapping = importlib.metadata.packages_distributions()
def normalize_distribution(value):
    return re.sub(r"[-_.]+", "-", value.lower())
distribution_names = {{normalize_distribution(name) for name in required_distributions}}
auto_imports_by_distribution = {{}}
for module, distributions in mapping.items():
    for distribution in distributions:
        normalized_distribution = normalize_distribution(distribution)
        if normalized_distribution in distribution_names:
            auto_imports_by_distribution.setdefault(normalized_distribution, []).append(module)
auto_imports = sorted({{module for modules in auto_imports_by_distribution.values() for module in modules}})
warnings = []
for package in {repr(manifest["requested_spec"]["python_packages"])}:
    normalized_name = normalize_distribution(package["name"])
    if not package.get("import_names") and not auto_imports_by_distribution.get(normalized_name):
        warnings.append({{"code": "IMPORT_NAME_NOT_DETECTED", "distribution": package["name"]}})
dpkg_output = subprocess.check_output(
    ["dpkg-query", "-W", "-f=" + chr(36) + "{{Package}}\\t" + chr(36) + "{{Version}}\\t" + chr(36) + "{{Architecture}}\\n"],
    text=True,
)
apt_manifest = []
for line in dpkg_output.splitlines():
    fields = line.split("\\t")
    if len(fields) == 3 and all(fields):
        apt_manifest.append({{"name": fields[0], "version": fields[1], "architecture": fields[2]}})
apt_by_name = {{item["name"]: item for item in apt_manifest}}
direct_apt = [
    apt_by_name[item["name"]]
    for item in required_system_packages
    if item["name"] in apt_by_name
]
payload = {{
    "imports": sorted(set(requested_imports) | set(auto_imports)),
    "auto_imports": auto_imports,
    "warnings": warnings,
    "pip_check": {{"ok": True}},
    "pip_version": pip_version,
    "apt": apt_manifest,
    "direct_apt": direct_apt,
    "platform_runner": {{"ok": True}},
}}
print("DAI_VALIDATION_BASE64=" + base64.b64encode(json.dumps(payload).encode()).decode())
"""
    try:
        result = _run_capture(
            [
                "docker", "run", "--rm", "--name", f"dai-v2-validate-{manifest['manifest_sha256'][:20]}",
                "--network", "none", "--user", "1000:1000",
                "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--pids-limit", str(settings.env_build_pids_limit),
                "--memory", f"{settings.env_build_memory_mb}m",
                "--cpus", str(settings.env_build_cpu_limit),
                tag, "python", "-c", script,
            ],
            timeout=timeout,
            env=_subprocess_env(settings),
            lease_check=lease_check,
            register_process=register_process,
            unregister_process=unregister_process,
        )
    except V2BuildTimeout as exc:
        raise V2BuildTimeout("镜像验证超过构建时限", detail={"phase": "validating"}) from exc
    if result.returncode != 0:
        raise V2BuildFailure("镜像验证失败", code="BUILD_VALIDATION_FAILED", detail={"stderr": result.stderr[-1000:]})
    validation = None
    for line in result.stdout.splitlines()[::-1]:
        if line.startswith("DAI_VALIDATION_BASE64="):
            try:
                validation = json.loads(
                    base64.b64decode(line.split("=", 1)[1]).decode("utf-8")
                )
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise V2BuildFailure("镜像验证报告格式无效", code="BUILD_VALIDATION_FAILED") from exc
            break
    if not isinstance(validation, dict):
        raise V2BuildFailure("镜像未返回验证报告", code="BUILD_VALIDATION_FAILED")
    try:
        inspect = _run_capture(
            ["docker", "image", "inspect", tag, "--format", "{{json .}}"],
            timeout=30,
            env=_subprocess_env(settings),
            lease_check=lease_check,
            register_process=register_process,
            unregister_process=unregister_process,
        )
    except V2BuildTimeout as exc:
        raise V2BuildTimeout("读取镜像信息超过时限", detail={"phase": "finalizing"}) from exc
    if inspect.returncode != 0:
        raise V2BuildFailure("无法读取镜像 digest", code="BUILD_VALIDATION_FAILED")
    try:
        info = json.loads(inspect.stdout)
        digest = str(info.get("Id", ""))
        size = int(info.get("Size", 0))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise V2BuildFailure("镜像 inspect 结果无效", code="BUILD_VALIDATION_FAILED") from exc
    if not digest.startswith("sha256:") or size > settings.env_build_max_image_bytes:
        raise V2BuildFailure("镜像 digest 或大小不符合平台限制", code="BUILD_VALIDATION_FAILED")
    return validation, digest, size


def _publish_image_to_registry(
    local_tag: str,
    manifest: dict,
    settings: Settings,
    timeout: int,
    *,
    lease_check=None,
    register_process=None,
    unregister_process=None,
) -> PublishedImage:
    """Push and pull-verify the immutable Registry reference.

    ``image_digest`` is intentionally the pullable ``repository@sha256``
    reference, never a node-local Docker image ID.  A push, digest discovery,
    pull, or inspect failure aborts the build before the Version can become
    available.
    """

    repository = settings.env_registry_repository
    if not is_valid_registry_repository(repository):
        raise V2BuildFailure(
            "V2 构建必须配置合法的 Registry repository",
            code="BUILD_SERVICE_UNAVAILABLE",
            detail={"phase": "finalizing", "dependency": "registry"},
        )
    tag = f"{repository}:v2-{manifest['manifest_sha256']}"

    def run(command: list[str], *, seconds: int):
        result = _run_capture(
            command,
            timeout=seconds,
            env=_subprocess_env(settings),
            lease_check=lease_check,
            register_process=register_process,
            unregister_process=unregister_process,
        )
        if result.returncode != 0:
            raise V2BuildFailure(
                "Registry 镜像操作失败",
                code="BUILD_SERVICE_UNAVAILABLE",
                detail={"phase": "finalizing", "command": command[:3], "stderr": (result.stderr or "")[-1000:]},
            )
        return result

    try:
        run(["docker", "tag", local_tag, tag], seconds=60)
        run(["docker", "push", tag], seconds=timeout)
        inspected = run(
            ["docker", "image", "inspect", tag, "--format", "{{json .}}"],
            seconds=60,
        )
        info = json.loads(inspected.stdout)
        repo_digests = info.get("RepoDigests") or []
        matching = [
            str(value)
            for value in repo_digests
            if str(value).startswith(repository + "@")
        ]
        if not matching:
            raise V2BuildFailure(
                "Registry 未返回镜像 digest",
                code="BUILD_SERVICE_UNAVAILABLE",
                detail={"phase": "finalizing", "repository": repository},
            )
        reference = matching[0]
        if not _REGISTRY_REF_RE.fullmatch(reference):
            raise V2BuildFailure(
                "Registry 返回的镜像 digest 格式无效",
                code="BUILD_SERVICE_UNAVAILABLE",
                detail={"phase": "finalizing", "repository": repository},
            )
        digest = reference.rsplit("@", 1)[1]
        run(["docker", "pull", reference], seconds=timeout)
        pulled = run(
            ["docker", "image", "inspect", reference, "--format", "{{json .}}"],
            seconds=60,
        )
        pulled_info = json.loads(pulled.stdout)
        pulled_digests = {str(value) for value in pulled_info.get("RepoDigests") or []}
        if reference not in pulled_digests:
            raise V2BuildFailure(
                "Registry digest 拉取后校验不一致",
                code="BUILD_VALIDATION_FAILED",
                detail={"expected": reference, "actual": sorted(pulled_digests)},
            )
        size = int(pulled_info.get("Size", 0))
        if size > settings.env_build_max_image_bytes:
            raise V2BuildFailure(
                "Registry 镜像超过平台大小限制",
                code="BUILD_VALIDATION_FAILED",
                detail={"size_bytes": size},
            )
        return PublishedImage(reference=reference, tag=tag, digest=digest, size_bytes=size)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise V2BuildFailure(
            "Registry 镜像 inspect 结果无效",
            code="BUILD_SERVICE_UNAVAILABLE",
            detail={"phase": "finalizing", "repository": repository},
        ) from exc


def execute_v2_build(
    manifest: dict,
    settings: Settings,
    *,
    on_phase=None,
    on_log=None,
    timeout: int | None = None,
    temp_tag: str | None = None,
    lease_check=None,
    register_process=None,
    unregister_process=None,
    pip_lock: list[dict] | None = None,
    on_resolution_lock=None,
) -> V2BuildResult:
    """Resolve, build, and validate one V2 immutable version."""

    on_phase = on_phase or (lambda phase: None)
    on_log = on_log or (lambda line: None)
    timeout = timeout or settings.env_build_timeout_seconds
    def mark_phase(phase: str) -> None:
        on_phase(phase)
        on_log(f"# phase={phase}")

    mark_phase("preflight")
    _validate_preflight(manifest, settings)
    mark_phase("resolving_system")
    mark_phase("resolving_python")
    if pip_lock is None:
        report = _resolve_in_base_image(
            manifest,
            settings,
            timeout,
            lease_check=lease_check,
            register_process=register_process,
            unregister_process=unregister_process,
        )
        pip_lock = build_pip_lock_from_report(report)
        if on_resolution_lock is not None:
            on_resolution_lock(pip_lock, canonical_lock_sha256(pip_lock))
    else:
        pip_lock = [
            {"name": name, "version": version, "hashes": hashes}
            for name, version, hashes in (_validate_lock_entry(entry) for entry in pip_lock)
        ]
        pip_lock.sort(key=lambda item: (item["name"], item["version"]))
    resolved_versions = {
        str(item["name"]).lower().replace("_", "-"): item["version"] for item in pip_lock
    }
    direct = []
    for item in manifest["requested_spec"]["python_packages"]:
        direct.append(
            {
                "name": item["name"],
                "requested_version": item["version"],
                "resolved_version": resolved_versions.get(item["name"].lower().replace("_", "-")),
                "import_names": item.get("import_names", []),
                "hashes": next(
                    (
                        entry["hashes"]
                        for entry in pip_lock
                        if entry["name"].lower().replace("_", "-")
                        == item["name"].lower().replace("_", "-")
                    ),
                    [],
                ),
            }
        )
    required_distributions = {
        normalize_pip_name(name) for name in settings.env_platform_python_packages
    }
    required_distributions.update(
        normalize_pip_name(item["name"])
        for item in manifest["requested_spec"]["python_packages"]
    )
    if not required_distributions.issubset(resolved_versions):
        raise V2BuildFailure(
            "pip 解析结果缺少请求或平台固定依赖",
            code="PIP_RESOLUTION_FAILED",
            detail={
                "phase": "resolving_python",
                "missing_packages": sorted(required_distributions - resolved_versions.keys()),
            },
        )
    dockerfile = render_v2_dockerfile(
        manifest,
        pip_lock=pip_lock,
        pip_index_url=settings.env_pip_index_url,
        apt_snapshot_sources=settings.env_apt_snapshot_sources.get(manifest["python_version"]),
    )
    with tempfile.TemporaryDirectory(prefix="dai-env-v2-") as temp_dir:
        context = Path(temp_dir)
        (context / "Dockerfile").write_text(dockerfile, encoding="utf-8")
        (context / "pip.lock").write_text("\n".join(_requirement_line(entry) for entry in pip_lock) + "\n", encoding="utf-8")
        from app.services.environment_builder import _load_kernel_runner

        runner_source = _load_kernel_runner()
        (context / "kernel_runner.py").write_text(runner_source, encoding="utf-8")
        mark_phase("building")
        tag = temp_tag or f"dai-env:v2-build-{manifest['manifest_sha256'][:16]}"
        _run_docker_build(
            context,
            tag,
            settings,
            timeout,
            lease_check=lease_check,
            register_process=register_process,
            unregister_process=unregister_process,
        )
        mark_phase("validating")
        validation, digest, size = _validate_image(
            tag,
            manifest,
            settings,
            timeout,
            lease_check=lease_check,
            register_process=register_process,
            unregister_process=unregister_process,
        )
        mark_phase("finalizing")
        published = _publish_image_to_registry(
            tag,
            manifest,
            settings,
            timeout,
            lease_check=lease_check,
            register_process=register_process,
            unregister_process=unregister_process,
        )
    # The persisted resolver lock is the exact pip lock used by the final
    # --require-hashes installation.  Keep the same canonical hash in the
    # resolved report so a retry can prove that it used identical input.
    lock_sha256 = canonical_lock_sha256(pip_lock)
    resolved_spec = {
        "schema_version": 1,
        "resolution_quality": "resolved",
        "direct_python_packages": direct,
        "python_lock": pip_lock,
        "system_packages": validation.get("apt", manifest["requested_spec"]["system_packages"]),
        "direct_system_packages": validation.get(
            "direct_apt", manifest["requested_spec"]["system_packages"]
        ),
        "import_names": validation["imports"],
        "pip_check": validation["pip_check"],
        "base_image_ref": manifest["base_image_ref"],
        "base_image_digest": manifest["base_image_ref"].split("@", 1)[1],
        "python_version": manifest["python_version"],
        "pip_version": validation.get("pip_version"),
        "platform_python_packages": manifest["platform_python_packages"],
        "platform_bundle_version": manifest["platform_bundle_version"],
        "platform_runner_sha256": hashlib.sha256(runner_source.encode("utf-8")).hexdigest(),
        "pip_source_key": manifest["pip_source_key"],
        "apt_snapshot_key": manifest["apt_snapshot_key"],
        "image_digest": published.reference,
        "image_local_id": digest,
        "image_size_bytes": published.size_bytes,
        "lock_sha256": lock_sha256,
        "warnings": validation.get("warnings", []),
        "registry": {
            "reference": published.reference,
            "tag": published.tag,
            "digest": published.digest,
            "verified": True,
        },
    }
    return V2BuildResult(
        image_digest=published.reference,
        image_size_bytes=published.size_bytes,
        resolved_spec=resolved_spec,
        result_summary={
            "image_size_bytes": published.size_bytes,
            "warnings": validation.get("warnings", []),
            "lock_sha256": lock_sha256,
            "imports": validation.get("imports", []),
            "pip_check": validation.get("pip_check"),
            "apt": validation.get("apt", []),
            "direct_apt": validation.get("direct_apt", []),
            "platform_runner": validation.get("platform_runner"),
            "registry": {
                "reference": published.reference,
                "tag": published.tag,
                "digest": published.digest,
                "verified": True,
            },
        },
        dockerfile_sha256=hashlib.sha256(dockerfile.encode("utf-8")).hexdigest(),
        image_tag=published.tag,
    )
