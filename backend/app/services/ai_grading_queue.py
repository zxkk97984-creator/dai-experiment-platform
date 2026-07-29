"""AI 评分队列——DB 驱动、Redis 唤醒、幂等、恢复。所有 producer/retry/recovery/consumer 统一使用配置的 AI queue 名称。"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from redis import Redis
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CodeGrade

logger = logging.getLogger("dai.ai_queue")

STALE_RUNNING_SECONDS = 600  # 10 分钟


def _ai_queue_name() -> str:
    return get_settings().ai_queue_name


def enqueue_ai_grade(db: Session, redis_client: Redis, code_grade_id: int) -> bool:
    """将 pending CodeGrade 条件更新为 queued 并推送 Redis。幂等：非 pending 返回 False。

    先 commit 再 rpush——若 Redis 推送失败，stale recovery 会定期把孤立 queued 记录重新推送。
    """
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(CodeGrade)
        .where(CodeGrade.id == code_grade_id, CodeGrade.status == "pending")
        .values(status="queued", queued_at=now)
    )
    if result.rowcount == 0:
        return False
    msg = json.dumps({"type": "ai_grade", "id": code_grade_id, "attempt": 0})
    db.commit()
    try:
        redis_client.rpush(_ai_queue_name(), msg)
    except Exception:
        logger.warning("Redis 推送失败，queued 记录等待 stale recovery: grade=%s", code_grade_id)
    return True


def claim_ai_grade(db: Session, code_grade_id: int) -> bool:
    """条件更新 queued → running。非 queued 返回 False。"""
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(CodeGrade)
        .where(CodeGrade.id == code_grade_id, CodeGrade.status == "queued")
        .values(status="running", started_at=now, attempt_count=CodeGrade.attempt_count + 1)
    )
    db.commit()
    return result.rowcount > 0


def complete_ai_grade(db: Session, code_grade_id: int) -> None:
    """标记完成（仅 running → completed，不覆盖 review_required）"""
    now = datetime.now(timezone.utc)
    db.execute(
        update(CodeGrade)
        .where(CodeGrade.id == code_grade_id, CodeGrade.status == "running")
        .values(status="completed", finished_at=now)
    )
    db.commit()


def fail_ai_grade(
    db: Session, redis_client: Redis, code_grade_id: int,
    error: str, *, retryable: bool, max_attempts: int = 3,
) -> None:
    """处理失败：可重试→queued(重新入队)，否则→review_required。"""
    grade = db.get(CodeGrade, code_grade_id)
    if grade is None:
        return
    safe = _sanitize(error)
    current = grade.attempt_count
    now = datetime.now(timezone.utc)

    if retryable and current < max_attempts:
        db.execute(
            update(CodeGrade)
            .where(CodeGrade.id == code_grade_id)
            .values(status="queued", last_error=safe, queued_at=now)
        )
        db.commit()
        msg = json.dumps({"type": "ai_grade", "id": code_grade_id, "attempt": current + 1})
        redis_client.rpush(_ai_queue_name(), msg)
    else:
        db.execute(
            update(CodeGrade)
            .where(CodeGrade.id == code_grade_id)
            .values(
                status="review_required", needs_teacher_review=True,
                review_reason=f"AI 评分失败（尝试 {current} 次）: {safe}",
                last_error=safe,
            )
        )
        db.commit()


def recover_stale_ai_grades(db: Session, redis_client: Redis) -> dict[str, int]:
    """恢复僵死任务：running/pending/queued 超时→重置并重新推送。

    - running 超过 10 分钟→重置为 queued（保留原 attempt，不重复计数）
    - queued 超过 5 分钟→重新推送 Redis（DB 已 queued 但消息丢失）
    - pending 超过 2 分钟→直接转为 queued 并入队
    """
    recovered = {"running": 0, "queued": 0, "pending": 0}
    now = datetime.now(timezone.utc)
    qname = _ai_queue_name()

    # running 超时 → queued，保留原 attempt_count（claim 时不再 +1 是错的 —— claim 是 +1 没错，但 recover 不应该 +1）
    running_threshold = now - timedelta(seconds=STALE_RUNNING_SECONDS)
    stale_running = db.scalars(
        select(CodeGrade).where(
            CodeGrade.status == "running",
            CodeGrade.started_at < running_threshold,
        )
    ).all()
    for grade in stale_running:
        db.execute(
            update(CodeGrade)
            .where(CodeGrade.id == grade.id)
            .values(status="queued", last_error="Worker 超时未响应", queued_at=now)
        )
        msg = json.dumps({"type": "ai_grade", "id": grade.id, "attempt": grade.attempt_count})
        redis_client.rpush(qname, msg)
        recovered["running"] += 1

    # queued 超时 → 重新推送（消息可能丢失）
    queued_threshold = now - timedelta(seconds=300)
    stale_queued = db.scalars(
        select(CodeGrade).where(
            CodeGrade.status == "queued",
            CodeGrade.queued_at < queued_threshold,
        )
    ).all()
    for grade in stale_queued:
        msg = json.dumps({"type": "ai_grade", "id": grade.id, "attempt": grade.attempt_count})
        redis_client.rpush(qname, msg)
        db.execute(
            update(CodeGrade).where(CodeGrade.id == grade.id).values(queued_at=now)
        )
        recovered["queued"] += 1

    # pending 超时 → 直接转为 queued 并入队
    pending_threshold = now - timedelta(seconds=120)
    stale_pending = db.scalars(
        select(CodeGrade).where(
            CodeGrade.status == "pending",
            CodeGrade.created_at < pending_threshold,
        )
    ).all()
    for grade in stale_pending:
        db.execute(
            update(CodeGrade)
            .where(CodeGrade.id == grade.id)
            .values(status="queued", queued_at=now)
        )
        msg = json.dumps({"type": "ai_grade", "id": grade.id, "attempt": grade.attempt_count})
        redis_client.rpush(qname, msg)
        recovered["pending"] += 1

    if any(recovered.values()):
        db.commit()
        logger.info("stale_ai_recovery", extra=recovered)

    return recovered


def _sanitize(error: str) -> str:
    import re
    error = re.sub(r"Bearer\s+\S+", "Bearer ***", error)
    error = re.sub(r"sk-[a-zA-Z0-9]+", "sk-***", error)
    if len(error) > 1000:
        error = error[:1000]
    return error
