"""第三轮回归测试——P0 问题：缺配置/缺Rubric→系统错误、越权、考试结算"""
import pytest


# ── P0: 缺配置/缺Rubric → 系统错误不扣分 ──

def test_v1_without_test_groups_system_error(db_session_factory):
    """非 legacy 无测试组→系统错误（score 不覆盖）"""
    from app.models import JudgeQuestion, Submission
    from app.services.judge_queue import enqueue_job

    with db_session_factory() as db:
        q = JudgeQuestion(assignment_id=1, title="Q", function_name="f",
                          hidden_tests="def test(): assert True",
                          grading_mode="shadow", test_groups=[])
        db.add(q); db.flush()
        sub = Submission(question_id=q.id, student_id=1, code="def f(): pass",
                         status="queued", grading_status="pending")
        db.add(sub); db.commit()
        enqueue_job(db, job_type="assignment", object_id=sub.id)

    from app.config import Settings
    from app.worker.judge_worker import process_submission

    settings = Settings(_env_file=None, judge_use_docker=False, judge_timeout_seconds=5)
    with db_session_factory() as db:
        result = process_submission(db, None, settings, sub.id)
        assert result.status == "system_error", f"应为 system_error: {result.status}"
        # 系统错误不扣分：score 保持 None（不覆盖）
        assert result.score in (0, None), f"缺配置不应产生有效分: {result.score}"


def test_v1_missing_rubric_system_error(db_session_factory):
    """缺锁定 Rubric→系统错误"""
    from app.models import JudgeQuestion, Submission
    from app.worker.judge_worker import _v1_judge_submission
    from app.config import Settings

    with db_session_factory() as db:
        q = JudgeQuestion(assignment_id=1, title="Q", function_name="f",
                          hidden_tests="def test(): assert True",
                          grading_mode="active",
                          test_groups=[{"id":"F1","name":"F","dimension":"F","max_score":60,"tests":"def test(): assert True"},
                                       {"id":"R1","name":"R","dimension":"R","max_score":10,"tests":"def test(): assert True"}])
        db.add(q); db.flush()
        sub = Submission(question_id=q.id, student_id=1, code="def f(): pass",
                         status="running", grading_status="running")
        db.add(sub); db.commit()

        settings = Settings(_env_file=None, judge_use_docker=False)
        result = _v1_judge_submission(db, None, settings, sub, q, None, None, 5, 256)
        assert result.status == "system_error"


def test_legacy_fallback_only_for_legacy(db_session_factory):
    """legacy 模式正确走 legacy 路径（mock Docker 验证）"""
    from unittest.mock import patch
    from app.models import JudgeQuestion, Submission
    from app.worker.judge_worker import process_submission
    from app.config import Settings
    from app.services.judge_queue import enqueue_job

    with db_session_factory() as db:
        q = JudgeQuestion(assignment_id=1, title="Q", function_name="f",
                          hidden_tests="def test(): assert True",
                          grading_mode="legacy", test_groups=[])
        db.add(q); db.flush()
        sub = Submission(question_id=q.id, student_id=1, code="def f(): pass",
                         status="queued", grading_status="pending")
        db.add(sub); db.commit()
        enqueue_job(db, job_type="assignment", object_id=sub.id)

    settings = Settings(_env_file=None, judge_use_docker=False, judge_timeout_seconds=5)
    with db_session_factory() as db:
        with patch("app.worker.judge_worker._run_docker_pytest",
                   side_effect=Exception("no docker")):
            result = process_submission(db, None, settings, sub.id)
        # legacy 路径：Docker 异常应被捕获为 system_error
        assert result.status == "system_error"


# ── P0: 考试权限——越权覆盖返回 403 ──

def test_teacher_cannot_override_other_course(client, db_session_factory):
    """教师不能覆盖其他课程的成绩"""
    from conftest import create_user, login, auth_header

    with db_session_factory() as db:
        from app.models import User, Course, Exam, ExamQuestion, ExamSubmission, ExamAnswer, CodeGrade, QuestionRubric
        import datetime as _dt

        t1 = create_user(db_session_factory, "t1_reg", "teacher")
        t2 = create_user(db_session_factory, "t2_reg", "teacher")
        s1 = create_user(db_session_factory, "s1_reg", "student")

        with db_session_factory() as db2:
            c1 = Course(title="C1", status="published", teacher_id=t1.id)
            c2 = Course(title="C2", status="published", teacher_id=t2.id)
            db2.add_all([c1, c2]); db2.flush()
            e1 = Exam(course_id=c1.id, title="E1", status="published", duration_minutes=60)
            db2.add(e1); db2.flush()
            eq = ExamQuestion(exam_id=e1.id, question_type="code", prompt="t",
                              correct_answer={"test_file":""}, points=10, grading_mode="shadow")
            db2.add(eq); db2.flush()
            es = ExamSubmission(exam_id=e1.id, student_id=s1.id, status="grading")
            db2.add(es); db2.flush()
            ea = ExamAnswer(submission_id=es.id, question_id=eq.id, code_answer="x",
                            grading_status="completed", score=5)
            db2.add(ea); db2.flush()
            now = _dt.datetime.now(_dt.timezone.utc)
            rub = QuestionRubric(exam_question_id=eq.id, version=1, status="locked",
                                 source_hash="a", source_snapshot={}, rubric_json={},
                                 model_name="m", locked_at=now)
            db2.add(rub); db2.flush()
            cg = CodeGrade(exam_answer_id=ea.id, rubric_id=rub.id, mode="shadow",
                           status="completed", functional_score=30, robustness_score=5)
            db2.add(cg); db2.commit()
            gid = cg.id

    # t2 登录尝试覆盖 t1 课程的评分
    t2_tok, _ = login(client, "t2_reg")
    resp = client.post(
        f"/api/v1/ai-grading/grades/{gid}/override",
        headers=auth_header(t2_tok),
        json={"reason": "跨课程覆盖测试", "final_score_100": 80},
    )
    assert resp.status_code == 403, f"跨课程覆盖应 403: {resp.status_code} {resp.text}"


# ── P0: exam finalize 阻止 active score=None ──

def test_finalize_blocks_active_score_none():
    """active 答案 score=None 时 finalize 返回 False"""
    from unittest.mock import MagicMock
    from app.services.exam_grading import finalize_if_ready

    db = MagicMock()
    mock_sub = MagicMock()
    mock_sub.status = "grading"
    # 新 scalar 调用顺序:
    # 1) submission, 2) active_nulls_score check, 3) CodeGrade blocking, 4) unfinished check
    db.scalar.side_effect = [mock_sub, True, None, None]

    result = finalize_if_ready(1, db)
    assert result is False, "score=None 的 active 答案应阻止汇总"
