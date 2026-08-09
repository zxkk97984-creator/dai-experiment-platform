"""课程设置后端支持测试：封面 / 开课时间 / 可见范围 / 默认评分 读写与兼容性"""
from __future__ import annotations

from datetime import datetime

from conftest import auth_header, create_user, login


def _teacher_token(client, db_session_factory, username="teacher"):
    create_user(db_session_factory, username, "teacher")
    token, _ = login(client, username)
    return token


def _create_course(client, token, **extra):
    payload = {"title": "课程设置测试课程", "description": "desc", "status": "published", **extra}
    resp = client.post("/api/v1/courses", headers=auth_header(token), json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_course_with_settings(client, db_session_factory):
    """创建课程时写入全部 4 个新字段，响应原样返回"""
    token = _teacher_token(client, db_session_factory)
    course = _create_course(
        client,
        token,
        cover="/uploads/cover.png",
        start_time="2026-09-01T08:00:00",
        visibility="private",
        default_score=100,
    )
    assert course["cover"] == "/uploads/cover.png"
    assert datetime.fromisoformat(course["start_time"]).date() == datetime(2026, 9, 1).date()
    assert course["visibility"] == "private"
    assert course["default_score"] == 100


def test_create_course_defaults_backward_compatible(client, db_session_factory):
    """旧请求不带新字段：行为与之前一致，仅落库默认值"""
    token = _teacher_token(client, db_session_factory)
    course = _create_course(client, token)
    assert course["cover"] is None
    assert course["start_time"] is None
    assert course["visibility"] == "private"
    assert course["default_score"] == 100.0


def test_get_course_returns_settings(client, db_session_factory):
    """GET 单课程返回设置字段"""
    token = _teacher_token(client, db_session_factory)
    course_id = _create_course(client, token)["id"]
    resp = client.get(f"/api/v1/courses/{course_id}", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["cover"] is None
    assert data["start_time"] is None
    assert data["visibility"] == "private"
    assert data["default_score"] == 100.0


def test_list_courses_returns_settings(client, db_session_factory):
    """课程列表同样携带设置字段"""
    token = _teacher_token(client, db_session_factory)
    _create_course(client, token, cover="cover-a.png", default_score=100)
    resp = client.get("/api/v1/courses", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["cover"] == "cover-a.png"
    assert item["default_score"] == 100


def test_update_course_partial_settings(client, db_session_factory):
    """PATCH 只更新传入字段，其余设置保持不变（部分更新）"""
    token = _teacher_token(client, db_session_factory)
    course = _create_course(client, token, cover="old.png", default_score=100)
    course_id = course["id"]

    resp = client.patch(
        f"/api/v1/courses/{course_id}",
        headers=auth_header(token),
        json={"cover": "new.png"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["cover"] == "new.png"
    assert resp.json()["visibility"] == "private"
    assert resp.json()["default_score"] == 100.0

    resp = client.patch(
        f"/api/v1/courses/{course_id}",
        headers=auth_header(token),
        json={"start_time": "2026-10-01T10:30:00", "default_score": 150},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert datetime.fromisoformat(data["start_time"]).date() == datetime(2026, 10, 1).date()
    assert data["default_score"] == 150
    # 未传字段保持不变
    assert data["cover"] == "new.png"
    assert data["visibility"] == "private"


def test_update_course_clears_optional_fields(client, db_session_factory):
    """cover / start_time 可显式传 null 清空"""
    token = _teacher_token(client, db_session_factory)
    course = _create_course(client, token, cover="old.png", start_time="2026-09-01T08:00:00")
    course_id = course["id"]

    resp = client.patch(
        f"/api/v1/courses/{course_id}",
        headers=auth_header(token),
        json={"cover": None, "start_time": None},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["cover"] is None
    assert resp.json()["start_time"] is None


def test_update_course_rejects_null_settings(client, db_session_factory):
    """visibility / default_score 非空字段传 null 应返回 422 而非落库报错"""
    token = _teacher_token(client, db_session_factory)
    course_id = _create_course(client, token)["id"]

    for body in ({"visibility": None}, {"default_score": None}):
        resp = client.patch(
            f"/api/v1/courses/{course_id}", headers=auth_header(token), json=body
        )
        assert resp.status_code == 422, resp.text


def test_create_course_accepts_all_visibilities(client, db_session_factory):
    """可见范围枚举：private / public / whitelist 三种值均可创建"""
    token = _teacher_token(client, db_session_factory)
    for vis in ("private", "public", "whitelist"):
        resp = client.post(
            "/api/v1/courses",
            headers=auth_header(token),
            json={"title": f"可见范围-{vis}", "visibility": vis},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["visibility"] == vis


def test_create_course_rejects_invalid_visibility(client, db_session_factory):
    """可见范围枚举校验：非法第四值创建时直接 422"""
    token = _teacher_token(client, db_session_factory)
    resp = client.post(
        "/api/v1/courses",
        headers=auth_header(token),
        json={"title": "非法可见范围", "visibility": "everyone"},
    )
    assert resp.status_code == 422, resp.text
