"""Shared health signal for the environment-image builder worker.

The builder is deliberately asynchronous, so an HTTP 200 from the API cannot
prove that a worker is alive or that it can reach the Docker daemon.  The
worker publishes a short-lived Redis key only after its startup reconciliation
and Docker daemon check succeed.  The API treats an absent/expired key as a
closed build gate.
"""

from __future__ import annotations

import json
import time
from typing import Any


DEFAULT_HEARTBEAT_KEY = "environment:v2:builder:heartbeat"
DEFAULT_HEARTBEAT_TTL_SECONDS = 30
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 10


def heartbeat_key(settings: Any) -> str:
    return str(getattr(settings, "env_builder_heartbeat_key", DEFAULT_HEARTBEAT_KEY))


def heartbeat_ttl_seconds(settings: Any) -> int:
    value = int(
        getattr(
            settings,
            "env_builder_heartbeat_ttl_seconds",
            DEFAULT_HEARTBEAT_TTL_SECONDS,
        )
    )
    return max(5, value)


def heartbeat_interval_seconds(settings: Any) -> int:
    value = int(
        getattr(
            settings,
            "env_builder_heartbeat_interval_seconds",
            DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        )
    )
    return max(1, min(value, heartbeat_ttl_seconds(settings) - 1))


def publish_heartbeat(redis_client, settings: Any, *, owner_id: str) -> None:
    """Publish one heartbeat without putting secrets into Redis or logs."""

    payload = json.dumps(
        {
            "owner_id": owner_id,
            "updated_at": int(time.time()),
        },
        separators=(",", ":"),
    )
    redis_client.set(
        heartbeat_key(settings),
        payload,
        ex=heartbeat_ttl_seconds(settings),
    )


def clear_heartbeat(redis_client, settings: Any, *, owner_id: str | None = None) -> bool:
    """Clear our heartbeat, without deleting a newer worker's key."""

    key = heartbeat_key(settings)
    if owner_id is not None:
        try:
            raw = redis_client.get(key)
            if raw:
                payload = json.loads(raw)
                if payload.get("owner_id") != owner_id:
                    return False
        except Exception:  # noqa: BLE001 - best-effort cleanup on shutdown/failure
            return False
    try:
        return bool(redis_client.delete(key))
    except Exception:  # noqa: BLE001 - Redis failure must not crash cleanup
        return False


def read_heartbeat(redis_client, settings: Any) -> dict[str, Any]:
    """Return a UI/API-safe status object; never expose the owner identifier."""

    key = heartbeat_key(settings)
    try:
        ttl = int(redis_client.ttl(key))
        if ttl == -2:
            return {
                "status": "unavailable",
                "code": "BUILD_WORKER_NOT_READY",
                "message": "环境构建 Worker 尚未就绪或心跳已过期",
            }
        if ttl == -1 or ttl <= 0:
            return {
                "status": "unavailable",
                "code": "BUILD_WORKER_NOT_READY",
                "message": "环境构建 Worker 心跳无有效 TTL",
            }
        # Reading the value catches a partially-written/corrupt test or Redis
        # value while still keeping the payload private.
        raw = redis_client.get(key)
        if not raw:
            return {
                "status": "unavailable",
                "code": "BUILD_WORKER_NOT_READY",
                "message": "环境构建 Worker 心跳不可读",
            }
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return {
                "status": "unavailable",
                "code": "BUILD_WORKER_NOT_READY",
                "message": "环境构建 Worker 心跳格式无效",
            }
        if not isinstance(payload, dict) or not payload.get("owner_id"):
            return {
                "status": "unavailable",
                "code": "BUILD_WORKER_NOT_READY",
                "message": "环境构建 Worker 心跳格式无效",
            }
        return {
            "status": "healthy",
            "message": "环境构建 Worker 已连接数据库、Redis 和 Docker daemon",
            "ttl_seconds": ttl,
        }
    except Exception:  # noqa: BLE001 - readiness must degrade gracefully
        return {
            "status": "unavailable",
            "code": "BUILD_WORKER_NOT_READY",
            "message": "无法读取环境构建 Worker 心跳",
        }
