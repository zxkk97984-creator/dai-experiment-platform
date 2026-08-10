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
    c = client.post(f"{API}/courses", headers=_h(t_tok), json={"title":"C","status":"published","visibility":"public"})
    cid = c.json()["id"]
    client.post(f"{API}/courses/{cid}/enroll", headers=_h(s_tok))
    now = datetime.datetime.now(timezone.utc)
    e = client.post(f"{API}/exams", headers=_h(t_tok), json={"course_id":cid,"title":"E","duration_minutes":60,"start_at":(now-timedelta(hours=1)).isoformat(),"end_at":(now+timedelta(hours=1)).isoformat()})
    eid = e.json()["id"]
    q1 = client.post(f"{API}/exams/{eid}/questions", headers=_h(t_tok), json={"question_type":"single_choice","prompt":"Q1","correct_answer":{"correct":["A"]},"points":10,"order_index":0,"options":{"A":"选项A","B":"选项B"}})
    assert q1.status_code == 201, q1.text
    q2 = client.post(f"{API}/exams/{eid}/questions", headers=_h(t_tok), json={"question_type":"code","prompt":"Q2","points":20,"order_index":1,"hidden_tests":"assert True","correct_answer":{},"grading_mode":"legacy"})
    assert q2.status_code == 201, q2.text
    return {"t_tok":t_tok,"s_tok":s_tok,"cid":cid,"eid":eid,"q1_id":q1.json()["id"],"q2_id":q2.json()["id"]}

def test_question_crud(client, db_session_factory):
    ctx = _setup(client, db_session_factory)
    r = client.get(f"{API}/exams/{ctx['eid']}/questions", headers=_h(ctx['t_tok']))
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2
    teacher_choice = r.json()["items"][0]
    teacher_code = r.json()["items"][1]
    assert teacher_choice["correct_answer"] == {"correct": ["A"]}
    assert teacher_code["hidden_tests"] == "assert True"


def test_student_question_response_never_leaks_private_fields(client, db_session_factory):
    ctx = _setup(client, db_session_factory)
    client.patch(f"{API}/exams/{ctx['eid']}", headers=_h(ctx['t_tok']), json={"status": "published"})
    client.post(f"{API}/exams/{ctx['eid']}/start", headers=_h(ctx['s_tok']))

    r = client.get(f"{API}/exams/{ctx['eid']}/questions", headers=_h(ctx['s_tok']))
    assert r.status_code == 200
    for question in r.json()["items"]:
        assert "correct_answer" not in question
        assert "hidden_tests" not in question
        assert "reference_solution" not in question
        assert "test_groups" not in question

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

def test_my_grade_does_not_leak_system_error(client, db_session_factory):
    """P1: my-grade 不向学生泄露原始 system_error（内部错误/配置细节）"""
    from app.models import ExamAnswer, ExamSubmission
    from sqlalchemy import select
    ctx = _setup(client, db_session_factory)
    client.patch(f"{API}/exams/{ctx['eid']}", headers=_h(ctx['t_tok']), json={"status":"published"})
    client.post(f"{API}/exams/{ctx['eid']}/start", headers=_h(ctx['s_tok']))
    client.put(f"{API}/exams/{ctx['eid']}/answers/{ctx['q2_id']}", headers=_h(ctx['s_tok']), json={"code_answer":"def f(): pass"})
    client.post(f"{API}/exams/{ctx['eid']}/submit", headers=_h(ctx['s_tok']))

    # 手动把答案置为 system_error（模拟内部错误）
    with db_session_factory() as db:
        sub = db.scalar(select(ExamSubmission).where(ExamSubmission.exam_id == ctx["eid"]))
        ans = db.scalar(select(ExamAnswer).where(
            ExamAnswer.submission_id == sub.id,
            ExamAnswer.question_id == ctx["q2_id"],
        ))
        ans.grading_status = "system_error"
        ans.score = None
        ans.last_error = "Docker 内部路径 /tmp/secret-key /var/run/xxx 堆栈"
        ans.system_error = "Docker 内部路径 /tmp/secret-key /var/run/xxx 堆栈"
        db.commit()

    r = client.get(f"{API}/exams/{ctx['eid']}/my-grade", headers=_h(ctx['s_tok']))
    assert r.status_code == 200
    body = r.text
    # 不泄露内部错误原文、路径、堆栈
    assert "Docker" not in body, "不得泄露内部错误原文"
    assert "/tmp/" not in body, "不得泄露内部路径"
    assert "secret-key" not in body, "不得泄露疑似密钥"
    assert "Traceback" not in body, "不得泄露堆栈"
    # 只暴露通用状态
    answers = r.json()["answers"]
    sys_ans = next(a for a in answers if a["question_id"] == ctx["q2_id"])
    assert sys_ans["grading_status"] == "system_error"
    assert "评分遇到系统问题" in (sys_ans.get("system_error") or ""), \
        "应返回安全通用状态而非原始错误"


