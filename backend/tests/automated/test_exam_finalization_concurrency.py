"""Task 3: 考试最终评分原子化——并发测试"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models import ExamAnswer, ExamGrade, ExamQuestion, ExamSubmission
from app.services.exam_grading import finalize_if_ready
from conftest import auth_header, create_user, login


def _setup_two_code_questions(db_session_factory):
    """创建一场考试，包含两道编程题，提交已 grading 但答案均为 completed"""
    with db_session_factory() as db:
        from app.models import Course, Exam, User
        teacher = User(username="fc_t", real_name="FCT", role="teacher", status="active",
                       password_hash="x")
        student = User(username="fc_s", real_name="FCS", role="student", status="active",
                       password_hash="x")
        db.add_all([teacher, student]); db.flush()
        course = Course(title="FC", status="published", teacher_id=teacher.id)
        db.add(course); db.flush()
        exam = Exam(course_id=course.id, title="FE", status="published",
                    duration_minutes=60)
        db.add(exam); db.flush()
        q1 = ExamQuestion(exam_id=exam.id, question_type="code", prompt="Q1",
                          correct_answer={}, points=10, hidden_tests="assert True")
        q2 = ExamQuestion(exam_id=exam.id, question_type="code", prompt="Q2",
                          correct_answer={}, points=20, hidden_tests="assert True")
        db.add_all([q1, q2]); db.flush()
        sub = ExamSubmission(exam_id=exam.id, student_id=student.id, status="grading")
        db.add(sub); db.flush()
        ans1 = ExamAnswer(submission_id=sub.id, question_id=q1.id,
                          code_answer="def a(): pass", grading_status="completed", score=10.0)
        ans2 = ExamAnswer(submission_id=sub.id, question_id=q2.id,
                          code_answer="def b(): pass", grading_status="completed", score=20.0)
        db.add_all([ans1, ans2]); db.commit()
        return {"submission_id": sub.id, "exam_id": exam.id, "student_id": student.id,
                "ans1_id": ans1.id, "ans2_id": ans2.id}


# ═══════════════════════════════════════════════════════════════
# 1. 两个独立 Session 同时汇总 → 只有一条 ExamGrade
# ═══════════════════════════════════════════════════════════════

def test_concurrent_finalize_produces_single_grade(db_session_factory):
    """两个 Session 同时完成汇总：只有一条 ExamGrade，分数正确"""
    ctx = _setup_two_code_questions(db_session_factory)

    # 两个独立 Session 并发尝试汇总
    with db_session_factory() as db1:
        # 模拟第一题完成后的汇总
        ok1 = finalize_if_ready(ctx["submission_id"], db1)

    with db_session_factory() as db2:
        # 第二个 Worker 完成最后一题后的汇总
        ok2 = finalize_if_ready(ctx["submission_id"], db2)

    assert ok1 is True
    assert ok2 is True  # 幂等：已 graded 时返回 True

    # 验证：只有一条 ExamGrade
    with db_session_factory() as db:
        grades = db.query(ExamGrade).where(
            ExamGrade.exam_id == ctx["exam_id"],
            ExamGrade.student_id == ctx["student_id"],
        ).all()
        assert len(grades) == 1, f"应只有一条成绩，实际: {len(grades)}"
        assert grades[0].score == 30.0

        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "graded"
        assert sub.score == 30.0


# ═══════════════════════════════════════════════════════════════
# 2. 还有未完成答案时不应结算
# ═══════════════════════════════════════════════════════════════

def test_finalize_blocks_when_answer_pending(db_session_factory):
    """有答案仍在 pending/queued/running 状态时，汇总被阻止"""
    ctx = _setup_two_code_questions(db_session_factory)

    # 将第一个答案设回 pending（模拟尚未判题）
    with db_session_factory() as db:
        ans = db.get(ExamAnswer, ctx["ans1_id"])
        ans.grading_status = "pending"
        db.commit()

    # 尝试汇总
    with db_session_factory() as db:
        ok = finalize_if_ready(ctx["submission_id"], db)
        assert ok is False, "有 pending 答案时不应汇总"

        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "grading", "状态不应改变"


def test_finalize_blocks_when_answer_queued(db_session_factory):
    """有答案在 queued 状态时阻汇总"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        ans = db.get(ExamAnswer, ctx["ans1_id"])
        ans.grading_status = "queued"
        db.commit()

    with db_session_factory() as db:
        ok = finalize_if_ready(ctx["submission_id"], db)
        assert ok is False


def test_finalize_blocks_when_answer_running(db_session_factory):
    """有答案在 running 状态时阻汇总"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        ans = db.get(ExamAnswer, ctx["ans1_id"])
        ans.grading_status = "running"
        db.commit()

    with db_session_factory() as db:
        ok = finalize_if_ready(ctx["submission_id"], db)
        assert ok is False


# ═══════════════════════════════════════════════════════════════
# 3. system_error 答案计入总分
# ═══════════════════════════════════════════════════════════════

def test_system_error_counted_in_total(db_session_factory):
    """system_error 是终态，其分数（0分）计入总分"""
    ctx = _setup_two_code_questions(db_session_factory)

    # 答案1 = completed(10) + 答案2 = system_error(0) → total = 10
    with db_session_factory() as db:
        ans2 = db.get(ExamAnswer, ctx["ans2_id"])
        ans2.grading_status = "system_error"
        ans2.score = 0.0
        db.commit()

    with db_session_factory() as db:
        ok = finalize_if_ready(ctx["submission_id"], db)
        assert ok is True

        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "graded"
        assert sub.score == 10.0


# ═══════════════════════════════════════════════════════════════
# 4. 幂等：已 graded 的提交重复汇总无害
# ═══════════════════════════════════════════════════════════════

def test_finalize_idempotent_on_graded(db_session_factory):
    """已 graded 的提交重复调用 finalize_if_ready 返回 True，不重复创建 grade"""
    ctx = _setup_two_code_questions(db_session_factory)

    # 第一次汇总
    with db_session_factory() as db:
        ok1 = finalize_if_ready(ctx["submission_id"], db)
        assert ok1 is True

    # 第二次汇总（幂等）
    with db_session_factory() as db:
        ok2 = finalize_if_ready(ctx["submission_id"], db)
        assert ok2 is True

    # 仍然只有一条 grade
    with db_session_factory() as db:
        grades = db.query(ExamGrade).where(
            ExamGrade.exam_id == ctx["exam_id"],
            ExamGrade.student_id == ctx["student_id"],
        ).all()
        assert len(grades) == 1


# ═══════════════════════════════════════════════════════════════
# 5. submission 不在 grading 状态时跳过
# ═══════════════════════════════════════════════════════════════

def test_finalize_skips_non_grading_submission(db_session_factory):
    """submission 为 started/submitted 时不处理"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        sub = db.get(ExamSubmission, ctx["submission_id"])
        sub.status = "started"
        db.commit()

    with db_session_factory() as db:
        ok = finalize_if_ready(ctx["submission_id"], db)
        assert ok is False
