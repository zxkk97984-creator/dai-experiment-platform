"""考试最终评分结构化 finalize——并发测试 + 父级 review_required 终态语义。

新语义（FinalizeOutcome）：
- graded：全部可评分 → 父 graded + 幂等 ExamGrade
- waiting：pending/queued/running 答案或 active CodeGrade 未完成
- review_required：system_error / completed+NULL / active CodeGrade review_required → 父转终态，无 ExamGrade
- noop：父已 graded / review_required / 非 grading
"""
from datetime import datetime, timezone

from app.models import CodeGrade, ExamAnswer, ExamGrade, ExamQuestion, ExamSubmission
from app.services.exam_grading import finalize_if_ready, FinalizeOutcome


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
                "ans1_id": ans1.id, "ans2_id": ans2.id, "q2_id": q2.id}


def _count_grades(db_session_factory, ctx):
    with db_session_factory() as db:
        return db.query(ExamGrade).where(
            ExamGrade.exam_id == ctx["exam_id"],
            ExamGrade.student_id == ctx["student_id"],
        ).all()


# ═══════════════════════════════════════════════════════════════
# 1. 正常汇总：graded + 幂等
# ═══════════════════════════════════════════════════════════════

def test_concurrent_finalize_produces_single_grade(db_session_factory):
    """两个 Session 同时汇总：只有一条 ExamGrade，分数正确"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db1:
        r1 = finalize_if_ready(ctx["submission_id"], db1)

    with db_session_factory() as db2:
        r2 = finalize_if_ready(ctx["submission_id"], db2)

    assert r1.outcome == FinalizeOutcome.GRADED
    assert r2.outcome == FinalizeOutcome.NOOP  # 已 graded 幂等

    grades = _count_grades(db_session_factory, ctx)
    assert len(grades) == 1, f"应只有一条成绩，实际: {len(grades)}"
    assert grades[0].score == 30.0

    with db_session_factory() as db:
        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "graded"
        assert sub.score == 30.0


# ═══════════════════════════════════════════════════════════════
# 2. 未完成答案：waiting
# ═══════════════════════════════════════════════════════════════

def test_finalize_waiting_when_answer_pending(db_session_factory):
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        ans = db.get(ExamAnswer, ctx["ans1_id"])
        ans.grading_status = "pending"
        db.commit()

    with db_session_factory() as db:
        r = finalize_if_ready(ctx["submission_id"], db)
        assert r.outcome == FinalizeOutcome.WAITING, f"应有 pending 答案时 waiting: {r}"
        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "grading", "状态不应改变"


def test_finalize_waiting_when_answer_queued(db_session_factory):
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        ans = db.get(ExamAnswer, ctx["ans1_id"])
        ans.grading_status = "queued"
        db.commit()

    with db_session_factory() as db:
        r = finalize_if_ready(ctx["submission_id"], db)
        assert r.outcome == FinalizeOutcome.WAITING


def test_finalize_waiting_when_answer_running(db_session_factory):
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        ans = db.get(ExamAnswer, ctx["ans1_id"])
        ans.grading_status = "running"
        db.commit()

    with db_session_factory() as db:
        r = finalize_if_ready(ctx["submission_id"], db)
        assert r.outcome == FinalizeOutcome.WAITING


def test_finalize_waiting_when_active_codegrade_incomplete(db_session_factory):
    """active CodeGrade 仍在 running/queued/pending 时 → waiting（不提前终态）"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        from app.models import QuestionRubric
        rubric = QuestionRubric(exam_question_id=ctx["q2_id"], version=1, status="locked",
                                source_hash="h", source_snapshot={}, rubric_json={},
                                model_name="m", locked_at=datetime.now(timezone.utc))
        db.add(rubric); db.flush()
        cg = CodeGrade(exam_answer_id=ctx["ans2_id"], rubric_id=rubric.id,
                       mode="active", status="running",
                       functional_score=60, robustness_score=10)
        db.add(cg); db.commit()

    with db_session_factory() as db:
        r = finalize_if_ready(ctx["submission_id"], db)
        assert r.outcome == FinalizeOutcome.WAITING, f"active CodeGrade 未完成应 waiting: {r}"
        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "grading"


# ═══════════════════════════════════════════════════════════════
# 3. 系统错误 / 不完整终态 → 父级 review_required（公平性：不按 0 分结算）
# ═══════════════════════════════════════════════════════════════

