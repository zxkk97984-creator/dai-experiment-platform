"""教师工作台 V3：聚合计数、统一提交中心、全局搜索、班级范围与成绩总览。"""

from datetime import datetime, timedelta, timezone

from conftest import auth_header, create_user, login, seed_basic_environment

NOW = datetime.now(timezone.utc)


def _seed(db_session_factory):
    seed_basic_environment(db_session_factory)
    from app.models import (
        AcademicTerm, Assignment, Chapter, Course, CourseEnrollment,
        CourseTeachingClass, Exam, ExamSubmission, ExperimentRecord,
        ExperimentSubmission, JudgeQuestion, Lesson, NotebookTemplate,
        NotebookTemplateVersion, Submission, TeachingClass, TeachingClassStudent,
    )

    teacher = create_user(db_session_factory, "wb-teacher", "teacher", real_name="工作台教师")
    teacher.department = "计算机学院"
    other = create_user(db_session_factory, "wb-other", "teacher")
    student = create_user(db_session_factory, "wb-student", "student", real_name="陈雨桐")
    student.student_no = "2026011203"

    with db_session_factory() as db:
        db.add(teacher)
        db.add(student)
        db.commit()

        course_a = Course(title="机器学习基础", status="published", teacher_id=teacher.id)
        course_b = Course(title="其他课程", status="published", teacher_id=other.id)
        db.add_all([course_a, course_b])
        db.flush()

        term = AcademicTerm(code="2026-FALL", name="2026 秋季学期", start_date=NOW.date(), end_date=NOW.date() + timedelta(days=90), status="active")
        db.add(term)
        db.flush()
        class_a = TeachingClass(academic_term_id=term.id, code="CS01", name="计科 2601", status="active")
        class_b = TeachingClass(academic_term_id=term.id, code="CS02", name="计科 2602", status="active")
        db.add_all([class_a, class_b])
        db.flush()
        db.add_all([
            CourseTeachingClass(course_id=course_a.id, teaching_class_id=class_a.id),
            CourseTeachingClass(course_id=course_b.id, teaching_class_id=class_b.id),
            TeachingClassStudent(teaching_class_id=class_a.id, student_id=student.id, status="active"),
            CourseEnrollment(course_id=course_a.id, student_id=student.id, status="enrolled"),
        ])

        chapter = Chapter(course_id=course_a.id, title="第一章")
        db.add(chapter)
        db.flush()
        lesson = Lesson(chapter_id=chapter.id, title="卷积神经网络 · 图像分类", due_at=NOW + timedelta(days=1))
        db.add(lesson)
        db.flush()

        assignment = Assignment(
            course_id=course_a.id, title="特征工程", status="published",
            due_at=NOW + timedelta(days=1),
        )
        db.add(assignment)
        db.flush()
        q1 = JudgeQuestion(assignment_id=assignment.id, title="特征工程题", function_name="featurize", hidden_tests="")
        q2 = JudgeQuestion(assignment_id=assignment.id, title="清洗题", function_name="clean", hidden_tests="")
        db.add_all([q1, q2])
        db.flush()
        db.add_all([
            Submission(
                question_id=q1.id, student_id=student.id, code="pass",
                status="completed", grading_status="completed", score=88.0,
                tests_passed=12, tests_total=12,
                created_at=NOW - timedelta(hours=2),
                finished_at=NOW - timedelta(hours=1),
            ),
            Submission(
                question_id=q2.id, student_id=student.id, code="queued",
                status="queued", grading_status="queued", score=None,
                created_at=NOW - timedelta(minutes=20),
            ),
        ])

        exam = Exam(
            course_id=course_a.id, title="期中考试", status="published",
            start_at=NOW - timedelta(days=1), end_at=NOW - timedelta(hours=1),
        )
        db.add(exam)
        db.flush()
        db.add(ExamSubmission(
            exam_id=exam.id, student_id=student.id, status="graded",
            score=76.0, submitted_at=NOW - timedelta(hours=2),
            graded_at=NOW - timedelta(minutes=30),
        ))

        tpl = NotebookTemplate(name="CNN 模板", status="published", owner_id=teacher.id)
        db.add(tpl)
        db.flush()
        ver = NotebookTemplateVersion(
            template_id=tpl.id, version_number=1, sha256="x" * 64,
            cells=[], cell_order=[], notebook_metadata={}, published_by_id=teacher.id,
        )
        db.add(ver)
        db.flush()
        record = ExperimentRecord(
            lesson_id=lesson.id, template_version_id=ver.id,
            student_id=student.id, status="submitted",
            submitted_at=NOW - timedelta(minutes=30),
        )
        db.add(record)
        db.flush()
        db.add(ExperimentSubmission(
            record_id=record.id, attempt_number=1, client_request_id="wb-exp-1",
            cells_snapshot={}, submitted_at=NOW - timedelta(minutes=30),
        ))
        db.commit()
        return {
            "teacher": teacher, "other": other, "student": student,
            "course_a": course_a, "course_b": course_b,
            "lesson": lesson, "assignment": assignment, "exam": exam,
            "class_a": class_a, "class_b": class_b,
        }


