from datetime import date

from app.models import CourseEnrollment, User
from tests.automated.conftest import auth_header, create_user, login


API = "/api/v1"


def _setup(client, db_session_factory):
    admin = create_user(db_session_factory, "academic_admin", "admin")
    teacher = create_user(db_session_factory, "academic_teacher", "teacher")
    student = create_user(db_session_factory, "academic_student", "student", real_name="陈同学")
    with db_session_factory() as db:
        db.get(User, student.id).student_no = "20260088"
        db.commit()
    admin_token, _ = login(client, admin.username)
    teacher_token, _ = login(client, teacher.username)
    student_token, _ = login(client, student.username)
    return admin, teacher, student, admin_token, teacher_token, student_token


def test_class_roster_syncs_course_counts_and_student_metadata(client, db_session_factory):
    _admin, _teacher, student, admin_token, teacher_token, student_token = _setup(client, db_session_factory)
    term = client.post(f"{API}/academic-terms", headers=auth_header(admin_token), json={
        "code": "2026-FALL", "name": "2026 秋季学期",
        "start_date": str(date(2026, 9, 1)), "end_date": str(date(2027, 1, 20)), "status": "active",
    })
    assert term.status_code == 201, term.text
    class_resp = client.post(f"{API}/teaching-classes", headers=auth_header(admin_token), json={
        "academic_term_id": term.json()["id"], "code": "CS-01", "name": "计算机一班",
    })
    assert class_resp.status_code == 201, class_resp.text
    class_id = class_resp.json()["id"]
    add = client.post(f"{API}/teaching-classes/{class_id}/students", headers=auth_header(admin_token), json={"student_ids": [student.id]})
    assert add.status_code == 200, add.text

    course = client.post(f"{API}/courses", headers=auth_header(teacher_token), json={
        "title": "数据结构", "status": "published", "visibility": "private",
        "academic_term_id": term.json()["id"], "teaching_class_ids": [class_id],
    })
    assert course.status_code == 201, course.text
    body = course.json()
    assert body["academic_term"]["name"] == "2026 秋季学期"
    assert body["teaching_classes"][0]["name"] == "计算机一班"
    assert body["student_count"] == 1

    listing = client.get(f"{API}/courses", headers=auth_header(teacher_token)).json()
    assert listing["items"][0]["chapter_count"] == 0
    assert listing["items"][0]["lesson_count"] == 0
    assert listing["items"][0]["student_count"] == 1
    assert listing["summary"]["published"] == 1

    student_course = client.get(f"{API}/courses/{body['id']}", headers=auth_header(student_token)).json()
    assert student_course["is_enrolled"] is True
    assert student_course["enrollment_origin"] == "class"
    denied = client.delete(f"{API}/courses/{body['id']}/enroll", headers=auth_header(student_token))
    assert denied.status_code == 409


def test_manual_drop_is_not_reactivated_by_class_sync(client, db_session_factory):
    _admin, _teacher, student, admin_token, teacher_token, student_token = _setup(client, db_session_factory)
    term = client.post(f"{API}/academic-terms", headers=auth_header(admin_token), json={
        "code": "2027-SPRING", "name": "2027 春季学期", "start_date": "2027-02-20", "end_date": "2027-07-10", "status": "active",
    }).json()
    class_id = client.post(f"{API}/teaching-classes", headers=auth_header(admin_token), json={
        "academic_term_id": term["id"], "code": "AI-01", "name": "人工智能一班",
    }).json()["id"]
    client.post(f"{API}/teaching-classes/{class_id}/students", headers=auth_header(admin_token), json={"student_ids": [student.id]})
    course_id = client.post(f"{API}/courses", headers=auth_header(teacher_token), json={
        "title": "机器学习", "status": "published", "visibility": "private",
        "academic_term_id": term["id"], "teaching_class_ids": [class_id],
    }).json()["id"]
    removed = client.delete(f"{API}/courses/{course_id}/students/{student.id}", headers=auth_header(teacher_token))
    assert removed.status_code == 204
    client.post(f"{API}/teaching-classes/{class_id}/students", headers=auth_header(admin_token), json={"student_ids": [student.id]})
    with db_session_factory() as db:
        enrollment = db.query(CourseEnrollment).filter_by(course_id=course_id, student_id=student.id).one()
        assert enrollment.status == "dropped"
        assert enrollment.origin == "manual"
    restore = client.post(f"{API}/courses/{course_id}/enroll", headers=auth_header(student_token))
    assert restore.status_code == 403