def test_teacher_grades(client, db_session_factory):
    ctx = _setup(client, db_session_factory)
    client.patch(f"{API}/exams/{ctx['eid']}", headers=_h(ctx['t_tok']), json={"status":"published"})
    client.post(f"{API}/exams/{ctx['eid']}/start", headers=_h(ctx['s_tok']))
    client.put(f"{API}/exams/{ctx['eid']}/answers/{ctx['q1_id']}", headers=_h(ctx['s_tok']), json={"selected_options":["A"]})
    client.put(f"{API}/exams/{ctx['eid']}/answers/{ctx['q2_id']}", headers=_h(ctx['s_tok']), json={"code_answer":"def answer(): return True"})
    client.post(f"{API}/exams/{ctx['eid']}/submit", headers=_h(ctx['s_tok']))
    r = client.get(f"{API}/exams/{ctx['eid']}/grades", headers=_h(ctx['t_tok']))
    assert r.status_code == 200
    body = r.json()
    assert body["exam"]["title"] == "E"
    assert body["exam"]["question_count"] == 2
    assert body["summary"]["expected_count"] == 1
    assert body["summary"]["submitted_count"] == 1
    assert len(body["distribution"]) == 5
    assert body["items"][0]["student_name"]
    assert body["items"][0]["student_number"] == "e_s"
    assert body["items"][0]["submission_id"] is not None

    detail = client.get(
        f"{API}/exams/{ctx['eid']}/grades/{body['items'][0]['submission_id']}",
        headers=_h(ctx['t_tok']),
    )
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["student"]["number"] == "e_s"
    assert len(detail_body["answers"]) == 2
    assert all("correct_answer" not in answer for answer in detail_body["answers"])
    assert all("hidden_tests" not in answer for answer in detail_body["answers"])

    listing = client.get(f"{API}/exams", headers=_h(ctx['t_tok']))
    listed_exam = next(item for item in listing.json()["items"] if item["id"] == ctx["eid"])
    assert listed_exam["course_title"] == "C"
    assert listed_exam["question_count"] == 2
    assert listed_exam["participant_count"] == 1


def test_p0_maybe_finalize_checks_running_not_just_pending(client, db_session_factory):
    """P0 回归：finalize_if_ready 检查包含 running/queued 状态，不会提前汇总"""
    from app.services.exam_grading import finalize_if_ready, FinalizeOutcome
    from datetime import datetime, timezone
    from app.models import Course, Exam, ExamAnswer, ExamQuestion, ExamSubmission, User

    with db_session_factory() as db:
        teacher = User(username="p0_t", real_name="P0T", role="teacher", status="active",
                       password_hash="x")
        student = User(username="p0_s", real_name="P0S", role="student", status="active",
                       password_hash="x")
        db.add_all([teacher, student]); db.flush()
        course = Course(title="P0C", status="published", teacher_id=teacher.id)
        db.add(course); db.flush()
        exam = Exam(course_id=course.id, title="P0E", status="published", duration_minutes=60)
        db.add(exam); db.flush()
        q1 = ExamQuestion(exam_id=exam.id, question_type="code", prompt="Q1",
                          correct_answer={}, points=10, hidden_tests="assert True")
        q2 = ExamQuestion(exam_id=exam.id, question_type="code", prompt="Q2",
                          correct_answer={}, points=20, hidden_tests="assert True")
        db.add_all([q1, q2]); db.flush()
        sub = ExamSubmission(exam_id=exam.id, student_id=student.id, status="grading")
        db.add(sub); db.flush()
        ans1 = ExamAnswer(submission_id=sub.id, question_id=q1.id,
                          code_answer="def a(): pass", grading_status="completed", score=10.0)
        ans2 = ExamAnswer(submission_id=sub.id, question_id=q2.id,
                          code_answer="def b(): pass", grading_status="running")
        db.add_all([ans1, ans2]); db.commit()
        sub_id = sub.id

    # 第一次测试：存在 running 答案 → waiting，不汇总
    with db_session_factory() as db:
        r = finalize_if_ready(sub_id, db)
        assert r.outcome == FinalizeOutcome.WAITING, f"running 答案应 waiting: {r}"
        sub_check = db.get(ExamSubmission, sub_id)
        assert sub_check.status == "grading", "不应提前汇总"

    # 第二次测试：全部 completed → 应汇总
    with db_session_factory() as db:
        ans2 = db.get(ExamAnswer, ans2.id)
        ans2.grading_status = "completed"
        ans2.score = 20.0
        db.commit()

    with db_session_factory() as db:
        r2 = finalize_if_ready(sub_id, db)
        assert r2.outcome == FinalizeOutcome.GRADED
        sub_check = db.get(ExamSubmission, sub_id)
        assert sub_check.status == "graded"
        assert sub_check.score == 30.0


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


