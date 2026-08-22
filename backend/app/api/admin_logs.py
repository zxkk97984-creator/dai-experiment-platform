"""管理员运维日志——直读本进程组的轮转日志文件（JSON 行）。

仅 admin 角色可访问。读取范围严格限定在配置的 log_dir 内（dai-api.log /
dai-worker.log 及其轮转副本），杜绝路径穿越；内容已由 JsonFormatter 脱敏
（api_key/authorization 等键剔除，学生原文按约定从不入日志）。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dependencies import get_db, require_roles
from app.errors import api_error
from app.models import User

logger = logging.getLogger("dai.admin_logs")

router = APIRouter(prefix="/admin/logs", tags=["管理员运维日志"])

_LEVEL_ORDER = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
_KNOWN_SOURCES = ("api", "worker")


def _safe_source(source: str) -> str:
    if source not in _KNOWN_SOURCES:
        raise api_error(422, "INVALID_SOURCE", f"日志来源必须是 {'/'.join(_KNOWN_SOURCES)}")
    return source


def _resolve_file(log_dir: str, source: str, rotated: int | None) -> Path:
    """解析日志文件路径——只允许 log_dir 下的 dai-{source}.log[.N]，防路径穿越。"""
    base = Path(log_dir).resolve()
    name = f"dai-{source}.log" if rotated is None else f"dai-{source}.log.{int(rotated)}"
    path = (base / name).resolve()
    if path.parent != base:
        raise api_error(422, "INVALID_PATH", "非法日志路径")
    if rotated is not None and rotated < 1:
        raise api_error(422, "INVALID_ROTATED", "轮转序号必须 >= 1")
    return path


def _tail_json_lines(path: Path, max_bytes: int) -> list[dict]:
    """读取文件末尾 max_bytes 字节并按行解析 JSON；无法解析的行静默跳过。"""
    if not path.exists():
        return []
    with path.open("rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - max_bytes))
        chunk = fh.read().decode("utf-8", errors="replace")
    records = []
    for line in chunk.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # 半行（正在写入）或非 JSON 行
        if isinstance(record, dict):
            records.append(record)
    return records


@router.get("")
def list_logs(
    source: str = Query(default="api"),
    level: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    rotated: int | None = Query(default=None, ge=1, le=99),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
    settings: Settings = Depends(get_settings),
):
    """按来源/级别/关键词查询最近日志，时间倒序返回。"""
    _safe_source(source)
    if level is not None and level.upper() not in _LEVEL_ORDER:
        raise api_error(422, "INVALID_LEVEL", "级别必须是 DEBUG/INFO/WARNING/ERROR/CRITICAL")
    level = level.upper() if level else None
    keyword = (q or "").strip().lower()

    path = _resolve_file(settings.log_dir, source, rotated)
    # 最多读 8MB 末尾，足够覆盖几千条日志且响应可控
    records = _tail_json_lines(path, max_bytes=8 * 1024 * 1024)

    min_level = _LEVEL_ORDER.get(level) if level else None
    filtered = []
    for record in records:
        rec_level = str(record.get("level", "")).upper()
        if min_level is not None and _LEVEL_ORDER.get(rec_level, 0) < min_level:
            continue
        if keyword:
            haystack = f"{record.get('message', '')} {record.get('logger', '')} {record.get('rid', '')}".lower()
            if keyword not in haystack:
                continue
        filtered.append(record)

    filtered.reverse()  # 最新在前
    return {
        "items": filtered[:limit],
        "total": len(filtered),
        "source": source,
        "rotated": rotated,
        "file": path.name,
        "file_size": path.stat().st_size if path.exists() else 0,
    }


@router.get("/files")
def list_log_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
    settings: Settings = Depends(get_settings),
):
    """列出可用日志文件（当前 + 轮转副本），供前端切换。"""
    files = []
    base = Path(settings.log_dir).resolve() if settings.log_dir else None
    if base and base.is_dir():
        for source in _KNOWN_SOURCES:
            for path in sorted(base.glob(f"dai-{source}.log*"), reverse=True):
                if path.is_file():
                    files.append({
                        "source": source,
                        "name": path.name,
                        "rotated": _rotated_index(path.name),
                        "size": path.stat().st_size,
                        "modified_at": path.stat().st_mtime,
                    })
    return {"items": files}


def _rotated_index(name: str) -> int | None:
    if name.endswith(".log"):
        return None
    suffix = name.rsplit(".", 1)[-1]
    return int(suffix) if suffix.isdigit() else None
