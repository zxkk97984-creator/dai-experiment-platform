"""考试最终评分——原子化汇总"""
import logging
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import CodeGrade, ExamAnswer, ExamGrade, ExamSubmission

logger = logging.getLogger("dai.exam_grading")

FINAL_STATUSES = ["completed", "system_error"]
NON_FINAL_STATUSES = ["pending", "queued", "running"]


def finalize_if_ready(submission_id: int, db: Session) -> bool:
    submission = db.scalar(
        select(ExamSubmission)
        .where(ExamSubmission.id == submission_id)
        .with_for_update()
    )
    if not submission:
        logger.warning("ExamSubmission %s 不存在", submission_id)
        return False
    if submission.status == "graded":
        return True
    if submission.status != "grading":
        return False

    # 阻塞检查：非终态答案 / score=None(等待AI) / 系统错误（不可作为零分结算）/ 未完成 active CodeGrade
    blocking = db.scalar(
        select(ExamAnswer.id).where(
            ExamAnswer.submission_id == submission_id,
            or_(
                ExamAnswer.grading_status.in_(NON_FINAL_STATUSES),
                ExamAnswer.grading_status == "system_error",
                ExamAnswer.score == None,
            )
        ).limit(1)
    )
    if blocking is not None:
        logger.debug("Submission %s 仍有未完成/等待AI的答案", submission_id)
        return False

    # active CodeGrade 门禁
    cg_blocking = db.scalar(
        select(CodeGrade.id)
        .join(ExamAnswer, CodeGrade.exam_answer_id == ExamAnswer.id)
        .where(
            ExamAnswer.submission_id == submission_id,
            CodeGrade.mode == "active",
            CodeGrade.status != "completed",
        )
        .limit(1)
    )
    if cg_blocking:
        logger.debug("Submission %s 等待 AI 评分完成", submission_id)
        return False

    # 计算总分
    total = db.scalar(
        select(func.sum(ExamAnswer.score)).where(
            ExamAnswer.submission_id == submission_id,
            ExamAnswer.grading_status.in_(FINAL_STATUSES),
        )
    )
    total = float(total) if total else 0.0

    now = datetime.now(timezone.utc)
    submission.score = total
    submission.status = "graded"
    submission.graded_at = now

    existing_grade = db.scalar(
        select(ExamGrade).where(
            ExamGrade.exam_id == submission.exam_id,
            ExamGrade.student_id == submission.student_id,
        )
    )
    if existing_grade:
        existing_grade.score = total
    else:
        grade = ExamGrade(exam_id=submission.exam_id, student_id=submission.student_id, score=total)
        db.add(grade)

    try:
        db.commit()
    except Exception:
        db.rollback()
        existing_grade = db.scalar(
            select(ExamGrade).where(
                ExamGrade.exam_id == submission.exam_id,
                ExamGrade.student_id == submission.student_id,
            )
        )
        if existing_grade:
            existing_grade.score = total
        sub2 = db.get(ExamSubmission, submission_id)
        if sub2:
            sub2.score = total
            sub2.status = "graded"
            sub2.graded_at = datetime.now(timezone.utc)
        db.commit()

    logger.info("Submission %s 汇总完成: score=%.1f", submission_id, total)
    return True
