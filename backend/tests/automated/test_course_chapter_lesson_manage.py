"""教师端课程目录管理接口测试：章节编辑/删除、课时删除/移动/发布切换"""
from __future__ import annotations

from conftest import auth_header, create_user, login


def _create_course(client, teacher_token):
    # TASK-006：POST /courses 只接受 status="draft"（不传默认 draft）；章节/课时管理不依赖发布状态
    resp = client.post(
        "/api/v1/courses",
        headers=auth_header(teacher_token),
        json={"title": "章节管理测试课程", "description": "desc"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_chapter(client, teacher_token, course_id, title="第一章", order_index=1):
    resp = client.post(
        f"/api/v1/courses/{course_id}/chapters",
        headers=auth_header(teacher_token),
        json={"title": title, "order_index": order_index},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_lesson(client, teacher_token, chapter_id, title="第一课"):
    resp = client.post(
        f"/api/v1/chapters/{chapter_id}/lessons",
        headers=auth_header(teacher_token),
        json={"title": title, "content_type": "markdown", "content": "# 内容", "order_index": 1},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_lesson_create_defaults_to_draft(client, db_session_factory):
    """新建课时默认草稿，读取接口返回 status 字段"""
    create_user(db_session_factory, "teacher", "teacher")
    teacher_token, _ = login(client, "teacher")
    course_id = _create_course(client, teacher_token)
    chapter = _create_chapter(client, teacher_token, course_id)
    lesson = _create_lesson(client, teacher_token, chapter["id"])

    assert lesson["status"] == "draft"

    chapters = client.get(
        f"/api/v1/courses/{course_id}/chapters", headers=auth_header(teacher_token)
    ).json()["items"]
    assert chapters[0]["lessons"][0]["status"] == "draft"


def test_update_lesson_title_and_status(client, db_session_factory):
    """PATCH 课时：修改标题与发布状态"""
    create_user(db_session_factory, "teacher", "teacher")
    teacher_token, _ = login(client, "teacher")
    course_id = _create_course(client, teacher_token)
    chapter = _create_chapter(client, teacher_token, course_id)
    lesson = _create_lesson(client, teacher_token, chapter["id"])

    resp = client.patch(
        f"/api/v1/lessons/{lesson['id']}",
        headers=auth_header(teacher_token),
        json={"title": "改名后的课", "status": "published"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "改名后的课"
    assert resp.json()["status"] == "published"


def test_move_lesson_to_another_chapter(client, db_session_factory):
    """PATCH 课时传 chapter_id 移动到其他章节"""
    create_user(db_session_factory, "teacher", "teacher")
    teacher_token, _ = login(client, "teacher")
    course_id = _create_course(client, teacher_token)
    chapter_a = _create_chapter(client, teacher_token, course_id, "第一章", 1)
    chapter_b = _create_chapter(client, teacher_token, course_id, "第二章", 2)
    lesson = _create_lesson(client, teacher_token, chapter_a["id"])

    resp = client.patch(
        f"/api/v1/lessons/{lesson['id']}",
        headers=auth_header(teacher_token),
        json={"chapter_id": chapter_b["id"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["chapter_id"] == chapter_b["id"]

    chapters = client.get(
        f"/api/v1/courses/{course_id}/chapters", headers=auth_header(teacher_token)
    ).json()["items"]
    assert chapters[0]["lessons"] == []
    assert chapters[1]["lessons"][0]["id"] == lesson["id"]


def test_move_lesson_rejects_cross_course_chapter(client, db_session_factory):
    """移动到其他课程的章节应被拒绝"""
    create_user(db_session_factory, "teacher", "teacher")
    teacher_token, _ = login(client, "teacher")
    course_a = _create_course(client, teacher_token)
    course_b = _create_course(client, teacher_token)
    chapter_a = _create_chapter(client, teacher_token, course_a)
    chapter_b = _create_chapter(client, teacher_token, course_b)
    lesson = _create_lesson(client, teacher_token, chapter_a["id"])

    resp = client.patch(
        f"/api/v1/lessons/{lesson['id']}",
        headers=auth_header(teacher_token),
        json={"chapter_id": chapter_b["id"]},
    )
    assert resp.status_code == 400, resp.text


def test_delete_lesson(client, db_session_factory):
    """DELETE 课时"""
    create_user(db_session_factory, "teacher", "teacher")
    teacher_token, _ = login(client, "teacher")
    course_id = _create_course(client, teacher_token)
    chapter = _create_chapter(client, teacher_token, course_id)
    lesson = _create_lesson(client, teacher_token, chapter["id"])

    resp = client.delete(
        f"/api/v1/lessons/{lesson['id']}", headers=auth_header(teacher_token)
    )
    assert resp.status_code == 204, resp.text

    chapters = client.get(
        f"/api/v1/courses/{course_id}/chapters", headers=auth_header(teacher_token)
    ).json()["items"]
    assert chapters[0]["lessons"] == []


def test_delete_missing_lesson_returns_404(client, db_session_factory):
    create_user(db_session_factory, "teacher", "teacher")
    teacher_token, _ = login(client, "teacher")
    resp = client.delete("/api/v1/lessons/99999", headers=auth_header(teacher_token))
    assert resp.status_code == 404


def test_update_chapter_title_and_order(client, db_session_factory):
    """PATCH 章节：修改标题与排序位置"""
    create_user(db_session_factory, "teacher", "teacher")
    teacher_token, _ = login(client, "teacher")
    course_id = _create_course(client, teacher_token)
    chapter = _create_chapter(client, teacher_token, course_id)

    resp = client.patch(
        f"/api/v1/chapters/{chapter['id']}",
        headers=auth_header(teacher_token),
        json={"title": "改名章节", "order_index": 9},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "改名章节"
    assert resp.json()["order_index"] == 9


def test_delete_chapter_cascades_lessons(client, db_session_factory):
    """DELETE 章节：级联删除章节内全部课时"""
    create_user(db_session_factory, "teacher", "teacher")
    teacher_token, _ = login(client, "teacher")
    course_id = _create_course(client, teacher_token)
    chapter = _create_chapter(client, teacher_token, course_id)
    _create_lesson(client, teacher_token, chapter["id"])

    resp = client.delete(
        f"/api/v1/chapters/{chapter['id']}", headers=auth_header(teacher_token)
    )
    assert resp.status_code == 204, resp.text

    chapters = client.get(
        f"/api/v1/courses/{course_id}/chapters", headers=auth_header(teacher_token)
    ).json()["items"]
    assert chapters == []


def test_non_owner_teacher_cannot_manage_chapters(client, db_session_factory):
    """非课程创建者不能编辑/删除章节"""
    create_user(db_session_factory, "teacher_a", "teacher")
    create_user(db_session_factory, "teacher_b", "teacher")
    token_a, _ = login(client, "teacher_a")
    token_b, _ = login(client, "teacher_b")
    course_id = _create_course(client, token_a)
    chapter = _create_chapter(client, token_a, course_id)

    resp = client.patch(
        f"/api/v1/chapters/{chapter['id']}",
        headers=auth_header(token_b),
        json={"title": "越权改名"},
    )
    assert resp.status_code == 403

    resp = client.delete(
        f"/api/v1/chapters/{chapter['id']}", headers=auth_header(token_b)
    )
    assert resp.status_code == 403