def test_exam_list_returns_is_submitted_for_student(client, db_session_factory):
    """任务中心数据源：学生考试列表返回 is_submitted（submitted/grading/graded 任一状态都算已考，与 dashboard 待办语义互补）"""
    from app.models import ExamSubmission, User
    from sqlalchemy import select

    ctx = _setup(client, db_session_factory)
    t_tok, s_tok, cid, eid = ctx["t_tok"], ctx["s_tok"], ctx["cid"], ctx["eid"]

    # 额外两个考试，用于覆盖 grading / graded 两种交后状态（eid 走真实 start→submit 流程）
    extra_ids = []
    for title in ("E-grading", "E-graded"):
        extra_id = client.post(
            f"{API}/exams", headers=_h(t_tok),
            json={"course_id": cid, "title": title, "duration_minutes": 60},
        ).json()["id"]
        r = client.post(
            f"{API}/exams/{extra_id}/questions", headers=_h(t_tok),
            json={"question_type": "single_choice", "prompt": "Q", "correct_answer": {"correct": ["A"]},
                  "points": 10, "options": {"A": "选项A", "B": "选项B"}},
        )
        assert r.status_code == 201, r.text
        extra_ids.append(extra_id)
    grading_eid, graded_eid = extra_ids

    for exam_id in [eid, grading_eid, graded_eid]:
        r = client.patch(f"{API}/exams/{exam_id}", headers=_h(t_tok), json={"status": "published"})
        assert r.status_code == 200, r.text

    def student_items():
        r = client.get(f"{API}/exams", headers=_h(s_tok))
        assert r.status_code == 200, r.text
        return {it["id"]: it["is_submitted"] for it in r.json()["items"]}

    # 未开始考试：未提交
    assert student_items()[eid] is False

    # 只开始不交卷（started）：仍视为未提交（started 不算已考，与 dashboard 待办语义一致）
    r = client.post(f"{API}/exams/{eid}/start", headers=_h(s_tok))
    assert r.status_code == 201, r.text
    assert student_items()[eid] is False

    # 交卷后（真实流程，状态为 submitted/grading 之一）：已提交
    r = client.post(f"{API}/exams/{eid}/submit", headers=_h(s_tok))
    assert r.status_code == 201, r.text
    assert student_items()[eid] is True

    # 手动构造 grading / graded 提交记录：同样视为已提交
    with db_session_factory() as db:
        student = db.scalar(select(User).where(User.username == "e_s"))
        for exam_id, status in ((grading_eid, "grading"), (graded_eid, "graded")):
            db.add(ExamSubmission(exam_id=exam_id, student_id=student.id, status=status))
        db.commit()
    by_id = student_items()
    assert by_id[grading_eid] is True
    assert by_id[graded_eid] is True

    # 教师视角不计算学生提交状态：默认 False
    r = client.get(f"{API}/exams", headers=_h(t_tok))
    assert r.status_code == 200, r.text
    teacher_items = {it["id"]: it["is_submitted"] for it in r.json()["items"]}
    assert all(v is False for v in teacher_items.values()), teacher_items
