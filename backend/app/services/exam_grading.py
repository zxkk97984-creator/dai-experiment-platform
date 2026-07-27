"""考试最终评分——原子化汇总，所有变更在单一事务内完成。

使用 SELECT ... FOR UPDATE 锁定 ExamSubmission，在锁内：
1. 重新检查所有答案均为终态（completed/system_error）
2. 计算总分
3. 写入 ExamGrade（upsert）
4. 更新 submission.score/status/graded_at

保证：任何并发 Worker 只能产生一份成绩记录。
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ExamAnswer, ExamGrade, ExamSubmission

logger = logging.getLogger("dai.exam_grading")

# 终态：这些状态的答案计入总分
FINAL_STATUSES = ["completed", "system_error"]

# 非终态：任一存在则禁止结算
NON_FINAL_STATUSES = ["pending", "queued", "running"]


def finalize_if_ready(submission_id: int, db: Session) -> bool:
    """检查是否所有答案均已完成，是则在单个事务内生成最终成绩。

    返回 True 表示已汇总（或已经 graded），False 表示还有答案未完成。

    并发安全：
        使用 SELECT ... FOR UPDATE 锁定 ExamSubmission 行。
        锁内重新检查所有答案状态，确保多 Worker 并发时只有一方执行汇总。
    """
    # 锁定提交行（MySQL 下阻止并发汇总）
    submission = db.scalar(
        select(ExamSubmission)
        .where(ExamSubmission.id == submission_id)
        .with_for_update()
    )

    if not submission:
        logger.warning("ExamSubmission %s 不存在，无法汇总", submission_id)
        return False

    if submission.status == "graded":
        # 已评分，幂等返回
        return True

    if submission.status != "grading":
        # 不是 grading 状态，不处理
        return False

    # 锁内检查：有任何非终态答案 → 不能汇总
    unfinished = db.scalar(
        select(ExamAnswer).where(
            ExamAnswer.submission_id == submission_id,
            ExamAnswer.grading_status.in_(NON_FINAL_STATUSES),
        ).limit(1)
    )
    if unfinished:
        logger.debug("Submission %s 仍有未完成答案，跳过汇总", submission_id)
        return False

    # 计算总分（只计算终态答案）
    total = db.scalar(
        select(func.sum(ExamAnswer.score)).where(
            ExamAnswer.submission_id == submission_id,
            ExamAnswer.grading_status.in_(FINAL_STATUSES),
        )
    )
    total = float(total) if total else 0.0

    # 更新 submission
    now = datetime.now(timezone.utc)
    submission.score = total
    submission.status = "graded"
    submission.graded_at = now

    # ExamGrade upsert：先尝试更新已有记录，不存在则插入
    existing_grade = db.scalar(
        select(ExamGrade).where(
            ExamGrade.exam_id == submission.exam_id,
            ExamGrade.student_id == submission.student_id,
        )
    )

    if existing_grade:
        existing_grade.score = total
        logger.info("更新已有成绩: exam=%s student=%s score=%.1f",
                     submission.exam_id, submission.student_id, total)
    else:
        grade = ExamGrade(
            exam_id=submission.exam_id,
            student_id=submission.student_id,
            score=total,
        )
        db.add(grade)
        logger.info("新建成绩: exam=%s student=%s score=%.1f",
                     submission.exam_id, submission.student_id, total)

    # 单一事务提交：submission + grade 一起落库
    db.commit()
    logger.info("Submission %s 汇总完成：score=%.1f", submission_id, total)
    return True
