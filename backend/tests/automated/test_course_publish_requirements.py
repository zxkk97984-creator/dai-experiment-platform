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


# ── TASK-006：创建旁路关闭 ────────────────────────────────────


def test_create_course_rejects_published_status(client, db_session_factory):
    token = _teacher_token(client, db_session_factory)
    response = client.post(
        f"{API}/courses",
        headers=auth_header(token),
        json={"title": "Bypass attempt", "status": "published"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_create_course_rejects_archived_status(client, db_session_factory):
    token = _teacher_token(client, db_session_factory)
    response = client.post(
        f"{API}/courses",
        headers=auth_header(token),
        json={"title": "Bypass attempt", "status": "archived"},
    )
    assert response.status_code == 422, response.text


def test_create_course_accepts_draft_status(client, db_session_factory):
    token = _teacher_token(client, db_session_factory)
    response = client.post(
        f"{API}/courses",
        headers=auth_header(token),
        json={"title": "Plain draft", "status": "draft"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "draft"


def test_update_course_rejects_unknown_status(client, db_session_factory):
    token = _teacher_token(client, db_session_factory)
    created = client.post(
        f"{API}/courses",
        headers=auth_header(token),
        json={"title": "Draft course", "status": "draft"},
    )
    response = client.patch(
        f"{API}/courses/{created.json()['id']}",
        headers=auth_header(token),
        json={"status": "published_now"},
    )
    assert response.status_code == 422, response.text


def test_plain_update_does_not_trigger_publish(client, db_session_factory):
    token = _teacher_token(client, db_session_factory)
    created = client.post(
        f"{API}/courses",
        headers=auth_header(token),
        json={"title": "Draft course", "status": "draft"},
    )
    # 不完整课程做普通字段更新（不带 status）不应触发发布门禁，也应保持 draft
    response = client.patch(
        f"{API}/courses/{created.json()['id']}",
        headers=auth_header(token),
        json={"title": "Renamed draft"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Renamed draft"
    assert body["status"] == "draft"
