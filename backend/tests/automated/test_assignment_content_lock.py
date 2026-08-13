"""作业评分事实不可变测试（TASK-009 / R-01）。

已发布或存在任何学生提交（即使取消发布）时：
- 题目新增/修改、环境字段、AI 评分配置、Rubric 生成/修改/锁定 → 409 ASSIGNMENT_CONTENT_LOCKED
- 标题/描述/截止时间等非评分元数据仍可修改
- 详情接口暴露 has_submissions 供前端锁定编辑入口
"""
import pytest
from conftest import auth_header, create_user, login
from sqlalchemy import select

from app.models import (
    Assignment,
    Course,
    JudgeQuestion,
    Submission,
    User,
)

API = "/api/v1"


@pytest.fixture()
def ctx(client, db_session_factory):
    teacher = create_user(db_session_factory, "acl-teacher", "teacher")
    student_id = create_user(db_session_factory, "acl-student", "student").id
    token, _ = login(client, "acl-teacher")
    with db_session_factory() as db:
        course = Course(
            title="锁", description="d", status="published",
            visibility="class", default_score=100, teacher_id=teacher.id,
        )
        db.add(course)
        db.flush()
        assignment = Assignment(course_id=course.id, title="锁作业", status="published")
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


def _patch_question(client, token, assignment_id, question_id, **fields):
    return client.patch(
        f"{API}/assignments/{assignment_id}/questions/{question_id}",
        headers=auth_header(token), json=fields,
    )


def _patch_assignment(client, token, assignment_id, **fields):
    return client.patch(
        f"{API}/assignments/{assignment_id}", headers=auth_header(token), json=fields,
    )


# ── 已发布锁定 ─────────────────────────────────────────────────


def test_published_blocks_question_create(client, db_session_factory, ctx):
    token, assignment_id, _, _ = ctx
    response = client.post(
        f"{API}/assignments/{assignment_id}/questions", headers=auth_header(token),
        json={"title": "新题", "function_name": "f", "hidden_tests": "assert True"},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "ASSIGNMENT_CONTENT_LOCKED"


def test_published_blocks_question_update(client, ctx):
    token, assignment_id, question_id, _ = ctx
    response = _patch_question(client, token, assignment_id, question_id, title="改标题")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "ASSIGNMENT_CONTENT_LOCKED"


def test_published_blocks_env_change(client, ctx):
    token, assignment_id, _, _ = ctx
    response = _patch_assignment(client, token, assignment_id, import_policy_mode="restricted")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "ASSIGNMENT_CONTENT_LOCKED"


def test_published_blocks_ai_config_update(client, ctx):
    token, assignment_id, question_id, _ = ctx
    response = client.put(
        f"{API}/ai-grading/questions/assignment/{question_id}/config",
        headers=auth_header(token),
        json={"grading_mode": "legacy", "teacher_constraints": {}, "reference_solution": None,
              "test_groups": [], "score_cap_rules": []},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "ASSIGNMENT_CONTENT_LOCKED"


def test_published_blocks_rubric_generate(client, ctx):
    token, assignment_id, question_id, _ = ctx
    response = client.post(
        f"{API}/ai-grading/questions/assignment/{question_id}/rubrics/generate",
        headers=auth_header(token),
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "ASSIGNMENT_CONTENT_LOCKED"


def test_published_allows_metadata_updates(client, ctx):
    """标题/描述/截止时间等非评分元数据仍可修改。"""
    token, assignment_id, _, _ = ctx
    response = _patch_assignment(client, token, assignment_id, title="锁作业 v2")
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "锁作业 v2"


# ── 取消发布后：有提交仍锁定 ────────────────────────────────────


def test_unpublished_with_submission_still_locked(client, db_session_factory, ctx):
    token, assignment_id, question_id, student_id = ctx
    with db_session_factory() as db:
        db.add(Submission(
            question_id=question_id, student_id=student_id, code="print(1)",
            status="graded", grading_status="completed",
        ))
        db.commit()
    # 取消发布
    unpublish = client.post(
        f"{API}/assignments/{assignment_id}/unpublish", headers=auth_header(token),
    )
    assert unpublish.status_code == 200, unpublish.text

    response = _patch_question(client, token, assignment_id, question_id, title="改标题")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "ASSIGNMENT_CONTENT_LOCKED"

    env_response = _patch_assignment(client, token, assignment_id, import_policy_mode="restricted")
    assert env_response.status_code == 409, env_response.text

    ai_response = client.put(
        f"{API}/ai-grading/questions/assignment/{question_id}/config",
        headers=auth_header(token),
        json={"grading_mode": "legacy", "teacher_constraints": {}, "reference_solution": None,
              "test_groups": [], "score_cap_rules": []},
    )
    assert ai_response.status_code == 409, ai_response.text

    # 元数据仍可改
    ok = _patch_assignment(client, token, assignment_id, title="锁作业 v3")
    assert ok.status_code == 200, ok.text


def test_unpublished_without_submission_editable(client, db_session_factory, ctx):
    token, assignment_id, question_id, _ = ctx
    with db_session_factory() as db:
        db.get(Assignment, assignment_id).status = "draft"
        db.commit()
    response = _patch_question(client, token, assignment_id, question_id, title="改标题")
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "改标题"


# ── 详情暴露提交事实 ───────────────────────────────────────────


def test_detail_exposes_has_submissions(client, db_session_factory, ctx):
    token, assignment_id, question_id, student_id = ctx
    detail = client.get(f"{API}/assignments/{assignment_id}", headers=auth_header(token))
    assert detail.json()["has_submissions"] is False

    with db_session_factory() as db:
        db.add(Submission(
            question_id=question_id, student_id=student_id, code="print(1)",
            status="graded", grading_status="completed",
        ))
        db.commit()
    detail = client.get(f"{API}/assignments/{assignment_id}", headers=auth_header(token))
    assert detail.json()["has_submissions"] is True
