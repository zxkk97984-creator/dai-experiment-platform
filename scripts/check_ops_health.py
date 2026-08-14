#!/usr/bin/env python3
"""TASK-029：最小运维健康检查——基于 Redis 指标计数器与 DB 队列事实，不依赖监控平台。

用法（后端环境内）：
    cd backend && python ../scripts/check_ops_health.py [--no-db]

输出报告；存在告警（含 DB/Redis 不可用）时退出码 1（供 cron/CI 使用）。
阈值可用环境变量覆盖：
    OPS_QUEUE_DEPTH_WARN（默认 100）
    OPS_QUEUE_OLDEST_AGE_SECONDS（默认 600）
    OPS_5XX_PER_HOUR（默认 50）
    OPS_JUDGE_FAILURES_PER_HOUR（默认 10）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import redis  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services.op_metrics import METRIC_NAMES, read  # noqa: E402


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"忽略非法环境变量 {name}={raw!r}，使用默认 {default}", file=sys.stderr)
        return default


def main() -> int:
    settings = get_settings()
    alerts: list[str] = []
    report: dict = {}

    # ── Redis：健康 + 计数器 + 队列深度 ──
    try:
        r = redis.Redis.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=2,
        )
        r.ping()
        report["redis"] = "ok"
        http_5xx = read(r, "http_requests_total", label="5xx")
        judge_permanent = read(r, "judge_failures_total", label="permanent")
        report["http_5xx_last_hour"] = http_5xx
        report["judge_failures_permanent_last_hour"] = judge_permanent
        report["judge_queue_depth"] = int(r.llen(settings.ai_queue_name))

        queue_warn = _env_int("OPS_QUEUE_DEPTH_WARN", 100)
        if report["judge_queue_depth"] > queue_warn:
            alerts.append(
                f"判题队列积压：深度 {report['judge_queue_depth']} > {queue_warn}"
            )
        fivexx_warn = _env_int("OPS_5XX_PER_HOUR", 50)
        if http_5xx > fivexx_warn:
            alerts.append(f"过去 1 小时 5xx 计数 {http_5xx} > {fivexx_warn}")
        judge_warn = _env_int("OPS_JUDGE_FAILURES_PER_HOUR", 10)
        if judge_permanent > judge_warn:
            alerts.append(
                f"过去 1 小时判题终态失败 {judge_permanent} > {judge_warn}"
            )
    except Exception as exc:
        report["redis"] = f"unavailable: {exc}"
        alerts.append(f"Redis 不可用: {exc}")

    # ── DB：健康 + 最老排队年龄 ──
    if "--no-db" in sys.argv:
        report["db"] = "skipped"
    else:
        try:
            from datetime import datetime, timezone

            from sqlalchemy import func, select

            from app.database import SessionLocal
            from app.models import CodeGrade

            with SessionLocal() as db:
                db.execute(select(1))
                oldest = db.scalar(
                    select(func.min(CodeGrade.queued_at)).where(
                        CodeGrade.status == "queued"
                    )
                )
            report["db"] = "ok"
            if oldest is not None:
                age = int((datetime.now(timezone.utc) - oldest).total_seconds())
                report["judge_queue_oldest_age_seconds"] = age
                age_warn = _env_int("OPS_QUEUE_OLDEST_AGE_SECONDS", 600)
                if age > age_warn:
                    alerts.append(f"判题队列最老等待 {age}s > {age_warn}s")
        except Exception as exc:
            report["db"] = f"unavailable: {exc}"
            alerts.append(f"MySQL 不可用: {exc}")

    # ── 报告 ──
    print("== 运维健康检查（TASK-029）==")
    for key, value in report.items():
        print(f"  {key}: {value}")
    if alerts:
        print("告警：")
        for line in alerts:
            print(f"  - {line}")
        return 1
    print("无告警。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