def test_teacher_counts_and_dashboard_v3(client, db_session_factory):
    _seed(db_session_factory)
    token, user = login(client, "wb-teacher")
    headers = auth_header(token)

    counts = client.get("/api/v1/dashboard/teacher/counts", headers=headers)
    assert counts.status_code == 200
    body = counts.json()
    assert body["pending_grading_count"] == 2  # 实验未评分 + 作业队列中
    assert body["pending_release_count"] == 1
    assert body["upcoming_deadline_count"] == 1

    dashboard = client.get("/api/v1/dashboard/teacher", headers=headers).json()
    assert dashboard["summary"]["active_course_count"] == 1
    kinds = {item["kind"] for item in dashboard["work_items"]}
    assert "experiment_review" in kinds
    assert "assignment_grading" in kinds
    assert "exam_release" in kinds
    recent_kinds = {row["kind"] for row in dashboard["recent_submissions"]}
    assert recent_kinds >= {"experiment", "assignment", "exam"}
    assert any(row["student_no"] == "2026011203" for row in dashboard["recent_submissions"])


def test_unified_submissions_filters_and_scopes(client, db_session_factory):
    g = _seed(db_session_factory)
    token, _ = login(client, "wb-teacher")
    headers = auth_header(token)

    body = client.get("/api/v1/submissions/unified", headers=headers).json()
    assert body["total"] == 4
    assert body["summary"]["pending"] == 2
    assert body["summary"]["graded"] == 2
    assert body["summary"]["failed"] == 0

    assignment_pending = client.get(
        "/api/v1/submissions/unified",
        params={"kind": "assignment", "status": "pending_grading", "entry_id": g["assignment"].id},
        headers=headers,
    ).json()
    assert assignment_pending["total"] == 1
    assert assignment_pending["items"][0]["route"].startswith("/teacher/judge-submissions/")

    graded_assignment = next(
        row for row in body["items"]
        if row["kind"] == "assignment" and row["status"] == "graded"
    )
    detail = client.get(
        f"/api/v1/judge/submissions/{graded_assignment['id']}/teacher",
        headers=headers,
    ).json()
    assert detail["student_no"] == "2026011203"
    assert detail["tests_passed"] == 12
    assert detail["assignment_title"] == "特征工程"

    other_token, _ = login(client, "wb-other")
    other_body = client.get("/api/v1/submissions/unified", headers=auth_header(other_token)).json()
    assert other_body["total"] == 0


