"""考试全链路 v2：服务器状态、完整个人时长、自动保存、填空与讲评公开。"""

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import Course, Exam, ExamSubmission
from app.services.time_utils import as_utc, utc_now
from conftest import auth_header, create_user, login

API = "/api/v1"


def _seed(client, db_sf, *, question=None, duration=60, start_delta=-10, end_delta=30):
    teacher_user = create_user(db_sf, "life_teacher", "teacher")
    create_user(db_sf, "life_student", "student")
    teacher, _ = login(client, "life_teacher")
    student, _ = login(client, "life_student")
    with db_sf() as db:
        course = Course(title="Lifecycle", description="d", status="published",
                        visibility="public", default_score=100, teacher_id=teacher_user.id)
        db.add(course)
        db.commit()
        course_id = course.id
    client.post(f"{API}/courses/{course_id}/enroll", headers=auth_header(student))
    now = utc_now()
    exam = client.post(f"{API}/exams", headers=auth_header(teacher), json={
        "course_id": course_id,
        "title": "Server Clock Exam",
        "duration_minutes": duration,
        "start_at": (now + timedelta(minutes=start_delta)).isoformat(),
        "end_at": (now + timedelta(minutes=end_delta)).isoformat(),
    })
    exam_id = exam.json()["id"]
    question = question or {
        "question_type": "single_choice",
        "prompt": "2 + 2 = ?",
        "options": {"A": "4", "B": "5"},
        "correct_answer": {"correct": ["A"]},
        "points": 10,
    }
    created_question = client.post(
        f"{API}/exams/{exam_id}/questions", headers=auth_header(teacher), json=question,
    )
    assert created_question.status_code == 201, created_question.text
    return {
        "teacher": teacher, "student": student, "exam_id": exam_id,
        "question_id": created_question.json()["id"], "course_id": course_id,
    }


def test_draft_hidden_and_future_exam_never_exposes_questions(client, db_session_factory):
    ctx = _seed(client, db_session_factory, start_delta=30, end_delta=60)
    student_headers = auth_header(ctx["student"])
    assert client.get(f"{API}/exams", headers=student_headers).json()["total"] == 0
    assert client.get(f"{API}/exams/{ctx['exam_id']}", headers=student_headers).status_code == 403

    published = client.patch(
        f"{API}/exams/{ctx['exam_id']}", headers=auth_header(ctx["teacher"]), json={"status": "published"},
    )
    assert published.status_code == 200, published.text
    summary = client.get(f"{API}/exams", headers=student_headers).json()["items"][0]
    assert summary["student_status"] == "scheduled"
    assert summary["can_start"] is False
    session = client.get(f"{API}/exams/{ctx['exam_id']}/session", headers=student_headers).json()
    assert session["questions"] == []
    assert client.post(f"{API}/exams/{ctx['exam_id']}/start", headers=student_headers).status_code == 403
    assert client.get(f"{API}/exams/{ctx['exam_id']}/questions", headers=student_headers).status_code == 403


def test_late_entry_receives_full_duration_not_global_window_cap(client, db_session_factory):
    ctx = _seed(client, db_session_factory, duration=60, start_delta=-5, end_delta=5)
    client.patch(f"{API}/exams/{ctx['exam_id']}", headers=auth_header(ctx["teacher"]), json={"status": "published"})
    before = utc_now()
    started = client.post(f"{API}/exams/{ctx['exam_id']}/start", headers=auth_header(ctx["student"]))
    assert started.status_code == 201, started.text
    expires = as_utc(datetime.fromisoformat(started.json()["expires_at"]))
    assert expires >= before + timedelta(minutes=59, seconds=50)


def test_autosave_versions_restore_and_detect_conflicts(client, db_session_factory):
    ctx = _seed(client, db_session_factory)
    client.patch(f"{API}/exams/{ctx['exam_id']}", headers=auth_header(ctx["teacher"]), json={"status": "published"})
    headers = auth_header(ctx["student"])
    client.post(f"{API}/exams/{ctx['exam_id']}/start", headers=headers)
    first = client.put(f"{API}/exams/{ctx['exam_id']}/answers", headers=headers, json={"answers": [{
        "question_id": ctx["question_id"], "selected_options": ["A"], "expected_version": 0,
    }]})
    assert first.json()["results"][0]["version"] == 1
    restored = client.get(f"{API}/exams/{ctx['exam_id']}/session", headers=headers).json()["saved_answers"][0]
    assert restored["selected_options"] == ["A"]
    assert restored["version"] == 1
    conflict = client.put(f"{API}/exams/{ctx['exam_id']}/answers", headers=headers, json={"answers": [{
        "question_id": ctx["question_id"], "selected_options": ["B"], "expected_version": 0,
    }]})
    assert conflict.json()["results"][0]["ok"] is False
    assert conflict.json()["results"][0]["code"] == "ANSWER_VERSION_CONFLICT"


def test_deadline_submit_is_idempotent_and_start_retry_restores_existing_attempt(client, db_session_factory):
    ctx = _seed(client, db_session_factory)
    client.patch(f"{API}/exams/{ctx['exam_id']}", headers=auth_header(ctx["teacher"]), json={"status": "published"})
    started = client.post(f"{API}/exams/{ctx['exam_id']}/start", headers=auth_header(ctx["student"]))
    assert started.status_code == 201

    with db_session_factory() as db:
        submission = db.scalar(select(ExamSubmission).where(ExamSubmission.exam_id == ctx["exam_id"]))
        exam = db.get(Exam, ctx["exam_id"])
        # 已经开始后，即使全局最晚进入时间过去，start 重试也应恢复同一记录。
        exam.end_at = utc_now() - timedelta(seconds=1)
        db.commit()
    retried = client.post(f"{API}/exams/{ctx['exam_id']}/start", headers=auth_header(ctx["student"]))
    assert retried.status_code == 201
    assert retried.json()["id"] == started.json()["id"]

    with db_session_factory() as db:
        submission = db.get(ExamSubmission, started.json()["id"])
        submission.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    first = client.post(f"{API}/exams/{ctx['exam_id']}/submit", headers=auth_header(ctx["student"]))
    second = client.post(f"{API}/exams/{ctx['exam_id']}/submit", headers=auth_header(ctx["student"]))
    assert first.status_code == second.status_code == 201
    assert first.json()["submission"]["submission_reason"] == "time_expired"
    assert second.json()["id"] == first.json()["id"]


