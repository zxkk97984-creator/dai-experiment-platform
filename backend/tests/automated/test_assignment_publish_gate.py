"""作业发布门禁与零题语义测试（TASK-007 / F-02 / F-03）。

- POST 只允许 draft；通用 PATCH 不接受 status（422）
- 发布/取消发布只走 /publish 与 /unpublish
- 零题作业发布 409 ASSIGNMENT_HAS_NO_QUESTIONS；零题 is_submitted 恒为 False
- 合法发布/取消发布/重复发布
"""
import pytest
from conftest import auth_header, create_user, login
from sqlalchemy import select

from app.models import (
    Assignment,
    Course,
    CourseEnrollment,
    JudgeQuestion,
    Submission,
    User,
)

API = "/api/v1"


@pytest.fixture()
def teacher(client, db_session_factory):
    create_user(db_session_factory, "apg-teacher", "teacher")
    token, _ = login(client, "apg-teacher")
    return token


@pytest.fixture()
def course_id(db_session_factory, teacher):
    with db_session_factory() as db:
        teacher_user = db.scalar(select(User).where(User.username == "apg-teacher"))
        course = Course(
            title="发布门禁课程", description="d", status="published",
            visibility="class", default_score=100, teacher_id=teacher_user.id,
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        return course.id


def _create_assignment(client, token, course_id, **extra):
    resp = client.post(
        f"{API}/assignments",
        headers=auth_header(token),
        json={"course_id": course_id, "title": "作业", **extra},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _add_question(client, token, assignment_id, grading_mode="legacy"):
    resp = client.post(
        f"{API}/assignments/{assignment_id}/questions",
        headers=auth_header(token),
        json={
            "title": "题1", "function_name": "solve",
            "hidden_tests": "def test_ok():\n    assert True",
            "public_cases": [{"args": [], "expected": True}],
            "grading_mode": grading_mode,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── 创建旁路 ───────────────────────────────────────────────────


def test_create_with_published_status_rejected(client, teacher, course_id):
    response = client.post(
        f"{API}/assignments",
        headers=auth_header(teacher),
        json={"course_id": course_id, "title": "旁路", "status": "published"},
    )
    assert response.status_code == 422, response.text


def test_create_defaults_to_draft(client, teacher, course_id):
    assignment = _create_assignment(client, teacher, course_id)
    assert assignment["status"] == "draft"
    assert assignment["published_at"] is None


def test_patch_cannot_write_status(client, teacher, course_id):
    assignment = _create_assignment(client, teacher, course_id)
    response = client.patch(
        f"{API}/assignments/{assignment['id']}",
        headers=auth_header(teacher),
        json={"status": "published"},
    )
    assert response.status_code == 422, response.text
    # 状态未被改变
    detail = client.get(
        f"{API}/assignments/{assignment['id']}", headers=auth_header(teacher)
    )
    assert detail.json()["status"] == "draft"


# ── 零题规则 ───────────────────────────────────────────────────


def test_publish_with_no_questions_rejected(client, teacher, course_id):
    assignment = _create_assignment(client, teacher, course_id)
    response = client.post(
        f"{API}/assignments/{assignment['id']}/publish",
        headers=auth_header(teacher),
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "ASSIGNMENT_HAS_NO_QUESTIONS"


def test_zero_question_assignment_is_submitted_false(client, db_session_factory, course_id):
    """零题作业永远不是已提交（含存量 ORM published 数据）。"""
    student_id = create_user(db_session_factory, "apg-student", "student").id
    with db_session_factory() as db:
        assignment = Assignment(
            course_id=course_id, title="存量零题作业", status="published",
        )
        db.add(assignment)
        db.add(CourseEnrollment(
            course_id=course_id, student_id=student_id, status="enrolled",
        ))
        db.commit()
        assignment_id = assignment.id

    student_token, _ = login(client, "apg-student")
    response = client.get(f"{API}/assignments", headers=auth_header(student_token))
    assert response.status_code == 200, response.text
    items = {item["id"]: item for item in response.json()["items"]}
    assert assignment_id in items
    assert items[assignment_id]["is_submitted"] is False


# ── 合法发布/取消/重复发布 ──────────────────────────────────────


def test_publish_with_question_succeeds(client, teacher, course_id):
    assignment = _create_assignment(client, teacher, course_id)
    _add_question(client, teacher, assignment["id"])
    response = client.post(
        f"{API}/assignments/{assignment['id']}/publish",
        headers=auth_header(teacher),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "published"
    assert body["published_at"] is not None


def test_unpublish_then_republish(client, teacher, course_id):
    assignment = _create_assignment(client, teacher, course_id)
    _add_question(client, teacher, assignment["id"])
    assert client.post(
        f"{API}/assignments/{assignment['id']}/publish",
        headers=auth_header(teacher),
    ).status_code == 200

    unpublish = client.post(
        f"{API}/assignments/{assignment['id']}/unpublish",
        headers=auth_header(teacher),
    )
    assert unpublish.status_code == 200, unpublish.text
    assert unpublish.json()["status"] == "draft"

    republish = client.post(
        f"{API}/assignments/{assignment['id']}/publish",
        headers=auth_header(teacher),
    )
    assert republish.status_code == 200, republish.text
    assert republish.json()["status"] == "published"


def test_repeated_publish_is_idempotent(client, teacher, course_id):
    assignment = _create_assignment(client, teacher, course_id)
    _add_question(client, teacher, assignment["id"])
    first = client.post(
        f"{API}/assignments/{assignment['id']}/publish",
        headers=auth_header(teacher),
    )
    assert first.status_code == 200
    published_at = first.json()["published_at"]
    second = client.post(
        f"{API}/assignments/{assignment['id']}/publish",
        headers=auth_header(teacher),
    )
    assert second.status_code == 200
    assert second.json()["published_at"] == published_at


def test_unpublish_requires_published(client, teacher, course_id):
    assignment = _create_assignment(client, teacher, course_id)
    response = client.post(
        f"{API}/assignments/{assignment['id']}/unpublish",
        headers=auth_header(teacher),
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "ASSIGNMENT_NOT_PUBLISHED"
