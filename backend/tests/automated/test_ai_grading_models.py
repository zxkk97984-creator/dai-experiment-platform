"""Task 2: AI 评分数据模型测试——legacy 默认、XOR 约束、版本唯一、覆盖不可级联删除"""
import pytest
from sqlalchemy.exc import IntegrityError


def test_historical_questions_default_to_legacy(db_session_factory):
    """历史题目新建时 grading_mode 默认为 legacy"""
    from app.models import JudgeQuestion

    with db_session_factory() as db:
        question = JudgeQuestion(
            assignment_id=1,
            title="测试题",
            function_name="solve",
            hidden_tests="def test_x(): assert True",
            grading_mode="legacy",
        )
        db.add(question)
        db.flush()
        assert question.grading_mode == "legacy"


def test_new_question_defaults_to_shadow(db_session_factory):
    """新建编程题默认 grading_mode 为 shadow"""
    from app.models import JudgeQuestion

    with db_session_factory() as db:
        question = JudgeQuestion(
            assignment_id=1,
            title="新题目",
            function_name="solve",
            hidden_tests="def test_x(): assert True",
        )
        db.add(question)
        db.flush()
        assert question.grading_mode == "shadow"


def test_exam_question_grading_fields(db_session_factory):
    """考试编程题具备 grading_mode 和相关配置字段"""
    from app.models import ExamQuestion

    with db_session_factory() as db:
        q = ExamQuestion(
            exam_id=1,
            question_type="code",
            prompt="写一个排序函数",
            correct_answer={"test_file": "def test_sort(): pass"},
            points=25,
            grading_mode="shadow",
        )
        db.add(q)
        db.flush()
        assert q.grading_mode == "shadow"
        assert q.test_groups == []
        assert q.teacher_constraints == {}
        assert q.score_cap_rules == []


def test_rubric_xor_target_required(db_session_factory):
    """Rubric 必须关联 judge_question_id 或 exam_question_id 之一"""
    from app.models import QuestionRubric

    with db_session_factory() as db:
        rubric = QuestionRubric(
            version=1,
            status="draft",
            source_hash="abc123",
            source_snapshot={},
            rubric_json={},
            model_name="deepseek-v4-flash",
        )
        db.add(rubric)
        with pytest.raises(IntegrityError):
            db.flush()


def test_rubric_version_unique_per_question(db_session_factory):
    """同一题目内 Rubric 版本号必须唯一"""
    from app.models import QuestionRubric

    with db_session_factory() as db:
        r1 = QuestionRubric(
            judge_question_id=1,
            version=1,
            status="draft",
            source_hash="hash1",
            source_snapshot={},
            rubric_json={},
            model_name="deepseek-v4-flash",
        )
        db.add(r1)
        db.flush()

        r2 = QuestionRubric(
            judge_question_id=1,
            version=1,  # 同一题目重复版本
            status="draft",
            source_hash="hash2",
            source_snapshot={},
            rubric_json={},
            model_name="deepseek-v4-flash",
        )
        db.add(r2)
        with pytest.raises(IntegrityError):
            db.flush()


def test_code_grade_xor_target(db_session_factory):
    """CodeGrade 必须关联 submission_id 或 exam_answer_id 之一"""
    from app.models import CodeGrade

    with db_session_factory() as db:
        grade = CodeGrade(
            rubric_id=1,
            mode="shadow",
            status="pending",
        )
        db.add(grade)
        with pytest.raises(IntegrityError):
            db.flush()


def test_code_grade_unique_per_target(db_session_factory):
    """同一 submission 只允许一份当前 CodeGrade"""
    from app.models import CodeGrade

    with db_session_factory() as db:
        cg1 = CodeGrade(
            submission_id=1,
            rubric_id=1,
            mode="shadow",
            status="pending",
        )
        db.add(cg1)
        db.flush()

        cg2 = CodeGrade(
            submission_id=1,  # 重复
            rubric_id=1,
            mode="shadow",
            status="pending",
        )
        db.add(cg2)
        with pytest.raises(IntegrityError):
            db.flush()


def test_override_does_not_cascade_delete_grade(db_session_factory):
    """删除评分主体时覆盖记录不能级联删除"""
    from app.models import CodeGrade, GradeOverride

    with db_session_factory() as db:
        cg = CodeGrade(
            submission_id=1,
            rubric_id=1,
            mode="shadow",
            status="completed",
            functional_score=54,
            algorithm_score=13,
            robustness_score=7,
            quality_score=5,
        )
        db.add(cg)
        db.flush()

        override = GradeOverride(
            code_grade_id=cg.id,
            original_snapshot={"score": 79},
            replacement_snapshot={"score": 85},
            reason="修正算法分",
            reviewer_id=1,
        )
        db.add(override)
        db.flush()

        # 确认覆盖记录关联正确
        assert override.code_grade_id == cg.id
        assert override.reason == "修正算法分"


def test_rubric_locked_at_is_nullable(db_session_factory):
    """draft Rubric 的 locked_at 可以为空"""
    from app.models import QuestionRubric

    with db_session_factory() as db:
        rubric = QuestionRubric(
            judge_question_id=1,
            version=1,
            status="draft",
            source_hash="hash123",
            source_snapshot={},
            rubric_json={},
            model_name="deepseek-v4-flash",
        )
        db.add(rubric)
        db.flush()
        assert rubric.locked_at is None
        assert rubric.status == "draft"
