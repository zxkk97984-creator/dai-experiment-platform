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
class V2BuildResult:
    image_digest: str
    image_size_bytes: int
    resolved_spec: dict
    result_summary: dict
    dockerfile_sha256: str


_IMAGE_DIGEST_RE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_APT_SAFE_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
_PIP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_PROXY_LOOPBACK_RE = re.compile(r"^https?://(?:127\.0\.0\.1|localhost|\[::1\])(?::\d+)?(?:/|$)", re.I)
_APT_SOURCE_RE = re.compile(r"^deb(?:-src)?(?:\s|\[).+$")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def platform_runner_sha256() -> str:
    from app.services.environment_builder import _load_kernel_runner

    return hashlib.sha256(_load_kernel_runner().encode("utf-8")).hexdigest()


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
            lock.append(
                {
                    "name": normalize_pip_name(str(metadata["name"])),
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
        if safe_apt_sources:
            lines.append(
                "RUN rm -f /etc/apt/sources.list /etc/apt/sources.list.d/* && printf '%s\\n' "
                + " ".join(shlex.quote(source) for source in safe_apt_sources)
                + " > /etc/apt/sources.list.d/dai-snapshot.list"
            )
        lines += [
            "RUN apt-get update && apt-get install -y --no-install-recommends \\",
            "    " + " \\\n    ".join(apt_lines),
            "RUN rm -rf /var/lib/apt/lists/*",
        ]
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


def _subprocess_env(settings: Settings) -> dict[str, str]:
    """Only pass a minimal environment to Docker; never inherit host proxies."""

    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
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


def _resolve_in_base_image(manifest: dict, settings: Settings, timeout: int) -> dict:
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
            + " && rm -rf /var/lib/apt/lists/* && "
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
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                _docker_network_arg(settings),
                *_docker_proxy_args(settings),
                manifest["base_image_ref"],
                "sh",
                "-c",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_subprocess_env(settings),
        )
    except subprocess.TimeoutExpired as exc:
        raise V2BuildTimeout("依赖解析超过构建时限", detail={"phase": "resolving"}) from exc
    if result.returncode != 0:
        stderr = result.stderr or ""
        if "No matching distribution" in stderr or "Could not find a version" in stderr:
            error_code = "PIP_PACKAGE_NOT_FOUND"
        elif "ResolutionImpossible" in stderr or "conflict" in stderr.lower():
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


def _run_docker_build(context: Path, tag: str, settings: Settings, timeout: int) -> None:
    _validate_build_proxy(settings.env_build_http_proxy)
    command = [
        "docker",
        "build",
        f"--network={_docker_network_arg(settings)}",
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
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_subprocess_env(settings),
        )
    except subprocess.TimeoutExpired as exc:
        raise V2BuildTimeout("Docker 构建超过构建时限", detail={"phase": "building"}) from exc
    if result.returncode != 0:
        raise V2BuildFailure("Docker 镜像构建失败", code="BUILD_FAILED", detail={"stderr": result.stderr[-1000:]})


def _validate_image(tag: str, manifest: dict, settings: Settings, timeout: int) -> tuple[dict, str, int]:
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
        result = subprocess.run(
            ["docker", "run", "--rm", "--network", "none", "--user", "1000:1000", tag, "python", "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_subprocess_env(settings),
        )
    except subprocess.TimeoutExpired as exc:
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
        inspect = subprocess.run(
            ["docker", "image", "inspect", tag, "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            timeout=30,
            env=_subprocess_env(settings),
        )
    except subprocess.TimeoutExpired as exc:
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


def execute_v2_build(
    manifest: dict,
    settings: Settings,
    *,
    on_phase=None,
    on_log=None,
    timeout: int | None = None,
    temp_tag: str | None = None,
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
    report = _resolve_in_base_image(manifest, settings, timeout)
    pip_lock = build_pip_lock_from_report(report)
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
        _run_docker_build(context, tag, settings, timeout)
        mark_phase("validating")
        validation, digest, size = _validate_image(tag, manifest, settings, timeout)
    mark_phase("finalizing")
    lock_payload = {"python_lock": pip_lock, "system_packages": manifest["requested_spec"]["system_packages"]}
    lock_sha256 = hashlib.sha256(_canonical_json(lock_payload).encode("utf-8")).hexdigest()
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
        "image_digest": digest,
        "image_size_bytes": size,
        "lock_sha256": lock_sha256,
        "warnings": validation.get("warnings", []),
    }
    return V2BuildResult(
        image_digest=digest,
        image_size_bytes=size,
        resolved_spec=resolved_spec,
        result_summary={
            "image_size_bytes": size,
            "warnings": validation.get("warnings", []),
            "lock_sha256": lock_sha256,
            "imports": validation.get("imports", []),
            "pip_check": validation.get("pip_check"),
            "apt": validation.get("apt", []),
            "direct_apt": validation.get("direct_apt", []),
            "platform_runner": validation.get("platform_runner"),
        },
        dockerfile_sha256=hashlib.sha256(dockerfile.encode("utf-8")).hexdigest(),
    )