def test_started_exam_allows_public_policy_changes_but_never_shortens_entry_window(client, db_session_factory):
    ctx = _seed(client, db_session_factory)
    teacher_headers = auth_header(ctx["teacher"])
    published = client.patch(f"{API}/exams/{ctx['exam_id']}", headers=teacher_headers, json={"status": "published"})
    client.post(f"{API}/exams/{ctx['exam_id']}/start", headers=auth_header(ctx["student"]))

    policy = client.patch(f"{API}/exams/{ctx['exam_id']}", headers=teacher_headers, json={
        "duration_minutes": published.json()["duration_minutes"],
        "start_at": published.json()["start_at"],
        "end_at": published.json()["end_at"],
        "show_score_after_grading": True,
    })
    assert policy.status_code == 200, policy.text
    assert policy.json()["show_score_after_grading"] is True

    shortened = client.patch(f"{API}/exams/{ctx['exam_id']}", headers=teacher_headers, json={
        "end_at": (utc_now() + timedelta(minutes=1)).isoformat(),
    })
    cleared = client.patch(f"{API}/exams/{ctx['exam_id']}", headers=teacher_headers, json={"end_at": None})
    assert shortened.status_code == cleared.status_code == 409


def test_fill_blank_partial_scoring_visibility_and_manual_review(client, db_session_factory):
    fill = {
        "question_type": "fill_blank",
        "prompt": "函数关键字是 [[blank:first]]，空值是 [[blank:second]]。",
        "correct_answer": {"blanks": [
            {"id": "first", "accepted_answers": ["def"], "case_sensitive": False},
            {"id": "second", "accepted_answers": ["None", "null"], "case_sensitive": False},
        ]},
        "points": 10,
    }
    ctx = _seed(client, db_session_factory, question=fill)
    teacher_headers = auth_header(ctx["teacher"])
    student_headers = auth_header(ctx["student"])
    assert client.patch(f"{API}/exams/{ctx['exam_id']}", headers=teacher_headers, json={"status": "published"}).status_code == 200
    started = client.post(f"{API}/exams/{ctx['exam_id']}/start", headers=student_headers).json()
    assert "correct_answer" not in started["questions"][0]
    saved = client.put(f"{API}/exams/{ctx['exam_id']}/answers", headers=student_headers, json={"answers": [{
        "question_id": ctx["question_id"],
        "text_answers": {"first": " DEF ", "second": "wrong"},
        "expected_version": 0,
    }]})
    assert saved.json()["results"][0]["ok"] is True
    submitted = client.post(f"{API}/exams/{ctx['exam_id']}/submit", headers=student_headers).json()
    assert submitted["status"] == "graded"
    assert submitted["score"] is None
    assert submitted["exam"]["max_score"] == 10

    client.patch(f"{API}/exams/{ctx['exam_id']}", headers=teacher_headers, json={
        "show_score_after_grading": True,
        "show_questions_after_review": True,
        "show_answers_after_review": True,
    })
    score_session = client.get(f"{API}/exams/{ctx['exam_id']}/session", headers=student_headers).json()
    assert score_session["submission"]["score"] == 5.0
    assert score_session["questions"] == []
    assert client.post(f"{API}/exams/{ctx['exam_id']}/review-release", headers=teacher_headers).status_code == 409

    with db_session_factory() as db:
        exam = db.get(Exam, ctx["exam_id"])
        exam.end_at = utc_now() - timedelta(seconds=1)
        db.commit()
    released = client.post(f"{API}/exams/{ctx['exam_id']}/review-release", headers=teacher_headers)
    assert released.status_code == 200, released.text
    review = client.get(f"{API}/exams/{ctx['exam_id']}/session", headers=student_headers).json()
    assert review["visibility"] == {"score": True, "questions": True, "answers": True, "review_released": True}
    assert review["questions"][0]["correct_answer"]["blanks"][0]["accepted_answers"] == ["def"]
    assert review["saved_answers"][0]["text_answers"]["first"] == " DEF "
    assert review["saved_answers"][0]["score"] == 5.0


def test_teacher_force_submit_records_reason(client, db_session_factory):
    ctx = _seed(client, db_session_factory)
    teacher_headers = auth_header(ctx["teacher"])
    student_headers = auth_header(ctx["student"])
    client.patch(f"{API}/exams/{ctx['exam_id']}", headers=teacher_headers, json={"status": "published"})
    started = client.post(f"{API}/exams/{ctx['exam_id']}/start", headers=student_headers).json()
    forced = client.post(
        f"{API}/exams/{ctx['exam_id']}/submissions/{started['id']}/force-submit", headers=teacher_headers,
    )
    assert forced.status_code == 200
    assert forced.json()["submission_reason"] == "teacher_forced"
    with db_session_factory() as db:
        submission = db.scalar(select(ExamSubmission).where(ExamSubmission.id == started["id"]))
        assert submission.status == "graded"
