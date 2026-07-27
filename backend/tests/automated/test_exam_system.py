"""考试系统测试"""
import datetime, pytest
from datetime import timezone, timedelta
from conftest import auth_header, create_user, login
API = "/api/v1"

def _h(token): return auth_header(token)

def _setup(client, db_session_factory):
    create_user(db_session_factory, "e_t", "teacher")
    create_user(db_session_factory, "e_s", "student")
    t_tok, _ = login(client, "e_t")
    s_tok, _ = login(client, "e_s")
    c = client.post(f"{API}/courses", headers=_h(t_tok), json={"title":"C","status":"published"})
    cid = c.json()["id"]
    client.post(f"{API}/courses/{cid}/enroll", headers=_h(s_tok))
    now = datetime.datetime.now(timezone.utc)
    e = client.post(f"{API}/exams", headers=_h(t_tok), json={"course_id":cid,"title":"E","duration_minutes":60,"start_at":(now-timedelta(hours=1)).isoformat(),"end_at":(now+timedelta(hours=1)).isoformat()})
    eid = e.json()["id"]
    q1 = client.post(f"{API}/exams/{eid}/questions", headers=_h(t_tok), json={"question_type":"single_choice","prompt":"Q1","correct_answer":{"correct":["A"]},"points":10,"order_index":0})
    assert q1.status_code == 201, q1.text
    q2 = client.post(f"{API}/exams/{eid}/questions", headers=_h(t_tok), json={"question_type":"code","prompt":"Q2","points":20,"order_index":1,"hidden_tests":"assert True","correct_answer":{}})
    assert q2.status_code == 201, q2.text
    return {"t_tok":t_tok,"s_tok":s_tok,"cid":cid,"eid":eid,"q1_id":q1.json()["id"],"q2_id":q2.json()["id"]}

def test_question_crud(client, db_session_factory):
    ctx = _setup(client, db_session_factory)
    r = client.get(f"{API}/exams/{ctx['eid']}/questions", headers=_h(ctx['t_tok']))
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2

def test_publish_locks_questions(client, db_session_factory):
    ctx = _setup(client, db_session_factory)
    client.patch(f"{API}/exams/{ctx['eid']}", headers=_h(ctx['t_tok']), json={"status":"published"})
    r = client.post(f"{API}/exams/{ctx['eid']}/questions", headers=_h(ctx['t_tok']), json={"question_type":"single_choice","prompt":"L","correct_answer":{"correct":["A"]},"points":5})
    assert r.status_code == 403

def test_start_and_submit(client, db_session_factory):
    ctx = _setup(client, db_session_factory)
    client.patch(f"{API}/exams/{ctx['eid']}", headers=_h(ctx['t_tok']), json={"status":"published"})
    r = client.post(f"{API}/exams/{ctx['eid']}/start", headers=_h(ctx['s_tok']))
    assert r.status_code == 201
    r = client.put(f"{API}/exams/{ctx['eid']}/answers/{ctx['q1_id']}", headers=_h(ctx['s_tok']), json={"selected_options":["A"]})
    assert r.status_code == 201
    r = client.post(f"{API}/exams/{ctx['eid']}/submit", headers=_h(ctx['s_tok']))
    assert r.status_code == 201
    r = client.get(f"{API}/exams/{ctx['eid']}/my-grade", headers=_h(ctx['s_tok']))
    assert r.status_code == 200
    assert r.json()["status"] in ("graded","grading")

def test_teacher_grades(client, db_session_factory):
    ctx = _setup(client, db_session_factory)
    client.patch(f"{API}/exams/{ctx['eid']}", headers=_h(ctx['t_tok']), json={"status":"published"})
    client.post(f"{API}/exams/{ctx['eid']}/start", headers=_h(ctx['s_tok']))
    client.post(f"{API}/exams/{ctx['eid']}/submit", headers=_h(ctx['s_tok']))
    r = client.get(f"{API}/exams/{ctx['eid']}/grades", headers=_h(ctx['t_tok']))
    assert r.status_code == 200


def test_p0_maybe_finalize_checks_running_not_just_pending(client, db_session_factory):
    """P0 回归：_maybe_finalize 检查包含 running 状态，不会在 Worker 运行中提前汇总"""
    from app.services.exam_service import _maybe_finalize
    from unittest.mock import MagicMock

    # 模拟 submission.status == "grading" 但有 running 的答案
    mock_sub = MagicMock()
    mock_sub.status = "grading"
    mock_sub.id = 1
    db = MagicMock()
    # unfinished check 返回有值（存在 running 答案）
    db.scalar.return_value = MagicMock()

    _maybe_finalize(mock_sub, db)

    # 因为存在未完成答案，不应查询 total 或调用 _finalize_grade
    assert db.scalar.call_count == 1, f"应在发现未完成后立即返回，调用了 {db.scalar.call_count} 次"
    assert not db.commit.called

    # 第二次测试：全部 completed → 应汇总
    db2 = MagicMock()
    mock_sub2 = MagicMock()
    mock_sub2.status = "grading"
    mock_sub2.id = 2
    # unfinished=None, total=100.0, grade lookup in _finalize_grade
    db2.scalar.side_effect = [None, 100.0, None]

    _maybe_finalize(mock_sub2, db2)
    assert db2.scalar.call_count >= 3, "确认无未完成后应查询 total + 汇总"
    assert db2.commit.called, "应提交最终成绩"


def test_p1_resubmit_idempotent(client, db_session_factory):
    """P1 回归：重复交卷返回当前状态，不报 403"""
    ctx = _setup(client, db_session_factory)
    client.patch(f"{API}/exams/{ctx['eid']}", headers=_h(ctx['t_tok']), json={"status": "published"})
    client.post(f"{API}/exams/{ctx['eid']}/start", headers=_h(ctx['s_tok']))
    # 第一次交卷
    r1 = client.post(f"{API}/exams/{ctx['eid']}/submit", headers=_h(ctx['s_tok']))
    assert r1.status_code == 201
    # 第二次交卷（幂等）
    r2 = client.post(f"{API}/exams/{ctx['eid']}/submit", headers=_h(ctx['s_tok']))
    assert r2.status_code in (200, 201), f"重复交卷不应 403: {r2.status_code}"
