"""V2 environment dependency declarations.

This module is deliberately independent from the database and Docker worker.  It
is the single boundary for normalising administrator input before it is stored,
hashed, searched, or rendered into a build request.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.services.import_policy import (
    normalize_pip_name,
    validate_import_names,
    validate_locked_version,
)

SUPPORTED_PYTHON_VERSIONS = ("3.10", "3.11", "3.12")
DEFAULT_PYTHON_VERSION = "3.12"
DEFAULT_MEMORY_MB = 256
MIN_MEMORY_MB = 64
MAX_MEMORY_MB = 65536
MAX_PYTHON_PACKAGES = 100
MAX_SYSTEM_PACKAGES = 50

_APT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
_APT_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+:~-]*$")
_MAX_APT_NAME = 128
_MAX_APT_VERSION = 128


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} 必须是对象")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} 必须是数组")
    return value


def validate_python_version(value: str) -> str:
    """Validate the platform Python allowlist.

    The editor accepts only the interpreter versions for which the platform has
    pinned base images.  Patch versions are intentionally not accepted here.
    """
    if value not in SUPPORTED_PYTHON_VERSIONS:
        raise ValueError(
            f"Python 版本不受支持，允许值为: {', '.join(SUPPORTED_PYTHON_VERSIONS)}"
        )
    return value


def validate_memory_mb(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("最小内存必须是整数 MB")
    if not MIN_MEMORY_MB <= value <= MAX_MEMORY_MB:
        raise ValueError(f"最小内存必须在 {MIN_MEMORY_MB}–{MAX_MEMORY_MB} MB 之间")
    return value


def validate_apt_name(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("系统包名不能为空")
    if len(value) > _MAX_APT_NAME:
        raise ValueError("系统包名长度不能超过 128")
    if not _APT_NAME_RE.fullmatch(value):
        raise ValueError("系统包名只允许小写字母、数字、加号、点和短横线")
    return value


def validate_apt_version(value: str) -> str:
    """Validate a single Debian version without accepting shell syntax."""
    if not isinstance(value, str) or not value:
        raise ValueError("系统包版本不能为空")
    if len(value) > _MAX_APT_VERSION or not _APT_VERSION_RE.fullmatch(value):
        raise ValueError("系统包版本必须是单个合法 Debian 版本")
    return value


def _normalize_python_package(item: Any, index: int) -> dict[str, Any]:
    raw = _mapping(item, f"python_packages.{index}")
    unknown = set(raw) - {"name", "version", "import_names"}
    if unknown:
        raise ValueError(f"python_packages.{index} 存在未知字段: {sorted(unknown)}")

    name = normalize_pip_name(raw.get("name"))
    version = raw.get("version")
    if version is not None:
        version = validate_locked_version(version)
    import_names = validate_import_names(raw.get("import_names", []))
    return {"name": name, "version": version, "import_names": import_names}


def _normalize_system_package(item: Any, index: int) -> dict[str, Any]:
    raw = _mapping(item, f"system_packages.{index}")
    unknown = set(raw) - {"name", "version"}
    if unknown:
        raise ValueError(f"system_packages.{index} 存在未知字段: {sorted(unknown)}")

    name = validate_apt_name(raw.get("name"))
    version = raw.get("version")
    if version is not None:
        version = validate_apt_version(version)
    return {"name": name, "version": version}


def normalize_requested_spec(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical, JSON-safe requested dependency declaration."""
    raw = _mapping(value, "requested_spec")
    unknown = set(raw) - {"schema_version", "python_packages", "system_packages"}
    if unknown:
        raise ValueError(f"requested_spec 存在未知字段: {sorted(unknown)}")
    if raw.get("schema_version") != 1:
        raise ValueError("requested_spec.schema_version 目前只支持 1")

    python_items = _list(raw.get("python_packages", []), "python_packages")
    system_items = _list(raw.get("system_packages", []), "system_packages")
    if len(python_items) > MAX_PYTHON_PACKAGES:
        raise ValueError(f"Python 直接依赖最多 {MAX_PYTHON_PACKAGES} 个")
    if len(system_items) > MAX_SYSTEM_PACKAGES:
        raise ValueError(f"系统直接依赖最多 {MAX_SYSTEM_PACKAGES} 个")

    python_packages = [_normalize_python_package(item, i) for i, item in enumerate(python_items)]
    system_packages = [_normalize_system_package(item, i) for i, item in enumerate(system_items)]

    python_names = [item["name"] for item in python_packages]
    if len(python_names) != len(set(python_names)):
        raise ValueError("Python 包不能重复")
    system_names = [item["name"] for item in system_packages]
    if len(system_names) != len(set(system_names)):
        raise ValueError("系统包不能重复")

    python_packages.sort(key=lambda item: item["name"])
    system_packages.sort(key=lambda item: item["name"])
    return {
        "schema_version": 1,
        "python_packages": python_packages,
        "system_packages": system_packages,
    }


def canonical_requested_spec(value: Mapping[str, Any]) -> str:
    """Canonical JSON representation used by manifests and idempotency checks."""
    normalised = normalize_requested_spec(value)
    return json.dumps(normalised, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def requested_spec_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_requested_spec(value).encode("utf-8")).hexdigest()


def _configured_source_key(value: Any, fallback: str) -> str:
    """Fingerprint platform source configuration without persisting its URL."""

    if value in (None, "", [], {}):
        return fallback
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{fallback}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def pip_source_key(index_url: str | None) -> str:
    if index_url:
        parsed = urlsplit(index_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Python 包源配置无效")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Python 包源不能在 URL 中携带凭据")
        index_url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
        )
    return _configured_source_key(index_url, "pypi")


def apt_snapshot_key(python_version: str, sources: list[str] | None) -> str:
    return _configured_source_key(sources, f"apt-{python_version}")
