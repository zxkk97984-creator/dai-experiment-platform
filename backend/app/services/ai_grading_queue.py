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

STALE_RUNNING_SECONDS = 600  # 10 分钟无心跳视为僵死


def enqueue_ai_grade(db: Session, redis_client: Redis, code_grade_id: int) -> bool:
    result = db.execute(
        update(CodeGrade)
        .where(CodeGrade.id == code_grade_id, CodeGrade.status == "pending")
        .values(status="queued", queued_at=datetime.now(timezone.utc))
    )
    if result.rowcount == 0:
        return False
    message = json.dumps({"type": "ai_grade", "id": code_grade_id, "attempt": 0})
    redis_client.rpush("judge:ai:queue", message)
    return True


def claim_ai_grade(db: Session, code_grade_id: int) -> bool:
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(CodeGrade)
        .where(CodeGrade.id == code_grade_id, CodeGrade.status == "queued")
        .values(status="running", started_at=now, attempt_count=CodeGrade.attempt_count + 1)
    )
    return result.rowcount > 0


def complete_ai_grade(db: Session, code_grade_id: int) -> None:
    now = datetime.now(timezone.utc)
    db.execute(
        update(CodeGrade)
        .where(CodeGrade.id == code_grade_id)
        .values(status="completed", finished_at=now)
    )
    db.commit()


def fail_ai_grade(
    db: Session,
    redis_client: Redis,
    code_grade_id: int,
    error: str,
    *,
    retryable: bool,
    max_attempts: int = 3,
) -> None:
    grade = db.get(CodeGrade, code_grade_id)
    if grade is None:
        return
    safe_error = _sanitize(error)
    current = grade.attempt_count

    if retryable and current < max_attempts:
        db.execute(
            update(CodeGrade)
            .where(CodeGrade.id == code_grade_id)
            .values(status="pending", last_error=safe_error)
        )
        db.commit()
        msg = json.dumps({"type": "ai_grade", "id": code_grade_id, "attempt": current + 1})
        redis_client.rpush("judge:ai:queue", msg)
    else:
        db.execute(
            update(CodeGrade)
            .where(CodeGrade.id == code_grade_id)
            .values(
                status="review_required",
                needs_teacher_review=True,
                review_reason=f"AI 评分失败（尝试 {current} 次）: {safe_error}",
                last_error=safe_error,
            )
        )
        db.commit()


def recover_stale_ai_grades(db: Session, redis_client: Redis) -> dict[str, int]:
    """恢复僵死 AI 评分任务——running 超过 10 分钟重置为 pending"""
    recovered = {"running": 0}
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(seconds=STALE_RUNNING_SECONDS)

    # 只恢复运行时间超过阈值的 running 任务
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
            .values(status="pending", last_error="Worker 超时未响应（stale running）")
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
