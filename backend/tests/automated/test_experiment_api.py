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
        "title": "Test", "status": "published", "visibility": "public",
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


def test_p0_4_teacher_submission_isolation(client, db_session_factory):
    """P0-4: 教师 A 不能看到教师 B 课程的实验提交"""
    # 创建教师 A 和课程 A
    create_user(db_session_factory, "t_iso_a", "teacher")
    create_user(db_session_factory, "s_iso_a", "student")
    t_a_tok, _ = login(client, "t_iso_a")
    s_a_tok, _ = login(client, "s_iso_a")

    # 教师 B 和课程 B
    create_user(db_session_factory, "t_iso_b", "teacher")
    create_user(db_session_factory, "s_iso_b", "student")
    t_b_tok, _ = login(client, "t_iso_b")
    s_b_tok, _ = login(client, "s_iso_b")

    # 教师 A 创建课程、章节、课时
    c_a = client.post("/api/v1/courses", headers=auth_header(t_a_tok), json={
        "title": "教师A的课程", "status": "published", "visibility": "public",
    })
    cid_a = c_a.json()["id"]
    client.post(f"/api/v1/courses/{cid_a}/enroll", headers=auth_header(s_a_tok))

    ch_a = client.post(f"/api/v1/courses/{cid_a}/chapters", headers=auth_header(t_a_tok), json={
        "title": "第一章", "order_index": 1,
    })
    chid_a = ch_a.json()["id"]

    # 需要创建模板才能创建课时（使用测试的 db_session_factory）
    from app.models import NotebookTemplate, NotebookTemplateVersion
    with db_session_factory() as db:
        tpl = NotebookTemplate(name="tpl_a", status="published", owner_id=1)
        db.add(tpl)
        db.flush()
        ver = NotebookTemplateVersion(
            template_id=tpl.id, version_number=1, sha256="abc",
            cells=[{"id": "c1", "type": "code", "source": "print(1)", "order": 0}],
            published_by_id=1,
        )
        db.add(ver)
        db.flush()
        tpl.current_version_id = ver.id
        db.commit()
        tpl_a_id = tpl.id

    les_a = client.post(f"/api/v1/chapters/{chid_a}/lessons", headers=auth_header(t_a_tok), json={
        "title": "课时A", "content_type": "markdown", "content": "# A",
        "order_index": 1,
    })
    lid_a = les_a.json()["id"]
    # 设置 template_id（LessonCreate schema 不含此字段，需单独更新）
    from app.database import SessionLocal as _SL
    from app.models import Lesson as _Lesson
    with db_session_factory() as db:
        lesson = db.get(_Lesson, lid_a)
        lesson.template_id = tpl_a_id
        db.commit()

    # 学生 A 创建实验记录并提交
    rec_a = client.post(f"/api/v1/experiments/records/ensure-for-lesson/{lid_a}",
                        headers=auth_header(s_a_tok))
    rid_a = rec_a.json()["id"]
    sub_a = client.post(f"/api/v1/experiments/records/{rid_a}/submit",
                        headers=auth_header(s_a_tok),
                        json={"client_request_id": "00000000-0000-0000-0000-000000000001"})
    assert sub_a.status_code == 201

    # 教师 A 可以查看自己课程的提交
    r_a = client.get("/api/v1/experiments/submissions", headers=auth_header(t_a_tok))
    assert r_a.status_code == 200
    items_a = r_a.json()["items"]
    assert len(items_a) >= 1, "教师 A 应该能看到自己课程的提交"

    # 教师 B 不应该看到教师 A 课程的提交（教师 B 没有任何课程）
    r_b = client.get("/api/v1/experiments/submissions", headers=auth_header(t_b_tok))
    assert r_b.status_code == 200
    items_b = r_b.json()["items"]
    assert len(items_b) == 0, f"教师 B 不应看到其他教师的提交，但看到了 {len(items_b)} 条"
