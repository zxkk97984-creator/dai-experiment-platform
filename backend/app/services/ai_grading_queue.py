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
    """处理失败：可重试→queued(重新入队)，否则→review_required。

    状态 CAS：只有仍为 running（当前 worker 认领）的 CodeGrade 才能被 fail——
    避免旧 Worker 的失败覆盖新 Worker 已完成的评分。
    """
    grade = db.get(CodeGrade, code_grade_id)
    if grade is None:
        return
    safe = _sanitize(error)
    current = grade.attempt_count
    now = datetime.now(timezone.utc)

    if retryable and current < max_attempts:
        result = db.execute(
            update(CodeGrade)
            .execution_options(synchronize_session=False)
            .where(CodeGrade.id == code_grade_id, CodeGrade.status == "running")
            .values(status="queued", last_error=safe, queued_at=now)
        )
        if result.rowcount == 0:
            db.rollback()
            return  # 已被并发 Worker 处理，不覆盖
        db.commit()
        db.expire_all()
        msg = json.dumps({"type": "ai_grade", "id": code_grade_id, "attempt": current + 1})
        redis_client.rpush(_ai_queue_name(), msg)
    else:
        result = db.execute(
            update(CodeGrade)
            .execution_options(synchronize_session=False)
            .where(CodeGrade.id == code_grade_id, CodeGrade.status == "running")
            .values(
                status="review_required", needs_teacher_review=True,
                review_reason=f"AI 评分失败（尝试 {current} 次）: {safe}",
                last_error=safe,
            )
        )
        if result.rowcount == 0:
            db.rollback()
            return  # 已被并发 Worker 处理，不覆盖
        db.commit()
        db.expire_all()
        # 考试 active CodeGrade：父级当场转 review_required（finalize 自身幂等/CAS）
        if grade.exam_answer_id:
            from app.models import ExamAnswer
            ans = db.get(ExamAnswer, grade.exam_answer_id)
            if ans:
                from app.services.exam_grading import finalize_if_ready
                finalize_if_ready(ans.submission_id, db)


def recover_stale_ai_grades(db: Session, redis_client: Redis) -> dict[str, int]:
    """恢复僵死任务：running/pending/queued 超时→重置并重新推送。

    关键：先 commit 状态变更，再 rpush Redis。避免消费者先收到消息却发现 DB 状态未更新导致 claim 失败。

    - running 超过 10 分钟→重置为 queued（保留原 attempt，不重复计数）
    - queued 超过 5 分钟→重新推送 Redis（DB 已 queued 但消息丢失）
    - pending 超过 2 分钟→直接转为 queued 并入队
    """
    recovered = {"running": 0, "queued": 0, "pending": 0}
    now = datetime.now(timezone.utc)
    qname = _ai_queue_name()

    # running 超时 → queued（CAS：仍 running 且 started_at 未变；先 commit 再 rpush）
    running_threshold = now - timedelta(seconds=STALE_RUNNING_SECONDS)
    stale_running = db.scalars(
        select(CodeGrade).where(
            CodeGrade.status == "running",
            CodeGrade.started_at < running_threshold,
        )
    ).all()
    for grade in stale_running:
        result = db.execute(
            update(CodeGrade)
            .execution_options(synchronize_session=False)
            .where(
                CodeGrade.id == grade.id,
                CodeGrade.status == "running",
                CodeGrade.started_at == grade.started_at,
            )
            .values(status="queued", last_error="Worker 超时未响应", queued_at=now)
        )
        if result.rowcount == 0:
            db.rollback()
            continue  # 已被并发实例恢复
        db.commit()  # 先持久化状态变更
        try:
            msg = json.dumps({"type": "ai_grade", "id": grade.id, "attempt": grade.attempt_count})
            redis_client.rpush(qname, msg)
        except Exception:
            logger.warning("Redis 推送失败（running→queued），等待下次恢复: grade=%s", grade.id)
        recovered["running"] += 1

    # queued 超时 → 重新推送（CAS：仍 queued 且 queued_at 未变，防重复推送）
    queued_threshold = now - timedelta(seconds=300)
    stale_queued = db.scalars(
        select(CodeGrade).where(
            CodeGrade.status == "queued",
            CodeGrade.queued_at < queued_threshold,
        )
    ).all()
    for grade in stale_queued:
        result = db.execute(
            update(CodeGrade)
            .execution_options(synchronize_session=False)
            .where(
                CodeGrade.id == grade.id,
                CodeGrade.status == "queued",
                CodeGrade.queued_at == grade.queued_at,
            )
            .values(queued_at=now)
        )
        if result.rowcount == 0:
            db.rollback()
            continue
        db.commit()  # 先持久化
        try:
            msg = json.dumps({"type": "ai_grade", "id": grade.id, "attempt": grade.attempt_count})
            redis_client.rpush(qname, msg)
        except Exception:
            logger.warning("Redis 推送失败（queued 重推），等待下次恢复: grade=%s", grade.id)
        recovered["queued"] += 1

    # pending 超时 → 转为 queued（CAS：仍 pending 且超时阈值）
    pending_threshold = now - timedelta(seconds=120)
    stale_pending = db.scalars(
        select(CodeGrade).where(
            CodeGrade.status == "pending",
            CodeGrade.created_at < pending_threshold,
        )
    ).all()
    for grade in stale_pending:
        result = db.execute(
            update(CodeGrade)
            .execution_options(synchronize_session=False)
            .where(
                CodeGrade.id == grade.id,
                CodeGrade.status == "pending",
                CodeGrade.created_at < pending_threshold,
            )
            .values(status="queued", queued_at=now)
        )
        if result.rowcount == 0:
            db.rollback()
            continue  # 已被并发实例恢复
        db.commit()  # 先持久化状态变更
        try:
            msg = json.dumps({"type": "ai_grade", "id": grade.id, "attempt": grade.attempt_count})
            redis_client.rpush(qname, msg)
        except Exception:
            logger.warning("Redis 推送失败（pending→queued），等待下次恢复: grade=%s", grade.id)
        recovered["pending"] += 1

    if any(recovered.values()):
        logger.info("stale_ai_recovery", extra=recovered)

    return recovered


def _sanitize(error: str) -> str:
    import re
    error = re.sub(r"Bearer\s+\S+", "Bearer ***", error)
    error = re.sub(r"sk-[a-zA-Z0-9]+", "sk-***", error)
    if len(error) > 1000:
        error = error[:1000]
    return error