def test_global_search_is_role_scoped(client, db_session_factory):
    _seed(db_session_factory)
    token, _ = login(client, "wb-teacher")
    headers = auth_header(token)

    body = client.get("/api/v1/search", params={"q": "2026011203"}, headers=headers).json()
    assert len(body["students"]) == 1
    assert body["students"][0]["subtitle"] == "2026011203"
    assert len(body["submissions"]) >= 1

    other_token, _ = login(client, "wb-other")
    other_body = client.get("/api/v1/search", params={"q": "2026011203"}, headers=auth_header(other_token)).json()
    assert other_body["students"] == []
    assert other_body["submissions"] == []


def test_teacher_class_list_and_roster_are_scoped(client, db_session_factory):
    g = _seed(db_session_factory)
    token, _ = login(client, "wb-teacher")
    headers = auth_header(token)

    classes = client.get("/api/v1/teaching-classes", params={"scope": "linked"}, headers=headers).json()
    assert [item["id"] for item in classes["items"]] == [g["class_a"].id]

    roster = client.get(
        f"/api/v1/teaching-classes/{g['class_a'].id}/students", headers=headers,
    )
    assert roster.status_code == 200
    assert [item["id"] for item in roster.json()["items"]] == [g["student"].id]

    other_token, _ = login(client, "wb-other")
    denied = client.get(
        f"/api/v1/teaching-classes/{g['class_a'].id}/students",
        headers=auth_header(other_token),
    )
    assert denied.status_code == 403


def test_teacher_grade_statistics(client, db_session_factory):
    _seed(db_session_factory)
    token, _ = login(client, "wb-teacher")
    body = client.get("/api/v1/teacher/grade-statistics", headers=auth_header(token)).json()
    assert body["exam_count"] == 1
    assert body["graded_count"] == 1
    assert body["average_score"] == 76.0
    assert body["pass_rate"] == 100.0
    assert body["exams"][0]["course_title"] == "机器学习基础"


def test_notifications_persist_and_read(client, db_session_factory):
    _seed(db_session_factory)
    token, _ = login(client, "wb-teacher")
    headers = auth_header(token)

    first = client.get("/api/v1/notifications", headers=headers)
    assert first.status_code == 200
    body = first.json()
    assert body["unread_count"] >= 1
    assert len(body["items"]) >= 1

    notice_id = body["items"][0]["id"]
    assert client.post(f"/api/v1/notifications/{notice_id}/read", headers=headers).status_code == 204
    second = client.get("/api/v1/notifications", headers=headers).json()
    assert second["unread_count"] == body["unread_count"] - 1

    assert client.post("/api/v1/notifications/read-all", headers=headers).status_code == 204
    third = client.get("/api/v1/notifications", headers=headers).json()
    assert third["unread_count"] == 0


def test_user_preferences_persist(client, db_session_factory):
    create_user(db_session_factory, "wb-pref-teacher", "teacher")
    token, _ = login(client, "wb-pref-teacher")
    headers = auth_header(token)

    created = client.patch(
        "/api/v1/users/me/preferences",
        json={"sidebar_collapsed": True, "preferred_page_size": 25},
        headers=headers,
    )
    assert created.status_code == 200
    assert created.json()["preferences"]["sidebar_collapsed"] is True

    fetched = client.get("/api/v1/users/me/preferences", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["preferences"] == {
        "sidebar_collapsed": True,
        "preferred_page_size": 25,
    }


def test_course_student_csv_import(client, db_session_factory):
    g = _seed(db_session_factory)
    token, _ = login(client, "wb-teacher")
    headers = auth_header(token)
    csv_content = "学号,姓名,账号\n2026011203,陈雨桐,wb-student\nNOT_EXISTS,不存在,missing\n"
    response = client.post(
        f"/api/v1/courses/{g['course_a'].id}/students/import",
        files={"file": ("roster.csv", csv_content.encode("utf-8-sig"), "text/csv")},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["created"] + body["updated"] == 1
    assert body["skipped"] == 1
    assert body["errors"][0]["row"] == 2

    roster = client.get(
        f"/api/v1/courses/{g['course_a'].id}/students", headers=headers,
    ).json()
    assert any(item["student_no"] == "2026011203" for item in roster["items"])