def test_student_number_required_and_unique(client, db_session_factory):
    admin = create_user(db_session_factory, "user_admin", "admin")
    token, _ = login(client, admin.username)
    missing = client.post(f"{API}/users", headers=auth_header(token), json={
        "username": "stu-a", "password": "Passw0rd!", "real_name": "A", "role": "student",
    })
    assert missing.status_code == 422
    first = client.post(f"{API}/users", headers=auth_header(token), json={
        "username": "stu-a", "student_no": "S001", "password": "Passw0rd!", "real_name": "A", "role": "student",
    })
    assert first.status_code == 201
    duplicate = client.post(f"{API}/users", headers=auth_header(token), json={
        "username": "stu-b", "student_no": "S001", "password": "Passw0rd!", "real_name": "B", "role": "student",
    })
    assert duplicate.status_code == 409


def test_multi_class_course_deduplicates_students_and_rejects_term_mismatch(client, db_session_factory):
    _admin, _teacher, student, admin_token, teacher_token, _student_token = _setup(client, db_session_factory)
    term_ids = []
    for code in ("2028-FALL", "2029-SPRING"):
        response = client.post(f"{API}/academic-terms", headers=auth_header(admin_token), json={
            "code": code, "name": code, "start_date": "2028-09-01", "end_date": "2029-07-10", "status": "active",
        })
        assert response.status_code == 201
        term_ids.append(response.json()["id"])
    class_ids = []
    for index, term_id in enumerate((term_ids[0], term_ids[0], term_ids[1]), start=1):
        response = client.post(f"{API}/teaching-classes", headers=auth_header(admin_token), json={
            "academic_term_id": term_id, "code": f"CLASS-{index}", "name": f"Class {index}",
        })
        assert response.status_code == 201
        class_ids.append(response.json()["id"])
        client.post(f"{API}/teaching-classes/{class_ids[-1]}/students", headers=auth_header(admin_token), json={"student_ids": [student.id]})

    mismatch = client.post(f"{API}/courses", headers=auth_header(teacher_token), json={
        "title": "Mismatch", "academic_term_id": term_ids[0], "teaching_class_ids": [class_ids[2]],
    })
    assert mismatch.status_code == 422

    course = client.post(f"{API}/courses", headers=auth_header(teacher_token), json={
        "title": "Combined", "academic_term_id": term_ids[0], "teaching_class_ids": class_ids[:2],
    })
    assert course.status_code == 201, course.text
    assert course.json()["student_count"] == 1


def test_closed_term_is_read_only_and_rosters_are_permissioned(client, db_session_factory):
    _admin, _teacher, student, admin_token, teacher_token, student_token = _setup(client, db_session_factory)
    other_teacher = create_user(db_session_factory, "other_academic_teacher", "teacher")
    other_teacher_token, _ = login(client, other_teacher.username)
    term = client.post(f"{API}/academic-terms", headers=auth_header(admin_token), json={
        "code": "2030-FALL", "name": "2030 Fall", "start_date": "2030-09-01", "end_date": "2031-01-20", "status": "active",
    }).json()
    course = client.post(f"{API}/courses", headers=auth_header(teacher_token), json={
        "title": "Read only course", "academic_term_id": term["id"],
    }).json()

    student_roster = client.get(f"{API}/courses/{course['id']}/students", headers=auth_header(student_token))
    assert student_roster.status_code == 403
    other_teacher_roster = client.get(f"{API}/courses/{course['id']}/students", headers=auth_header(other_teacher_token))
    assert other_teacher_roster.status_code == 403

    closed = client.delete(f"{API}/academic-terms/{term['id']}", headers=auth_header(admin_token))
    assert closed.status_code == 200
    assert client.patch(f"{API}/academic-terms/{term['id']}", headers=auth_header(admin_token), json={"status": "active"}).status_code == 409
    assert client.patch(f"{API}/courses/{course['id']}", headers=auth_header(teacher_token), json={"title": "Changed"}).status_code == 409
    assert client.post(f"{API}/courses/{course['id']}/students", headers=auth_header(teacher_token), json={"student_id": student.id}).status_code == 409
