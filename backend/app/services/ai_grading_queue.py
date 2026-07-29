"""AI 评分队列——DB 驱动、Redis 唤醒、幂等、恢复"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from redis import Redis
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import CodeGrade

logger = logging.getLogger("dai.ai_queue")

STALE_RUNNING_SECONDS = 600  # 10 分钟


def enqueue_ai_grade(db: Session, redis_client: Redis, code_grade_id: int) -> bool:
    """将 pending CodeGrade 条件更新为 queued 并推送 Redis。幂等：非 pending 返回 False。"""
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
    redis_client.rpush("judge:ai:queue", msg)
    return True


def claim_ai_grade(db: Session, code_grade_id: int) -> bool:
    """条件更新 queued → running。非 queued（如 pending）返回 False。"""
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
        # 退回 queued 并推送 Redis（claim 要求 queued 状态）
        db.execute(
            update(CodeGrade)
            .where(CodeGrade.id == code_grade_id)
            .values(status="queued", last_error=safe, queued_at=now)
        )
        db.commit()
        msg = json.dumps({"type": "ai_grade", "id": code_grade_id, "attempt": current + 1})
        redis_client.rpush("judge:ai:queue", msg)
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
    """恢复僵死任务：running 超过 10 分钟→重置为 queued 并重新入队。"""
    recovered = {"running": 0}
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(seconds=STALE_RUNNING_SECONDS)

    stale = db.scalars(
        select(CodeGrade).where(
            CodeGrade.status == "running",
            CodeGrade.started_at < threshold,
        )
    ).all()

    for grade in stale:
        db.execute(
            update(CodeGrade)
            .where(CodeGrade.id == grade.id)
            .values(status="queued", last_error="Worker 超时未响应（stale running）",
                    queued_at=now, attempt_count=CodeGrade.attempt_count + 1)
        )
        msg = json.dumps({"type": "ai_grade", "id": grade.id, "attempt": grade.attempt_count})
        redis_client.rpush("judge:ai:queue", msg)
        recovered["running"] += 1

    if recovered["running"] > 0:
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
