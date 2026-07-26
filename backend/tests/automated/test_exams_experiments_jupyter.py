"""考试 + Jupyter 旧集成测试（适配 v5 模型）"""
from conftest import auth_header, create_user, login


def test_exam_submission_and_grade_visibility(client, db_session_factory):
    create_user(db_session_factory, "teacher", "teacher")
    create_user(db_session_factory, "student", "student")
    teacher_token, _ = login(client, "teacher")
    student_token, _ = login(client, "student")

    course_id = client.post(
        "/api/v1/courses",
        headers=auth_header(teacher_token),
        json={"title": "深度学习", "status": "published"},
    ).json()["id"]
    client.post(f"/api/v1/courses/{course_id}/enroll", headers=auth_header(student_token))

    exam_response = client.post(
        "/api/v1/exams",
        headers=auth_header(teacher_token),
        json={
            "course_id": course_id,
            "title": "期末考试",
            "status": "published",
            "duration_minutes": 90,
        },
    )
    assert exam_response.status_code == 201
    exam_id = exam_response.json()["id"]

    start_response = client.post(
        f"/api/v1/exams/{exam_id}/start",
        headers=auth_header(student_token),
    )
    assert start_response.status_code == 201

    # v5: ExamSubmission 不再有 answers 字段，ExamAnswer 是唯一事实源
    submit_response = client.post(
        f"/api/v1/exams/{exam_id}/submit",
        headers=auth_header(student_token),
        json={"score": 88},
    )
    assert submit_response.status_code in (200, 201)

    grades_response = client.get(
        f"/api/v1/exams/{exam_id}/grades",
        headers=auth_header(teacher_token),
    )
    assert grades_response.status_code == 200


def test_jupyter_entry_and_experiment_records(client, db_session_factory):
    create_user(db_session_factory, "developer", "developer")
    create_user(db_session_factory, "student", "student")
    developer_token, _ = login(client, "developer")
    student_token, _ = login(client, "student")

    entry_response = client.get("/api/v1/jupyter/entry", headers=auth_header(student_token))
    assert entry_response.status_code in (200, 503)

    templates_response = client.get(
        "/api/v1/jupyter/templates",
        headers=auth_header(student_token),
    )
    assert templates_response.status_code == 200
    assert templates_response.json()["items"][0]["name"].endswith(".ipynb")

    module_response = client.post(
        "/api/v1/experiments/modules",
        headers=auth_header(developer_token),
        json={
            "name": "Swin Transformer 可视化",
            "description": "可视化实验",
            "status": "published",
        },
    )
    assert module_response.status_code == 201
    module_id = module_response.json()["id"]

    # v5: records 仍可通过 GET 列出
    records_response = client.get(
        "/api/v1/experiments/records",
        headers=auth_header(student_token),
    )
    assert records_response.status_code == 200
