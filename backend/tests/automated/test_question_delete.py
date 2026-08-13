"""作业题目安全删除测试（TASK-017 / F-07）。

- 仅无任何提交的 draft 作业可删除题目（204）
- 已发布或有提交 → 409，且无任何数据变化
- 同一事务清理从属数据（Rubric）；非 owner 403
"""
import pytest
from conftest import auth_header, create_user, login
from sqlalchemy import select

from app.models import (
    Assignment,
    Course,
    JudgeQuestion,
    QuestionRubric,
    Submission,
    User,
)

API = "/api/v1"


@pytest.fixture()
def ctx(client, db_session_factory):
    teacher = create_user(db_session_factory, "qd-teacher", "teacher")
    student_id = create_user(db_session_factory, "qd-student", "student").id
    token, _ = login(client, "qd-teacher")
    with db_session_factory() as db:
        course = Course(
            title="删除课", description="d", status="published",
            visibility="class", default_score=100, teacher_id=teacher.id,
        )
        db.add(course)
        db.flush()
        assignment = Assignment(course_id=course.id, title="删除作业")
        db.add(assignment)
        db.flush()
        question = JudgeQuestion(
            assignment_id=assignment.id, title="题1", function_name="solve",
            hidden_tests="def test_ok():\n    assert True",
            public_cases=[{"args": [], "expected": True}], grading_mode="legacy",
        )
        db.add(question)
        db.commit()
        return token, assignment.id, question.id, student_id


def _add_rubric(db_session_factory, question_id):
    with db_session_factory() as db:
        rubric = QuestionRubric(
            judge_question_id=question_id, version=1, status="locked",
            source_hash="h", source_snapshot={}, rubric_json={}, model_name="m",
        )
        db.add(rubric)
        db.commit()
        return rubric.id


def _delete(client, token, assignment_id, question_id):
    return client.delete(
        f"{API}/assignments/{assignment_id}/questions/{question_id}",
        headers=auth_header(token),
    )


def test_delete_question_succeeds_and_cleans_rubric(client, db_session_factory, ctx):
    token, assignment_id, question_id, _ = ctx
    rubric_id = _add_rubric(db_session_factory, question_id)
    response = _delete(client, token, assignment_id, question_id)
    assert response.status_code == 204, response.text
    with db_session_factory() as db:
        assert db.get(JudgeQuestion, question_id) is None
        assert db.get(QuestionRubric, rubric_id) is None


def test_delete_published_question_conflict(client, db_session_factory, ctx):
    token, assignment_id, question_id, _ = ctx
    with db_session_factory() as db:
        db.get(Assignment, assignment_id).status = "published"
        db.commit()
    response = _delete(client, token, assignment_id, question_id)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "ASSIGNMENT_CONTENT_LOCKED"
    with db_session_factory() as db:
        assert db.get(JudgeQuestion, question_id) is not None


def test_delete_question_with_submission_conflict(client, db_session_factory, ctx):
    """取消发布后只要存在提交仍禁止删除，且拒绝时零数据变化。"""
    token, assignment_id, question_id, student_id = ctx
    with db_session_factory() as db:
        db.add(Submission(
            question_id=question_id, student_id=student_id, code="print(1)",
            status="graded", grading_status="completed",
        ))
        db.commit()
    rubric_id = _add_rubric(db_session_factory, question_id)
    response = _delete(client, token, assignment_id, question_id)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "ASSIGNMENT_CONTENT_LOCKED"
    with db_session_factory() as db:
        assert db.get(JudgeQuestion, question_id) is not None
        assert db.get(QuestionRubric, rubric_id) is not None


def test_delete_question_forbidden_for_non_manager(client, db_session_factory, ctx):
    token, assignment_id, question_id, student_id = ctx
    create_user(db_session_factory, "qd-other-teacher", "teacher")
    other_token, _ = login(client, "qd-other-teacher")
    response = _delete(client, other_token, assignment_id, question_id)
    assert response.status_code == 403, response.text


def test_delete_question_not_found(client, ctx):
    token, assignment_id, _, _ = ctx
    response = _delete(client, token, assignment_id, 99999)
    assert response.status_code == 404, response.text
    assert response.json()["detail"]["code"] == "QUESTION_NOT_FOUND"


def test_delete_wrong_assignment_question_404(client, db_session_factory, ctx):
    token, assignment_id, _, _ = ctx
    with db_session_factory() as db:
        other = Assignment(course_id=db.get(Assignment, assignment_id).course_id, title="另一份")
        db.add(other)
        db.flush()
        other_question = JudgeQuestion(
            assignment_id=other.id, title="别家题", function_name="f",
            hidden_tests="assert True", grading_mode="legacy",
        )
        db.add(other_question)
        db.commit()
        other_question_id = other_question.id
    response = _delete(client, token, assignment_id, other_question_id)
    assert response.status_code == 404, response.text
