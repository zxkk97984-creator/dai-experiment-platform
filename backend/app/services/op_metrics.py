"""TASK-029（F-36）：最小运维指标——固定指标集 + Redis 计数器，不绑定监控厂商。

设计约束：
- 指标名与标签值均为固定白名单（防高基数：绝不把用户 id/题目 id/路径原文当标签）；
- Redis 故障时静默降级（指标绝不阻断业务路径）；
- 窗口按整点小时，保留 25 小时；读取方（/metrics 等）只取当前小时。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger("dai.op_metrics")

RETENTION_HOURS = 25

# 固定指标名：新增指标必须在此登记（拒绝任意名称，防高基数/注入）
METRIC_NAMES = {
    "http_requests_total",          # 标签：2xx/3xx/4xx/5xx
    "http_latency_ms_sum",          # 标签：2xx/3xx/4xx/5xx（配合 requests 求平均）
    "judge_failures_total",         # 标签：permanent/retryable
    "ai_requests_total",            # 标签：ai_grading/rubric_generation/test_group_generation
    "ai_prompt_tokens_total",       # 标签：同上
    "ai_completion_tokens_total",   # 标签：同上
}

# 固定标签值：按指标名分组白名单
ALLOWED_LABELS: dict[str, set[str]] = {
    "http_requests_total": {"2xx", "3xx", "4xx", "5xx"},
    "http_latency_ms_sum": {"2xx", "3xx", "4xx", "5xx"},
    "judge_failures_total": {"permanent", "retryable"},
    "ai_requests_total": {"ai_grading", "rubric_generation", "test_group_generation"},
    "ai_prompt_tokens_total": {"ai_grading", "rubric_generation", "test_group_generation"},
    "ai_completion_tokens_total": {"ai_grading", "rubric_generation", "test_group_generation"},
}

_metrics_redis = None  # 惰性单例；模块级缓存避免每请求新建连接


def get_metrics_redis():
    """惰性 Redis 客户端；不可用返回 None（调用方 no-op）。"""
    global _metrics_redis
    if _metrics_redis is None:
        try:
            import redis as _redis

            from app.config import get_settings

            _metrics_redis = _redis.Redis.from_url(
                get_settings().redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            )
        except Exception as exc:  # pragma: no cover - 环境问题
            logger.warning("指标 Redis 初始化失败，指标降级为 no-op: %s", exc)
            return None
    return _metrics_redis


def _window() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d%H")


def record(redis_client, name: str, value: int = 1, *, label: str | None = None) -> None:
    """指标自增。名称/标签不在白名单 → 拒绝（记警告，不落库）。

    绝不抛出——指标路径不能影响业务。
    """
    if name not in METRIC_NAMES:
        logger.warning("拒绝未登记指标名: %r", name)
        return
    allowed = ALLOWED_LABELS[name]
    if (label or "") not in allowed:
        logger.warning("拒绝指标 %s 的未登记标签: %r", name, label)
        return
    try:
        key = f"opmetrics:{name}:{label}:{_window()}"
        redis_client.incrby(key, value)
        redis_client.expire(key, RETENTION_HOURS * 3600)
    except Exception as exc:
        logger.debug("指标写入失败（降级 no-op）: %s", exc)


def read(redis_client, name: str, *, label: str | None = None) -> int:
    """读取当前窗口计数；异常返回 0。"""
    if name not in METRIC_NAMES:
        return 0
    try:
        raw = redis_client.get(f"opmetrics:{name}:{label}:{_window()}")
        return int(raw or 0)
    except Exception:
        return 0


def snapshot(redis_client) -> dict[str, dict[str, int]]:
    """当前窗口全量快照（/metrics 端点用）。"""
    result: dict[str, dict[str, int]] = {}
    for name in sorted(METRIC_NAMES):
        result[name] = {
            label: read(redis_client, name, label=label)
            for label in sorted(ALLOWED_LABELS[name])
        }
    return result


def http_metrics_recorder():
    """给 API 中间件用的记录函数：记录状态类别计数与延迟（每次调用时惰性取 Redis）。"""

    def _record(status_class: str, latency_ms: float) -> None:
        redis_client = get_metrics_redis()
        if redis_client is None:
            return
        record(redis_client, "http_requests_total", label=status_class)
        record(redis_client, "http_latency_ms_sum", int(latency_ms), label=status_class)

    return _record


def ai_metrics_sink():
    """给 DeepSeekClient 的 metrics_sink：按操作累加 token 计数与调用次数。"""

    def _sink(data: dict) -> None:
        redis_client = get_metrics_redis()
        if redis_client is None:
            return
        operation = data.get("operation", "")
        if operation not in ALLOWED_LABELS["ai_requests_total"]:
            return
        record(redis_client, "ai_requests_total", label=operation)
        if data.get("prompt_tokens"):
            record(redis_client, "ai_prompt_tokens_total", int(data["prompt_tokens"]), label=operation)
        if data.get("completion_tokens"):
            record(redis_client, "ai_completion_tokens_total", int(data["completion_tokens"]), label=operation)

    return _sink


def queue_depth(redis_client, queue_name: str) -> int:
    """Redis 队列当前深度；异常返回 -1（调用方显式报告不可用）。"""
    try:
        return int(redis_client.llen(queue_name))
    except Exception:
        return -1