def test_system_error_triggers_parent_review_required(db_session_factory):
    """system_error 答案 → 父转 review_required，不创建 ExamGrade，不按 0 分结算"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        ans2 = db.get(ExamAnswer, ctx["ans2_id"])
        ans2.grading_status = "system_error"
        ans2.score = None
        ans2.last_error = "缺少隐藏测试"
        db.commit()

    with db_session_factory() as db:
        r = finalize_if_ready(ctx["submission_id"], db)
        assert r.outcome == FinalizeOutcome.REVIEW_REQUIRED, f"系统错误应转 review_required: {r}"

        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "review_required"
        assert sub.review_required_at is not None, "应记录转人工时间"
        assert sub.review_reason and "系统错误" in sub.review_reason, "应记录脱敏原因"

        # 子答案保持 system_error/score=NULL，不被覆盖
        ans2b = db.get(ExamAnswer, ctx["ans2_id"])
        assert ans2b.grading_status == "system_error"
        assert ans2b.score is None

    assert _count_grades(db_session_factory, ctx) == [], "系统错误不得创建 ExamGrade"


def test_completed_null_score_triggers_parent_review_required(db_session_factory):
    """completed 但 score=NULL（active 等待 AI 分但 AI 终止）→ 父 review_required"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        ans2 = db.get(ExamAnswer, ctx["ans2_id"])
        ans2.grading_status = "completed"
        ans2.score = None
        db.commit()

    with db_session_factory() as db:
        r = finalize_if_ready(ctx["submission_id"], db)
        assert r.outcome == FinalizeOutcome.REVIEW_REQUIRED
        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "review_required"

    assert _count_grades(db_session_factory, ctx) == []


def test_unknown_answer_status_triggers_review_required(db_session_factory):
    """未知 ExamAnswer 状态（allowlist 外，如 bogus）→ 父 review_required，不按分数 graded"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        ans2 = db.get(ExamAnswer, ctx["ans2_id"])
        ans2.grading_status = "bogus"
        ans2.score = 10.0  # 有分也不能 graded——状态不变量优先
        db.commit()

    with db_session_factory() as db:
        r = finalize_if_ready(ctx["submission_id"], db)
        assert r.outcome == FinalizeOutcome.REVIEW_REQUIRED, \
            f"未知状态应转 review_required: {r}"
        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "review_required"
        assert "未知评分状态" in (sub.review_reason or ""), "reason 应脱敏且描述不变量破坏"

    assert _count_grades(db_session_factory, ctx) == [], "未知状态不得创建 ExamGrade"


def test_unknown_codegrade_status_triggers_review_required(db_session_factory):
    """未知 active CodeGrade 状态 → 父 review_required"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        from app.models import QuestionRubric
        rubric = QuestionRubric(exam_question_id=ctx["q2_id"], version=1, status="locked",
                                source_hash="h", source_snapshot={}, rubric_json={},
                                model_name="m", locked_at=datetime.now(timezone.utc))
        db.add(rubric); db.flush()
        cg = CodeGrade(exam_answer_id=ctx["ans2_id"], rubric_id=rubric.id,
                       mode="active", status="bogus",
                       functional_score=60, robustness_score=10)
        db.add(cg); db.commit()

    with db_session_factory() as db:
        r = finalize_if_ready(ctx["submission_id"], db)
        assert r.outcome == FinalizeOutcome.REVIEW_REQUIRED
        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "review_required"
        assert "未知 AI 评分状态" in (sub.review_reason or "")

    assert _count_grades(db_session_factory, ctx) == []


def test_active_codegrade_review_required_triggers_parent(db_session_factory):
    """active CodeGrade 处于 review_required → 父转 review_required（同一父级缺口）"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        from app.models import QuestionRubric
        rubric = QuestionRubric(exam_question_id=ctx["q2_id"], version=1, status="locked",
                                source_hash="h", source_snapshot={}, rubric_json={},
                                model_name="m", locked_at=datetime.now(timezone.utc))
        db.add(rubric); db.flush()
        cg = CodeGrade(exam_answer_id=ctx["ans2_id"], rubric_id=rubric.id,
                       mode="active", status="review_required",
                       needs_teacher_review=True, review_reason="AI 评分失败",
                       functional_score=60, robustness_score=10)
        db.add(cg); db.commit()

    with db_session_factory() as db:
        r = finalize_if_ready(ctx["submission_id"], db)
        assert r.outcome == FinalizeOutcome.REVIEW_REQUIRED, f"active CodeGrade review_required 应转父: {r}"
        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "review_required"

    assert _count_grades(db_session_factory, ctx) == []


# ═══════════════════════════════════════════════════════════════
# 4. 幂等与 noop
# ═══════════════════════════════════════════════════════════════

def test_finalize_noop_on_graded(db_session_factory):
    """已 graded 的提交重复调用返回 noop，不重复创建 grade"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        r1 = finalize_if_ready(ctx["submission_id"], db)
        assert r1.outcome == FinalizeOutcome.GRADED

    with db_session_factory() as db:
        r2 = finalize_if_ready(ctx["submission_id"], db)
        assert r2.outcome == FinalizeOutcome.NOOP

    assert len(_count_grades(db_session_factory, ctx)) == 1


