"""Task 8: 教师实验评分反馈——权限、评分落库、终态"""
import uuid

from sqlalchemy import select
from app.models import ExperimentRecord, ExperimentSubmission, Lesson
from conftest import auth_header, create_user, login

API = "/api/v1"


def _setup_submission(client, db_sf):
    """创建已提交的实验记录（带 notebook template）"""
    create_user(db_sf, "erv_t", "teacher")
    create_user(db_sf, "erv_s", "student")
    t_tok, _ = login(client, "erv_t")
    s_tok, _ = login(client, "erv_s")

    c = client.post(f"{API}/courses", headers=auth_header(t_tok),
                    json={"title": "RVC", "status": "published", "visibility": "public"})
    cid = c.json()["id"]
    client.post(f"{API}/courses/{cid}/enroll", headers=auth_header(s_tok))
    ch = client.post(f"{API}/courses/{cid}/chapters", headers=auth_header(t_tok),
                     json={"title": "Ch1", "order_index": 1})
    chid = ch.json()["id"]

    with db_sf() as db:
        from app.models import NotebookTemplate, NotebookTemplateVersion, User
        teacher = db.scalar(select(User).where(User.username == "erv_t"))
        tpl = NotebookTemplate(name="RevNB", description="x", status="published",
                               owner_id=teacher.id, draft_cells=[], draft_revision=1)
        db.add(tpl); db.flush()
        ver = NotebookTemplateVersion(
            template_id=tpl.id,
            version_number=1,
            sha256="abc",
            cells=[
                {"id": "m1", "type": "markdown", "source": "# Instructions", "order": 0},
                {"id": "c1", "type": "code", "source": "x", "order": 1},
            ],
            cell_order=["m1", "c1"],
            published_by_id=teacher.id,
        )
        db.add(ver); db.flush()
        tpl.current_version_id = ver.id
        db.commit()
        nbid = tpl.id

    le = client.post(f"{API}/chapters/{chid}/lessons", headers=auth_header(t_tok), json={
        "title": "L1", "content_type": "notebook", "order_index": 1,
    })
    leid = le.json()["id"]
    with db_sf() as db:
        lesson = db.get(Lesson, leid)
        lesson.template_id = nbid
        db.commit()

    rec = client.post(f"{API}/experiments/records/ensure-for-lesson/{leid}",
                      headers=auth_header(s_tok))
    rid = rec.json()["id"]
    with db_sf() as db:
        record = db.get(ExperimentRecord, rid)
        record.cells_sources = {"c1": "print('submitted')"}
        record.cells_outputs = {
            "c1": {
                "execution_count": 1,
                "outputs": [{"output_type": "stream", "text": "submitted\n"}],
            }
        }
        db.commit()
    sub = client.post(f"{API}/experiments/records/{rid}/submit",
                      headers=auth_header(s_tok),
                      json={"client_request_id": str(uuid.uuid4())})
    return {"t_tok": t_tok, "s_tok": s_tok, "rid": rid, "sub_id": sub.json()["id"],
            "cid": cid}


def test_submission_detail_returns_immutable_cell_context(client, db_session_factory):
    """详情返回模板元数据和提交时输出，后续 record 变化不污染历史快照。"""
    ctx = _setup_submission(client, db_session_factory)

    with db_session_factory() as db:
        record = db.get(ExperimentRecord, ctx["rid"])
        record.cells_outputs = {
            "c1": {
                "execution_count": 2,
                "outputs": [{"output_type": "stream", "text": "changed\n"}],
            }
        }
        db.commit()

    r = client.get(
        f"{API}/experiments/submissions/{ctx['sub_id']}",
        headers=auth_header(ctx["t_tok"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cells_snapshot"]["m1"] == "# Instructions"
    assert body["cell_metadata"] == {
        "m1": {"type": "markdown", "order": 0},
        "c1": {"type": "code", "order": 1},
    }
    assert body["outputs_snapshot"]["c1"]["execution_count"] == 1
    assert body["outputs_snapshot"]["c1"]["outputs"][0]["text"] == "submitted\n"


# ═══════════════════════════════════════════════════════════════
# 1. 教师评分成功
# ═══════════════════════════════════════════════════════════════

def test_teacher_can_review_submission(client, db_session_factory):
    """教师可对自己的课程提交评分"""
    ctx = _setup_submission(client, db_session_factory)

    r = client.patch(f"{API}/experiments/submissions/{ctx['sub_id']}/review",
                     headers=auth_header(ctx["t_tok"]),
                     json={"score": 85.0, "feedback": "做得不错"})
    assert r.status_code == 200, r.text
    assert r.json()["score"] == 85.0
    assert r.json()["feedback"] == "做得不错"
    assert r.json()["reviewed_by_id"] is not None

    # 验证 record 状态变为 graded
    rec = client.get(f"{API}/experiments/records/{ctx['rid']}",
                     headers=auth_header(ctx["s_tok"]))
    assert rec.json()["status"] == "graded"


# ═══════════════════════════════════════════════════════════════
# 2. 跨教师越权
# ═══════════════════════════════════════════════════════════════

def test_other_teacher_cannot_review(client, db_session_factory):
    """另一教师无法评分他人的课程提交"""
    ctx = _setup_submission(client, db_session_factory)
    create_user(db_session_factory, "erv_t2", "teacher")
    t2_tok, _ = login(client, "erv_t2")

    r = client.patch(f"{API}/experiments/submissions/{ctx['sub_id']}/review",
                     headers=auth_header(t2_tok),
                     json={"score": 90.0})
    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════
# 3. 学生不能评分
# ═══════════════════════════════════════════════════════════════

def test_student_cannot_review(client, db_session_factory):
    """学生不能评分"""
    ctx = _setup_submission(client, db_session_factory)

    r = client.patch(f"{API}/experiments/submissions/{ctx['sub_id']}/review",
                     headers=auth_header(ctx["s_tok"]),
                     json={"score": 100.0})
    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════
# 4. 评分后不可再次提交
# ═══════════════════════════════════════════════════════════════

def test_cannot_submit_after_graded(client, db_session_factory):
    """评分后 record 状态为 graded，不能再提交"""
    ctx = _setup_submission(client, db_session_factory)

    # 教师评分
    client.patch(f"{API}/experiments/submissions/{ctx['sub_id']}/review",
                 headers=auth_header(ctx["t_tok"]),
                 json={"score": 90.0})

    # 学生尝试再次提交
    r = client.post(f"{API}/experiments/records/{ctx['rid']}/submit",
                    headers=auth_header(ctx["s_tok"]),
                    json={"client_request_id": str(uuid.uuid4())})
    assert r.status_code == 400, f"评分后应拒绝提交: {r.status_code}"
