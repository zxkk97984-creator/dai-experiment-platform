"""考试最终评分——原子化汇总 + 父级 review_required 终态。

状态机（父级）：started -> submitted -> grading -> graded
                 grading -> review_required（自动评分终止，需人工处理）
                 review_required -> grading（仅显式受控重试）

公平性原则：任何配置/基础设施系统错误都不得自动按 0 分结算，
不创建 ExamGrade；父级转入 review_required 等待人工处理。
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import CodeGrade, ExamAnswer, ExamGrade, ExamSubmission

logger = logging.getLogger("dai.exam_grading")

NON_FINAL_STATUSES = ["pending", "queued", "running"]

# 答案/CodeGrade 状态 allowlist——未知状态一律视为不变量破坏，转父 review_required
ANSWER_KNOWN_STATUSES = ["pending", "queued", "running", "completed", "system_error"]
CODEGRADE_KNOWN_STATUSES = ["pending", "queued", "running", "completed", "review_required"]


class FinalizeOutcome(str, Enum):
    """结构化汇总结果分类——调用方不得再用含糊 bool 统计"""

    GRADED = "graded"                    # 全部可评分 → 父 graded + ExamGrade upsert
    WAITING = "waiting"                  # 仍有未完成答案/AI 评分，继续等待
    REVIEW_REQUIRED = "review_required"  # 自动评分终止，父转终态等待人工处理
    NOOP = "noop"                        # 父已终态或非 grading，无事可做


@dataclass
class FinalizeResult:
    """结构化汇总结果"""

    outcome: FinalizeOutcome
    submission_id: int
    reason: str | None = None


def finalize_if_ready(submission_id: int, db: Session) -> FinalizeResult:
    """原子化汇总父级考试提交。

    并发安全（SQLite/MySQL 通用）：状态转换一律用带旧状态守卫的条件 UPDATE，
    rowcount=1 才算真实转换，0 则视为已被并发实例转换（NOOP）。
    父行 FOR UPDATE 仅作为 MySQL 下的第一道防线（SQLite 忽略之，靠条件 UPDATE 兜底）。

    返回 FinalizeResult，调用方按 outcome 统计真实状态转换。
    """
    submission = db.scalar(
        select(ExamSubmission)
        .where(ExamSubmission.id == submission_id)
        .with_for_update()
    )
    if not submission:
        logger.warning("ExamSubmission %s 不存在", submission_id)
        return FinalizeResult(FinalizeOutcome.NOOP, submission_id, "提交不存在")
    if submission.status == "graded":
        return FinalizeResult(FinalizeOutcome.NOOP, submission_id, "已 graded")
    if submission.status == "review_required":
        return FinalizeResult(FinalizeOutcome.NOOP, submission_id, "已 review_required")
    if submission.status != "grading":
        return FinalizeResult(FinalizeOutcome.NOOP, submission_id, f"非 grading: {submission.status}")

    # 1. 非终态答案 → waiting（继续等待，绝不提前终态）
    waiting = db.scalar(
        select(ExamAnswer.id).where(
            ExamAnswer.submission_id == submission_id,
            ExamAnswer.grading_status.in_(NON_FINAL_STATUSES),
        ).limit(1)
    )
    if waiting is not None:
        return FinalizeResult(FinalizeOutcome.WAITING, submission_id, "存在未完成答案")

    # 2. active CodeGrade 未完成（非 review_required 终态）→ waiting
    cg_waiting = db.scalar(
        select(CodeGrade.id)
        .join(ExamAnswer, CodeGrade.exam_answer_id == ExamAnswer.id)
        .where(
            ExamAnswer.submission_id == submission_id,
            CodeGrade.mode == "active",
            CodeGrade.status.in_(NON_FINAL_STATUSES),
        )
        .limit(1)
    )
    if cg_waiting is not None:
        return FinalizeResult(FinalizeOutcome.WAITING, submission_id, "等待 AI 评分")

    # 3. 需要人工处理（公平性：不按 0 分结算，不创建 ExamGrade）
    #    3a. system_error 答案（已达终态但无有效分数）
    sys_err = db.scalar(
        select(ExamAnswer).where(
            ExamAnswer.submission_id == submission_id,
            ExamAnswer.grading_status == "system_error",
        ).limit(1)
    )
    #    3b. completed 但 score=NULL（active 等 AI 分，但 AI 已终止）
    null_score = db.scalar(
        select(ExamAnswer.id).where(
            ExamAnswer.submission_id == submission_id,
            ExamAnswer.grading_status == "completed",
            ExamAnswer.score == None,
        ).limit(1)
    )
    #    3c. active CodeGrade 处于 review_required（AI 自动终态）
    cg_review = db.scalar(
        select(CodeGrade.id)
        .join(ExamAnswer, CodeGrade.exam_answer_id == ExamAnswer.id)
        .where(
            ExamAnswer.submission_id == submission_id,
            CodeGrade.mode == "active",
            CodeGrade.status == "review_required",
        )
        .limit(1)
    )
    #    3d. 未知状态（不变量破坏）：不在 allowlist 的状态一律转父 review_required
    unknown_answer = db.scalar(
        select(ExamAnswer.id).where(
            ExamAnswer.submission_id == submission_id,
            ~ExamAnswer.grading_status.in_(ANSWER_KNOWN_STATUSES),
        ).limit(1)
    )
    unknown_cg = db.scalar(
        select(CodeGrade.id)
        .join(ExamAnswer, CodeGrade.exam_answer_id == ExamAnswer.id)
        .where(
            ExamAnswer.submission_id == submission_id,
            CodeGrade.mode == "active",
            ~CodeGrade.status.in_(CODEGRADE_KNOWN_STATUSES),
        )
        .limit(1)
    )
    if sys_err is not None or null_score is not None or cg_review is not None \
            or unknown_answer is not None or unknown_cg is not None:
        now = datetime.now(timezone.utc)
        reasons = []
        if sys_err is not None:
            reasons.append("存在系统错误答案")
        if null_score is not None:
            reasons.append("存在未完成评分（completed 但无分数）")
        if cg_review is not None:
            reasons.append("AI 评分终止需人工复核")
        if unknown_answer is not None:
            reasons.append("存在未知评分状态")
        if unknown_cg is not None:
            reasons.append("存在未知 AI 评分状态")
        reason = "；".join(reasons)
        # 条件 UPDATE：只有 status 仍为 grading 的实例才算真实转换
        result = db.execute(
            update(ExamSubmission).execution_options(synchronize_session=False)
            .where(ExamSubmission.id == submission_id, ExamSubmission.status == "grading")
            .values(status="review_required", review_reason=reason, review_required_at=now)
        )
        if result.rowcount == 0:
            db.rollback()
            return FinalizeResult(FinalizeOutcome.NOOP, submission_id, "已被并发转换")
        db.commit()
        logger.warning("ExamSubmission %s 转 review_required: %s", submission_id, reason)
        return FinalizeResult(FinalizeOutcome.REVIEW_REQUIRED, submission_id, reason)

    # 4. 全部可评分 → 求和、条件 UPDATE 父 graded、幂等 upsert ExamGrade
    total = db.scalar(
        select(func.sum(ExamAnswer.score)).where(
            ExamAnswer.submission_id == submission_id,
        )
    )
    total = float(total) if total is not None else 0.0

    now = datetime.now(timezone.utc)
    result = db.execute(
        update(ExamSubmission).execution_options(synchronize_session=False)
        .where(ExamSubmission.id == submission_id, ExamSubmission.status == "grading")
        .values(status="graded", score=total, graded_at=now)
    )
    if result.rowcount == 0:
        db.rollback()
        return FinalizeResult(FinalizeOutcome.NOOP, submission_id, "已被并发转换")

    existing_grade = db.scalar(
        select(ExamGrade).where(
            ExamGrade.exam_id == submission.exam_id,
            ExamGrade.student_id == submission.student_id,
        )
    )
    if existing_grade:
        existing_grade.score = total
    else:
        db.add(ExamGrade(exam_id=submission.exam_id, student_id=submission.student_id, score=total))
    db.commit()
    logger.info("Submission %s 汇总完成: score=%.1f", submission_id, total)
    return FinalizeResult(FinalizeOutcome.GRADED, submission_id, f"score={total}")
