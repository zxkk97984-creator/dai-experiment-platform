from conftest import auth_header, create_user, login
from app.worker.judge_worker import process_submission


def test_course_assignment_submission_and_worker_result(
    client,
    db_session_factory,
    redis_client,
    test_settings,
):
    create_user(db_session_factory, "teacher", "teacher")
    create_user(db_session_factory, "student", "student")
    teacher_token, _ = login(client, "teacher")
    student_token, _ = login(client, "student")

    course_response = client.post(
        "/api/v1/courses",
        headers=auth_header(teacher_token),
        json={
            "title": "机器学习基础",
            "description": "AI course",
            "status": "published",
        },
    )
    assert course_response.status_code == 201, course_response.text
    course_id = course_response.json()["id"]

    chapter_response = client.post(
        f"/api/v1/courses/{course_id}/chapters",
        headers=auth_header(teacher_token),
        json={"title": "第一章", "order_index": 1},
    )
    assert chapter_response.status_code == 201
    chapter_id = chapter_response.json()["id"]

    lesson_response = client.post(
        f"/api/v1/chapters/{chapter_id}/lessons",
        headers=auth_header(teacher_token),
        json={
            "title": "线性回归",
            "content_type": "markdown",
            "content": "# Linear Regression",
            "order_index": 1,
        },
    )
    assert lesson_response.status_code == 201

    enroll_response = client.post(
        f"/api/v1/courses/{course_id}/enroll",
        headers=auth_header(student_token),
    )
    assert enroll_response.status_code == 201

    chapters_response = client.get(
        f"/api/v1/courses/{course_id}/chapters",
        headers=auth_header(student_token),
    )
    assert chapters_response.status_code == 200
    assert chapters_response.json()["items"][0]["lessons"][0]["title"] == "线性回归"

    assignment_response = client.post(
        "/api/v1/assignments",
        headers=auth_header(teacher_token),
        json={
            "course_id": course_id,
            "title": "函数作业",
            "description": "实现 add",
            "status": "published",
        },
    )
    assert assignment_response.status_code == 201
    assignment_id = assignment_response.json()["id"]

    question_response = client.post(
        f"/api/v1/assignments/{assignment_id}/questions",
        headers=auth_header(teacher_token),
        json={
            "title": "两数相加",
            "description": "实现 add",
            "function_name": "add",
            "signature": "def add(a: int, b: int) -> int",
            "starter_code": "def add(a, b):\n    return 0\n",
            "public_cases": [{"input": [1, 2], "expected": 3}],
            "hidden_tests": "def test_add():\n    assert user_code.add(1, 2) == 3\n    assert user_code.add(-1, 1) == 0\n",
            "time_limit_ms": 5000,
            "memory_limit_mb": 256,
        },
    )
    assert question_response.status_code == 201
    question_id = question_response.json()["id"]

    submit_response = client.post(
        "/api/v1/judge/submissions",
        headers=auth_header(student_token),
        json={
            "question_id": question_id,
            "code": "def add(a, b):\n    return a + b\n",
        },
    )
    assert submit_response.status_code == 201, submit_response.text
    submission_id = submit_response.json()["id"]
    assert submit_response.json()["status"] == "queued"
    assert redis_client.llen("judge:queue") == 1

    with db_session_factory() as db:
        process_submission(db, redis_client, test_settings, submission_id)

    result_response = client.get(
        f"/api/v1/judge/submissions/{submission_id}/result",
        headers=auth_header(student_token),
    )
    assert result_response.status_code == 200
    assert result_response.json()["status"] == "accepted"
    assert result_response.json()["score"] == 100


def test_worker_marks_wrong_answer(client, db_session_factory, redis_client, test_settings):
    create_user(db_session_factory, "teacher", "teacher")
    create_user(db_session_factory, "student", "student")
    teacher_token, _ = login(client, "teacher")
    student_token, _ = login(client, "student")

    course_id = client.post(
        "/api/v1/courses",
        headers=auth_header(teacher_token),
        json={"title": "Python", "status": "published"},
    ).json()["id"]
    client.post(f"/api/v1/courses/{course_id}/enroll", headers=auth_header(student_token))
    assignment_id = client.post(
        "/api/v1/assignments",
        headers=auth_header(teacher_token),
        json={"course_id": course_id, "title": "A1", "status": "published"},
    ).json()["id"]
    question_id = client.post(
        f"/api/v1/assignments/{assignment_id}/questions",
        headers=auth_header(teacher_token),
        json={
            "title": "Add",
            "function_name": "add",
            "signature": "def add(a, b)",
            "starter_code": "def add(a, b):\n    return 0\n",
            "public_cases": [],
            "hidden_tests": "def test_add():\n    assert user_code.add(1, 2) == 3\n",
        },
    ).json()["id"]
    submission_id = client.post(
        "/api/v1/judge/submissions",
        headers=auth_header(student_token),
        json={"question_id": question_id, "code": "def add(a, b):\n    return 0\n"},
    ).json()["id"]

    with db_session_factory() as db:
        process_submission(db, redis_client, test_settings, submission_id)

    response = client.get(
        f"/api/v1/judge/submissions/{submission_id}/result",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "wrong_answer"
    assert response.json()["score"] == 0
