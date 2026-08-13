"""课程发布前的基本信息完整性门禁测试。"""
from datetime import date

from conftest import auth_header, create_user, login
from app.models import AcademicTerm, TeachingClass


API = "/api/v1"


def _teacher_token(client, db_session_factory):
    create_user(db_session_factory, "publish_teacher", "teacher")
    token, _ = login(client, "publish_teacher")
    return token


def _academic_data(db_session_factory):
    with db_session_factory() as db:
        term = AcademicTerm(
            code="PUBLISH-TERM",
            name="Publish term",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 1, 20),
            status="active",
        )
        db.add(term)
        db.flush()
        teaching_class = TeachingClass(
            academic_term_id=term.id,
            code="PUBLISH-CLASS",
            name="Publish class",
            status="active",
        )
        db.add(teaching_class)
        db.commit()
        return term.id, teaching_class.id


def test_publish_rejects_incomplete_course(client, db_session_factory):
    token = _teacher_token(client, db_session_factory)
    created = client.post(
        f"{API}/courses",
        headers=auth_header(token),
        json={"title": "Draft course", "status": "draft"},
    )
    assert created.status_code == 201, created.text

    response = client.patch(
        f"{API}/courses/{created.json()['id']}",
        headers=auth_header(token),
        json={"status": "published"},
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "COURSE_INCOMPLETE"
    assert "所属学期" in response.json()["detail"]["message"]
    assert "课程封面" in response.json()["detail"]["message"]


def test_create_with_published_status_rejected(client, db_session_factory):
    """TASK-006：POST 只接受 draft，直接创建 published 返回 422（关闭发布旁路）。"""
    token = _teacher_token(client, db_session_factory)
    response = client.post(
        f"{API}/courses",
        headers=auth_header(token),
        json={"title": "Bypass course", "status": "published"},
    )
    assert response.status_code == 422, response.text
    # 未落库
    assert "bypass" not in response.text


def test_create_with_unknown_status_rejected(client, db_session_factory):
    token = _teacher_token(client, db_session_factory)
    response = client.post(
        f"{API}/courses",
        headers=auth_header(token),
        json={"title": "Weird course", "status": "live"},
    )
    assert response.status_code == 422, response.text


def test_regular_update_does_not_publish(client, db_session_factory):
    """普通更新（不传 status）不触发发布：草稿仍为草稿。"""
    token = _teacher_token(client, db_session_factory)
    created = client.post(
        f"{API}/courses",
        headers=auth_header(token),
        json={"title": "Stay draft", "status": "draft"},
    )
    assert created.status_code == 201, created.text
    course_id = created.json()["id"]

    response = client.patch(
        f"{API}/courses/{course_id}",
        headers=auth_header(token),
        json={"title": "Stay draft v2"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "draft"


def test_patch_with_unknown_status_rejected(client, db_session_factory):
    token = _teacher_token(client, db_session_factory)
    created = client.post(
        f"{API}/courses",
        headers=auth_header(token),
        json={"title": "Typed status", "status": "draft"},
    )
    assert created.status_code == 201, created.text
    response = client.patch(
        f"{API}/courses/{created.json()['id']}",
        headers=auth_header(token),
        json={"status": "live"},
    )
    assert response.status_code == 422, response.text


def test_publish_accepts_course_with_complete_basic_information(client, db_session_factory):
    token = _teacher_token(client, db_session_factory)
    term_id, class_id = _academic_data(db_session_factory)
    created = client.post(
        f"{API}/courses",
        headers=auth_header(token),
        json={
            "title": "Complete course",
            "description": "Course description",
            "status": "draft",
            "academic_term_id": term_id,
            "teaching_class_ids": [class_id],
            "cover": "covers/complete.png",
            "start_time": "2026-09-01T08:00:00",
            "visibility": "public",
            "default_score": 100,
        },
    )
    assert created.status_code == 201, created.text

    response = client.patch(
        f"{API}/courses/{created.json()['id']}",
        headers=auth_header(token),
        json={"status": "published"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"
