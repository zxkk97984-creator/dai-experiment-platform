"""AI 评分队列——DB 驱动、Redis 唤醒、幂等、恢复"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from redis import Redis
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import CodeGrade

logger = logging.getLogger("dai.ai_queue")

_STALE_TIMEOUT_SECONDS = 600  # 10 分钟无心跳视为僵死


def enqueue_ai_grade(db: Session, redis_client: Redis, code_grade_id: int) -> bool:
    """将 pending CodeGrade 条件更新为 queued 并推 Redis 通知"""
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
    """条件更新 queued → running"""
    result = db.execute(
        update(CodeGrade)
        .where(CodeGrade.id == code_grade_id, CodeGrade.status == "queued")
        .values(
            status="running",
            started_at=datetime.now(timezone.utc),
            attempt_count=CodeGrade.attempt_count + 1,
        )
    )
    return result.rowcount > 0


def complete_ai_grade(db: Session, code_grade_id: int) -> None:
    """标记 AI 评分为完成"""
    db.execute(
        update(CodeGrade)
        .where(CodeGrade.id == code_grade_id)
        .values(status="completed", finished_at=datetime.now(timezone.utc))
    )


def fail_ai_grade(
    db: Session,
    redis_client: Redis,
    code_grade_id: int,
    error: str,
    *,
    retryable: bool,
    max_attempts: int = 3,
) -> None:
    """处理 AI 评分失败——可重试则退回 pending，否则进入 review_required"""
    grade = db.get(CodeGrade, code_grade_id)
    if grade is None:
        return

    safe_error = sanitize_ai_error(error)
    current_attempts = grade.attempt_count

    if retryable and current_attempts < max_attempts:
        db.execute(
            update(CodeGrade)
            .where(CodeGrade.id == code_grade_id)
            .values(status="pending", last_error=safe_error)
        )
        # 重试消息
        message = json.dumps({"type": "ai_grade", "id": code_grade_id, "attempt": current_attempts + 1})
        redis_client.rpush("judge:ai:queue", message)
    else:
        db.execute(
            update(CodeGrade)
            .where(CodeGrade.id == code_grade_id)
            .values(
                status="review_required",
                needs_teacher_review=True,
                review_reason=f"AI 评分失败（尝试 {current_attempts} 次）: {safe_error}",
                last_error=safe_error,
            )
        )


def recover_stale_ai_grades(db: Session, redis_client: Redis) -> dict[str, int]:
    """恢复僵死的 AI 评分任务"""
    recovered = {"pending": 0, "queued": 0, "running": 0}
    now = datetime.now(timezone.utc)

    # 恢复 pending（长时间未处理）
    # pending 状态不需要恢复，它们尚未被领取

    # 恢复 stale queued（10 分钟未开始）
    # 将 stale queued 重置为 pending
    # 简化实现：不做复杂时间判断，只在 Worker 启动时恢复所有运行中任务
    stale_running = db.scalars(
        select(CodeGrade).where(
            CodeGrade.status == "running",
            CodeGrade.started_at < now,
        )
    ).all()

    for grade in stale_running:
        # 简单策略：重置为 pending 重试
        db.execute(
            update(CodeGrade)
            .where(CodeGrade.id == grade.id)
            .values(status="pending")
        )
        message = json.dumps({"type": "ai_grade", "id": grade.id, "attempt": grade.attempt_count})
        redis_client.rpush("judge:ai:queue", message)
        recovered["running"] += 1

    return recovered


def sanitize_ai_error(error: str) -> str:
    """删除错误消息中的敏感信息"""
    import re
    error = re.sub(r"Bearer\s+\S+", "Bearer ***", error)
    error = re.sub(r"sk-[a-zA-Z0-9]+", "sk-***", error)
    # 截断
    if len(error) > 1000:
        error = error[:1000]
    return error
