"""公开 API 状态字段强类型化测试（TASK-019 / F-42）。

覆盖课程/作业/考试/实验/课时/用户的状态写入口：非法状态统一 422，
合法值可写；响应保留现有字符串格式（不改 DB 存储）。
"""
import pytest
from conftest import auth_header, create_user, login
from pydantic import ValidationError

from app.models import Course
from app.schemas import (
    CourseCreate,
    CourseUpdate,
    ExamCreate,
    ExamUpdate,
    LessonCreate,
    LessonUpdate,
    StatusUpdate,
    UserCreate,
    UserUpdate,
)

API = "/api/v1"


# ── Schema 层 ──────────────────────────────────────────────────


def test_course_schemas_typed():
    CourseCreate(title="t")
    with pytest.raises(ValidationError):
        CourseCreate(title="t", status="published")
    with pytest.raises(ValidationError):
        CourseUpdate(status="live")


def test_exam_schemas_typed():
    ExamCreate(course_id=1, title="t")
    with pytest.raises(ValidationError):
        ExamCreate(course_id=1, title="t", status="published")
    ExamUpdate(status="published")
    with pytest.raises(ValidationError):
        ExamUpdate(status="archived")


def test_lesson_schemas_typed():
    LessonCreate(title="l", status="pending")
    with pytest.raises(ValidationError):
        LessonCreate(title="l", status="live")
    LessonUpdate(status="published")
    with pytest.raises(ValidationError):
        LessonUpdate(status="hidden")


def test_user_schemas_typed():
    UserCreate(username="u", password="Passw0rd!", real_name="U", role="student", status="disabled")
    with pytest.raises(ValidationError):
        UserCreate(username="u", password="Passw0rd!", real_name="U", role="legacy")
    with pytest.raises(ValidationError):
        UserCreate(username="u", password="Passw0rd!", real_name="U", role="student", status="banned")
    UserUpdate(status="active")
    with pytest.raises(ValidationError):
        UserUpdate(role="legacy")
    with pytest.raises(ValidationError):
        UserUpdate(status="pending")
    with pytest.raises(ValidationError):
        StatusUpdate(status="archived")


# ── API 层 ─────────────────────────────────────────────────────


def test_user_status_endpoint_typed(client, db_session_factory):
    create_user(db_session_factory, "st-admin", "admin")
    target = create_user(db_session_factory, "st-target", "student")
    token, _ = login(client, "st-admin")
    bad = client.patch(
        f"{API}/users/{target.id}/status", headers=auth_header(token),
        json={"status": "banned"},
    )
    assert bad.status_code == 422, bad.text
    good = client.patch(
        f"{API}/users/{target.id}/status", headers=auth_header(token),
        json={"status": "disabled"},
    )
    assert good.status_code == 200, good.text
    assert good.json()["status"] == "disabled"


def test_user_patch_status_typed(client, db_session_factory):
    """PATCH /users/{id} 的 status 字段与 /status 端点同样强类型。"""
    create_user(db_session_factory, "st-admin2", "admin")
    target = create_user(db_session_factory, "st-target2", "student")
    token, _ = login(client, "st-admin2")
    bad = client.patch(
        f"{API}/users/{target.id}", headers=auth_header(token),
        json={"status": "banned"},
    )
    assert bad.status_code == 422, bad.text


def test_exam_status_endpoint_typed(client, db_session_factory):
    teacher = create_user(db_session_factory, "st-teacher", "teacher")
    token, _ = login(client, "st-teacher")
    with db_session_factory() as db:
        course = Course(
            title="c", description="d", status="published",
            visibility="public", default_score=100, teacher_id=teacher.id,
        )
        db.add(course)
        db.commit()
        course_id = course.id
    created = client.post(
        f"{API}/exams", headers=auth_header(token),
        json={"course_id": course_id, "title": "考试"},
    )
    assert created.status_code == 201, created.text
    bad = client.patch(
        f"{API}/exams/{created.json()['id']}", headers=auth_header(token),
        json={"status": "archived"},
    )
    assert bad.status_code == 422, bad.text


def test_lesson_status_endpoint_typed(client, db_session_factory):
    teacher = create_user(db_session_factory, "st-teacher2", "teacher")
    token, _ = login(client, "st-teacher2")
    with db_session_factory() as db:
        course = Course(
            title="c2", description="d", status="published",
            visibility="public", default_score=100, teacher_id=teacher.id,
        )
        db.add(course)
        db.commit()
        course_id = course.id
    chapter = client.post(
        f"{API}/courses/{course_id}/chapters", headers=auth_header(token),
        json={"title": "章"},
    ).json()
    bad = client.post(
        f"{API}/chapters/{chapter['id']}/lessons", headers=auth_header(token),
        json={"title": "课", "status": "hidden"},
    )
    assert bad.status_code == 422, bad.text
    good = client.post(
        f"{API}/chapters/{chapter['id']}/lessons", headers=auth_header(token),
        json={"title": "课2", "status": "pending"},
    )
    assert good.status_code == 201, good.text
    assert good.json()["status"] == "pending"
