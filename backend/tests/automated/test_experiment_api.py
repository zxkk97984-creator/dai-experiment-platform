"""实验 API 测试 — v5 统一模型后的验收测试"""
from conftest import auth_header, create_course_db, create_user, login, seed_basic_environment


def _seed_student_catalog(db_session_factory):
    seed_basic_environment(db_session_factory)
    """创建四态目录数据，并放入一条其他学生记录验证隔离。"""
    from datetime import datetime, timedelta, timezone

    from app.models import (
        ExperimentModule,
        ExperimentRecord,
        NotebookTemplate,
        NotebookTemplateVersion,
    )

    developer = create_user(db_session_factory, "catalog_developer", "developer")
    student = create_user(db_session_factory, "catalog_student", "student")
    other_student = create_user(db_session_factory, "catalog_other", "student")

    with db_session_factory() as db:
        template = NotebookTemplate(
            name="Catalog template",
            status="published",
            owner_id=developer.id,
        )
        db.add(template)
        db.flush()
        version = NotebookTemplateVersion(
            template_id=template.id,
            version_number=1,
            sha256="catalog-v1",
            cells=[],
            published_by_id=developer.id,
        )
        db.add(version)
        db.flush()

        modules = [
            ExperimentModule(name="01 Python 入门", status="published", owner_id=developer.id),
            ExperimentModule(name="02 NumPy 基础", status="published", owner_id=developer.id),
            ExperimentModule(name="03 可视化", status="published", owner_id=developer.id),
            ExperimentModule(name="04 数据清洗", status="published", owner_id=developer.id),
            ExperimentModule(name="隐藏草稿", status="draft", owner_id=developer.id),
        ]
        db.add_all(modules)
        db.flush()

        now = datetime.now(timezone.utc)
        db.add_all([
            ExperimentRecord(
                module_id=modules[0].id,
                template_version_id=version.id,
                student_id=student.id,
                status="started",
                updated_at=now - timedelta(days=3),
            ),
            ExperimentRecord(
                module_id=modules[1].id,
                template_version_id=version.id,
                student_id=student.id,
                status="submitted",
                updated_at=now - timedelta(days=2),
            ),
            ExperimentRecord(
                module_id=modules[2].id,
                template_version_id=version.id,
                student_id=student.id,
                status="graded",
                updated_at=now - timedelta(days=1),
            ),
            ExperimentRecord(
                module_id=modules[3].id,
                template_version_id=version.id,
                student_id=other_student.id,
                status="graded",
                updated_at=now,
            ),
        ])
        db.commit()

    return student


def test_student_catalog_merges_status_summary_and_isolates_records(client, db_session_factory):
    _seed_student_catalog(db_session_factory)
    token, _ = login(client, "catalog_student")

    response = client.get(
        "/api/v1/experiments/modules/student-catalog",
        headers=auth_header(token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["learning_status"] for item in body["items"]] == [
        "started", "submitted", "graded", "not_started",
    ]
    assert body["summary"] == {
        "total": 4,
        "not_started": 1,
        "started": 1,
        "submitted": 1,
        "graded": 1,
    }
    assert body["items"][3]["last_learning_at"] is None
    assert all(item["name"] != "隐藏草稿" for item in body["items"])


def test_student_catalog_search_filter_sort_and_pagination(client, db_session_factory):
    _seed_student_catalog(db_session_factory)
    token, _ = login(client, "catalog_student")
    headers = auth_header(token)

    filtered = client.get(
        "/api/v1/experiments/modules/student-catalog?status=submitted&q=NumPy",
        headers=headers,
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["name"] == "02 NumPy 基础"
    assert filtered.json()["summary"]["total"] == 4

    recent = client.get(
        "/api/v1/experiments/modules/student-catalog?sort=recent_desc&page=2&page_size=2",
        headers=headers,
    )
    assert recent.status_code == 200, recent.text
    assert recent.json()["page"] == 2
    assert recent.json()["page_size"] == 2
    assert recent.json()["total"] == 4
    assert [item["name"] for item in recent.json()["items"]] == [
        "01 Python 入门", "04 数据清洗",
    ]


def test_student_catalog_rejects_non_student_roles(client, db_session_factory):
    create_user(db_session_factory, "catalog_teacher", "teacher")
    token, _ = login(client, "catalog_teacher")
    response = client.get(
        "/api/v1/experiments/modules/student-catalog",
        headers=auth_header(token),
    )
    assert response.status_code == 403


def test_teacher_can_create_and_update_own_module_only(client, db_session_factory):
    """教师可以创建模块，但不能修改其他开发者的模块"""
    create_user(db_session_factory, "teacher_module", "teacher")
    create_user(db_session_factory, "developer_module", "developer")
    teacher_tok, _ = login(client, "teacher_module")
    developer_tok, _ = login(client, "developer_module")

    own = client.post(
        "/api/v1/experiments/modules",
        headers=auth_header(teacher_tok),
        json={"name": "教师实验模块", "description": "教师创建"},
    )
    assert own.status_code == 201, own.text

    own_update = client.post(
        f"/api/v1/experiments/modules/{own.json()['id']}/publish",
        headers=auth_header(teacher_tok),
    )
    # 未绑定模板 → 发布被模板就绪门禁拒绝
    assert own_update.status_code == 422, own_update.text
    assert own_update.json()["detail"]["code"] == "MODULE_TEMPLATE_REQUIRED"

    other = client.post(
        "/api/v1/experiments/modules",
        headers=auth_header(developer_tok),
        json={"name": "开发者实验模块"},
    )
    assert other.status_code == 201, other.text

    other_update = client.patch(
        f"/api/v1/experiments/modules/{other.json()['id']}",
        headers=auth_header(teacher_tok),
        json={"name": "越权改名"},
    )
    assert other_update.status_code == 403


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


def test_module_publish_requires_template_ready(client, db_session_factory):
    """模块发布走专用端点；PATCH 不再能改 status"""
    create_user(db_session_factory, "developer2", "developer")
    d_tok, _ = login(client, "developer2")

    m = client.post("/api/v1/experiments/modules", headers=auth_header(d_tok), json={
        "name": "To Publish", "status": "draft",
    })
    mid = m.json()["id"]

    # PATCH status 被拒绝（status 不在 Update Schema 中）
    r = client.patch(f"/api/v1/experiments/modules/{mid}", headers=auth_header(d_tok), json={
        "status": "published",
    })
    assert r.status_code == 422, r.text

    # 未绑定模板 → publish 端点被模板就绪门禁拒绝
    r = client.post(f"/api/v1/experiments/modules/{mid}/publish", headers=auth_header(d_tok))
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "MODULE_TEMPLATE_REQUIRED"


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

    cid = create_course_db(
        db_session_factory, teacher_username="teacher_t", title="Test",
        status="published", visibility="public",
    )
    ch = client.post(f"/api/v1/courses/{cid}/chapters", headers=auth_header(t_tok), json={
        "title": "Ch1",
    })
    le = client.post(f"/api/v1/chapters/{ch.json()['id']}/lessons", headers=auth_header(t_tok), json={
        "title": "Lesson", "content_type": "markdown",
    })
    client.post(f"/api/v1/courses/{cid}/enroll", headers=auth_header(s_tok))

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
    cid_a = create_course_db(
        db_session_factory, teacher_username="t_iso_a", title="教师A的课程",
        status="published", visibility="public",
    )
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
