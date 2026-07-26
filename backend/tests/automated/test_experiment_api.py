"""实验 API 测试 — v5 统一模型后的验收测试"""
from conftest import auth_header, create_user, login


def test_student_cannot_read_draft_module(client, db_session_factory):
    """学生不能查看 draft 状态的实验模块"""
    create_user(db_session_factory, "developer1", "developer")
    create_user(db_session_factory, "student2", "student")
    d_tok, _ = login(client, "developer1")
    s_tok, _ = login(client, "student2")

    m = client.post("/api/v1/experiments/modules", headers=auth_header(d_tok), json={
        "name": "Draft Module", "status": "draft",
    })
    assert m.status_code == 201
    mid = m.json()["id"]

    r = client.get("/api/v1/experiments/modules", headers=auth_header(s_tok))
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["items"]]
    assert mid not in ids


def test_module_publish_is_patch(client, db_session_factory):
    """模块发布通过 PATCH 更新 status"""
    create_user(db_session_factory, "developer2", "developer")
    d_tok, _ = login(client, "developer2")

    m = client.post("/api/v1/experiments/modules", headers=auth_header(d_tok), json={
        "name": "To Publish", "status": "draft",
    })
    mid = m.json()["id"]

    r = client.patch(f"/api/v1/experiments/modules/{mid}", headers=auth_header(d_tok), json={
        "status": "published",
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "published"


def test_notebooks_deprecation_header(client, db_session_factory):
    """旧 notebooks API 返回 Deprecation 头"""
    create_user(db_session_factory, "student_dep", "student")
    tok, _ = login(client, "student_dep")
    r = client.get("/api/v1/notebooks/999", headers=auth_header(tok))
    assert r.headers.get("Deprecation") == "true"


def test_ensure_record_validation(client, db_session_factory):
    """ensure-for-lesson 不存在模板时返回 TEMPLATE_NOT_FOUND"""
    create_user(db_session_factory, "teacher_t", "teacher")
    create_user(db_session_factory, "student_s", "student")
    t_tok, _ = login(client, "teacher_t")
    s_tok, _ = login(client, "student_s")

    c = client.post("/api/v1/courses", headers=auth_header(t_tok), json={
        "title": "Test", "status": "published",
    })
    ch = client.post(f"/api/v1/courses/{c.json()['id']}/chapters", headers=auth_header(t_tok), json={
        "title": "Ch1",
    })
    le = client.post(f"/api/v1/chapters/{ch.json()['id']}/lessons", headers=auth_header(t_tok), json={
        "title": "Lesson", "content_type": "markdown",
    })
    client.post(f"/api/v1/courses/{c.json()['id']}/enroll", headers=auth_header(s_tok))

    r = client.post(
        f"/api/v1/experiments/records/ensure-for-lesson/{le.json()['id']}",
        headers=auth_header(s_tok),
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "TEMPLATE_NOT_FOUND"