def test_finalize_noop_on_review_required(db_session_factory):
    """已 review_required 的父提交不再重复转换（扫描噪声停止）"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        ans2 = db.get(ExamAnswer, ctx["ans2_id"])
        ans2.grading_status = "system_error"
        ans2.score = None
        db.commit()

    with db_session_factory() as db:
        r1 = finalize_if_ready(ctx["submission_id"], db)
        assert r1.outcome == FinalizeOutcome.REVIEW_REQUIRED

    with db_session_factory() as db:
        r2 = finalize_if_ready(ctx["submission_id"], db)
        assert r2.outcome == FinalizeOutcome.NOOP, "review_required 后应 noop"

        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "review_required"
        assert sub.review_required_at is not None  # 不重复刷新


def test_finalize_skips_non_grading_submission(db_session_factory):
    """submission 为 started/submitted 时不处理（noop）"""
    ctx = _setup_two_code_questions(db_session_factory)

    with db_session_factory() as db:
        sub = db.get(ExamSubmission, ctx["submission_id"])
        sub.status = "started"
        db.commit()

    with db_session_factory() as db:
        r = finalize_if_ready(ctx["submission_id"], db)
        assert r.outcome == FinalizeOutcome.NOOP


# ═══════════════════════════════════════════════════════════════
# 5. 真并发：graded 只一条 / review_required 只转换一次
# ═══════════════════════════════════════════════════════════════

def test_p1_5_true_concurrent_finalize_single_grade(db_session_factory):
    """两个线程真并发执行 finalize：只产生一条成绩，outcome 恰好 graded+noop"""
    import threading

    ctx = _setup_two_code_questions(db_session_factory)
    results = []
    barrier = threading.Barrier(2, timeout=5)
    errors = []

    def do_finalize(worker_name):
        try:
            with db_session_factory() as db:
                barrier.wait()
                r = finalize_if_ready(ctx["submission_id"], db)
                results.append((worker_name, r.outcome))
        except Exception as e:
            errors.append((worker_name, str(e)))

    t1 = threading.Thread(target=do_finalize, args=("worker-1",))
    t2 = threading.Thread(target=do_finalize, args=("worker-2",))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert len(errors) == 0, f"并发汇总出错: {errors}"
    assert len(results) == 2, f"两个 Worker 都应完成: {results}"
    outcomes = sorted(r for _, r in results)
    assert outcomes == [FinalizeOutcome.GRADED, FinalizeOutcome.NOOP], \
        f"应恰好一个 graded 一个 noop: {results}"

    grades = _count_grades(db_session_factory, ctx)
    assert len(grades) == 1
    assert grades[0].score == 30.0

    with db_session_factory() as db:
        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "graded"


def test_concurrent_review_required_transition_once(db_session_factory):
    """两个线程并发触发 review_required：父只转换一次，只记一次原因"""
    import threading

    ctx = _setup_two_code_questions(db_session_factory)
    with db_session_factory() as db:
        ans2 = db.get(ExamAnswer, ctx["ans2_id"])
        ans2.grading_status = "system_error"
        ans2.score = None
        db.commit()

    results = []
    barrier = threading.Barrier(2, timeout=5)
    errors = []

    def do_finalize(worker_name):
        try:
            with db_session_factory() as db:
                barrier.wait()
                r = finalize_if_ready(ctx["submission_id"], db)
                results.append((worker_name, r.outcome))
        except Exception as e:
            errors.append((worker_name, str(e)))

    t1 = threading.Thread(target=do_finalize, args=("w1",))
    t2 = threading.Thread(target=do_finalize, args=("w2",))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert len(errors) == 0, f"并发转换出错: {errors}"
    outcomes = sorted(r for _, r in results)
    assert outcomes == [FinalizeOutcome.NOOP, FinalizeOutcome.REVIEW_REQUIRED], \
        f"应恰好一次转换: {results}"

    with db_session_factory() as db:
        sub = db.get(ExamSubmission, ctx["submission_id"])
        assert sub.status == "review_required"
        assert sub.review_required_at is not None

    assert _count_grades(db_session_factory, ctx) == []
