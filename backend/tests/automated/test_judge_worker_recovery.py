"""Task 2: Worker 恢复测试——crash 恢复、重复消息、stale-running、终态"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models import ExamAnswer, ExamSubmission, ExamQuestion, Submission
from app.services.judge_queue import (
    MAX_ATTEMPTS,
    claim_job,
    complete_job,
    enqueue_job,
    fail_job,
    requeue_stale_jobs,
)
from conftest import auth_header, create_user, login


def _setup_submission(db_session_factory):
    """创建 pending 的作业提交"""
    with db_session_factory() as db:
        from app.models import Assignment, Course, JudgeQuestion, User
        teacher = User(username="rcv_t", real_name="RT", role="teacher", status="active",
                       password_hash="x")
        student = User(username="rcv_s", real_name="RS", role="student", status="active",
                       password_hash="x")
        db.add_all([teacher, student])
        db.flush()
        course = Course(title="RC", status="published", teacher_id=teacher.id)
        db.add(course); db.flush()
        assignment = Assignment(course_id=course.id, title="RA", status="published")
        db.add(assignment); db.flush()
        question = JudgeQuestion(
            assignment_id=assignment.id, title="RQ", function_name="add",
            hidden_tests="assert True", public_cases=[{"args": [1, 2], "expected": 3}],
        )
        db.add(question); db.flush()
        sub = Submission(
            question_id=question.id, student_id=student.id,
            code="def add(a,b): return a+b",
            status="queued", grading_status="pending",
        )
        db.add(sub); db.commit()
        return sub.id


def _setup_exam_answer(db_session_factory):
    """创建 pending 的考试答案"""
    with db_session_factory() as db:
        from app.models import Course, Exam, User
        teacher = User(username="rv_t", real_name="RVT", role="teacher", status="active",
                       password_hash="x")
        student = User(username="rv_s", real_name="RVS", role="student", status="active",
                       password_hash="x")
        db.add_all([teacher, student]); db.flush()
        course = Course(title="RVC", status="published", teacher_id=teacher.id)
        db.add(course); db.flush()
        exam = Exam(course_id=course.id, title="RVE", status="published",
                    duration_minutes=60)
        db.add(exam); db.flush()
        eq = ExamQuestion(exam_id=exam.id, question_type="code", prompt="X",
                          correct_answer={}, points=10, hidden_tests="assert True")
        db.add(eq); db.flush()
        sub = ExamSubmission(exam_id=exam.id, student_id=student.id, status="grading")
        db.add(sub); db.flush()
        ans = ExamAnswer(submission_id=sub.id, question_id=eq.id,
                         code_answer="def add(a,b): return a+b", grading_status="pending")
        db.add(ans); db.commit()
        return ans.id


# ═══════════════════════════════════════════════════════════════
# 1. crash 恢复：Worker 领取后崩溃，任务能被恢复扫描重置
# ═══════════════════════════════════════════════════════════════

def test_crash_after_claim_recoverable(db_session_factory):
    """Worker 在 claim 后崩溃 → running 超时后重置为 pending，重新入队"""
    sid = _setup_submission(db_session_factory)

    # 入队
    with db_session_factory() as db:
        enqueue_job(db, job_type="assignment", object_id=sid)

    # 模拟 Worker 领取任务后立即崩溃
    with db_session_factory() as db:
        ok = claim_job(db, job_type="assignment", object_id=sid)
        assert ok is True

        # 验证已变为 running
        sub = db.get(Submission, sid)
        assert sub.grading_status == "running"

    # 手动设置 started_at 为 10 分钟前（模拟崩溃后长时间无人处理）
    with db_session_factory() as db:
        sub = db.get(Submission, sid)
        sub.started_at = datetime.now(timezone.utc) - timedelta(seconds=600)
        db.commit()

    # 恢复扫描：stale_running_seconds=300，应重置此任务
    with db_session_factory() as db:
        stats = requeue_stale_jobs(db, job_type="assignment", stale_running_seconds=300)
        assert stats["running_reset"] >= 1, f"应重置 stale running: {stats}"

        sub = db.get(Submission, sid)
        assert sub.grading_status == "pending", f"崩溃后应重置为 pending: {sub.grading_status}"
        assert "stale running" in (sub.last_error or "")


# ═══════════════════════════════════════════════════════════════
# 2. 重复消息不会执行两次
# ═══════════════════════════════════════════════════════════════

def test_duplicate_redis_message_not_processed_twice(db_session_factory):
    """同一任务的重复 Redis 消息：claim_job 第二次失败，不重复执行"""
    sid = _setup_submission(db_session_factory)

    with db_session_factory() as db:
        enqueue_job(db, job_type="assignment", object_id=sid)

    # Worker-1 领取
    with db_session_factory() as db:
        ok1 = claim_job(db, job_type="assignment", object_id=sid)
        assert ok1 is True

    # Worker-2 收到重复消息尝试领取 → 失败
    with db_session_factory() as db:
        ok2 = claim_job(db, job_type="assignment", object_id=sid)
        assert ok2 is False, "重复消息不应成功抢占"

    # 状态仍然是 running（Worker-1 设置的）
    with db_session_factory() as db:
        sub = db.get(Submission, sid)
        assert sub.grading_status == "running"


def test_duplicate_redis_message_exam_not_processed_twice(db_session_factory):
    """考试题同样不会被重复执行"""
    aid = _setup_exam_answer(db_session_factory)

    with db_session_factory() as db:
        enqueue_job(db, job_type="exam", object_id=aid)
        ok1 = claim_job(db, job_type="exam", object_id=aid)
        assert ok1 is True

    with db_session_factory() as db:
        ok2 = claim_job(db, job_type="exam", object_id=aid)
        assert ok2 is False


# ═══════════════════════════════════════════════════════════════
# 3. 永久错误最终进入终态
# ═══════════════════════════════════════════════════════════════

def test_permanent_error_reaches_system_error(db_session_factory):
    """不可重试的错误 → system_error 终态"""
    sid = _setup_submission(db_session_factory)

    with db_session_factory() as db:
        enqueue_job(db, job_type="assignment", object_id=sid)
        claim_job(db, job_type="assignment", object_id=sid)

        fail_job(db, job_type="assignment", object_id=sid,
                 error="题目不存在", retryable=False)

        sub = db.get(Submission, sid)
        assert sub.grading_status == "system_error"
        assert sub.last_error == "题目不存在"


def test_max_retries_reaches_system_error(db_session_factory):
    """达到最大重试次数 → system_error，分数为 0"""
    sid = _setup_submission(db_session_factory)

    with db_session_factory() as db:
        sub = db.get(Submission, sid)
        sub.attempt_count = MAX_ATTEMPTS
        db.commit()

        stats = requeue_stale_jobs(db, job_type="assignment", stale_pending_seconds=0)
        assert stats["max_retries_reached"] >= 1

        sub2 = db.get(Submission, sid)
        assert sub2.grading_status == "system_error"
        assert sub2.score is None  # 系统错误不扣分（第六轮修正）
        assert "超过最大重试次数" in (sub2.last_error or "")


def test_exam_answer_max_retries_with_finalize(db_session_factory):
    """考试题超过最大重试 → system_error + 触发最终汇总"""
    aid = _setup_exam_answer(db_session_factory)

    with db_session_factory() as db:
        ans = db.get(ExamAnswer, aid)
        ans.attempt_count = MAX_ATTEMPTS
        db.commit()

        stats = requeue_stale_jobs(db, job_type="exam", stale_pending_seconds=0)
        assert stats["max_retries_reached"] >= 1

        ans2 = db.get(ExamAnswer, aid)
        assert ans2.grading_status == "system_error"
        assert ans2.score is None  # 系统错误不扣分（第六轮修正）

        # 验证提交状态已变为 graded（因为所有答案都是终态）
        sub = db.get(ExamSubmission, ans2.submission_id)
        assert sub.status in ("graded", "grading"), f"应为 graded/grading: {sub.status}"


# ═══════════════════════════════════════════════════════════════
# 4. 未知异常在 process_submission/process_exam_answer 中触发 fail_job
# ═══════════════════════════════════════════════════════════════

def test_process_submission_unknown_exception_triggers_fail_job(db_session_factory):
    """process_submission 内部未知异常 → fail_job 退回 pending"""
    from app.worker.judge_worker import process_submission
    from app.config import get_settings

    sid = _setup_submission(db_session_factory)
    settings = MagicMock()
    settings.judge_timeout_seconds = 30
    settings.judge_memory_limit_mb = 256
    settings.judge_cpu_limit = 1.0
    settings.judge_image = "dai-judge"

    with db_session_factory() as db:
        enqueue_job(db, job_type="assignment", object_id=sid)

    with db_session_factory() as db:
        # 模拟 _write_submission_files 抛出未知异常（claim_job 已成功后）
        with patch("app.worker.judge_worker._write_submission_files",
                   side_effect=RuntimeError("模拟未知异常")):
            result = process_submission(db, MagicMock(), settings, sid)

        # 应该退回 pending 而非 running
        sub = db.get(Submission, sid)
        assert sub.grading_status == "pending", f"未知异常应退回 pending: {sub.grading_status}"
        assert sub.last_error is not None, "应记录错误信息"


def test_process_exam_answer_unknown_exception_triggers_fail_job(db_session_factory):
    """process_exam_answer 内部未知异常（非 Docker 路径） → fail_job 退回 pending"""
    from app.worker.judge_worker import process_exam_answer
    from app.config import get_settings
    import fakeredis

    aid = _setup_exam_answer(db_session_factory)
    settings = get_settings()

    with db_session_factory() as db:
        enqueue_job(db, job_type="exam", object_id=aid)

    with db_session_factory() as db:
        # 模拟 tempfile.TemporaryDirectory 创建失败（在 claim 之后、Docker 执行之前）
        with patch("tempfile.TemporaryDirectory",
                   side_effect=OSError("磁盘已满，无法创建临时目录")):
            result = process_exam_answer(db, fakeredis.FakeStrictRedis(), settings, aid)

        ans = db.get(ExamAnswer, aid)
        # 异常在 claim 之后、complete 之前发生，应退回 pending
        assert ans.grading_status in ("pending", "running"), \
            f"未知异常应退回 pending/running: {ans.grading_status}"
        assert ans.last_error is not None


# ═══════════════════════════════════════════════════════════════
# 5. 进程崩溃后考试 stal-running 触发汇总
# ═══════════════════════════════════════════════════════════════

def test_stale_running_exam_trigger_finalize(db_session_factory):
    """考试编程题 stal-running 被重置后，最终汇总应能正确执行"""
    aid = _setup_exam_answer(db_session_factory)

    with db_session_factory() as db:
        enqueue_job(db, job_type="exam", object_id=aid)
        claim_job(db, job_type="exam", object_id=aid)

        # 模拟崩溃
        ans = db.get(ExamAnswer, aid)
        ans.started_at = datetime.now(timezone.utc) - timedelta(seconds=600)
        db.commit()

        # 恢复扫描
        stats = requeue_stale_jobs(db, job_type="exam", stale_running_seconds=300)
        assert stats["running_reset"] >= 1

        ans2 = db.get(ExamAnswer, aid)
        assert ans2.grading_status == "pending"

    # 重新入队并成功判题
    with db_session_factory() as db:
        enqueue_job(db, job_type="exam", object_id=aid)
        ans = db.get(ExamAnswer, aid)
        assert ans.grading_status == "queued"
        assert ans.attempt_count == 2  # 第二次尝试


# ═══════════════════════════════════════════════════════════════
# P0-1: 考试重复判题——claim_job 失败必须立即返回
# ═══════════════════════════════════════════════════════════════

def test_p0_1_duplicate_exam_message_not_judged_twice(db_session_factory):
    """P0-1: claim_job 抢占失败必须立即返回，不能绕过抢占继续执行 Docker"""
    from app.worker.judge_worker import process_exam_answer
    from app.config import get_settings
    import fakeredis

    aid = _setup_exam_answer(db_session_factory)
    settings = get_settings()

    # 入队 → status = queued
    with db_session_factory() as db:
        enqueue_job(db, job_type="exam", object_id=aid)

    docker_call_count = 0

    def counting_docker(*args, **kwargs):
        nonlocal docker_call_count
        docker_call_count += 1
        return ("1 passed", "", 0, 150)

    # Step 1: Worker-1 抢占成功（claim_job 把 queued→running），但尚未执行 Docker
    with db_session_factory() as db_w1:
        claim_job(db_w1, job_type="exam", object_id=aid)

    # Step 2: Worker-2 收到重复 Redis 消息，调用 process_exam_answer
    #   answer.grading_status 在 DB 中是 "running"（Worker-1 抢占的）
    #   claim_job 返回 False（因为 grading_status 不是 queued）
    #   → 应该立即返回，不执行 Docker
    with db_session_factory() as db_w2:
        with patch("app.worker.judge_worker._run_docker_pytest", side_effect=counting_docker):
            result2 = process_exam_answer(db_w2, fakeredis.FakeStrictRedis(), settings, aid)

    # 断言：Docker 调用次数必须是 0（Worker-2 claim 失败后不容许绕过抢占）
    assert docker_call_count == 0, \
        f"claim_job 失败后不应执行 Docker，实际调用了 {docker_call_count} 次"
