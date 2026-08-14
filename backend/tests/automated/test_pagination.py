"""统一分页契约测试（TASK-021 / F-24）。

所有公开列表共享同一校验：page >= 1、1 <= page_size <= 100；非法值 422。
前端现有 100 条请求保持兼容。
"""
import pytest
from conftest import auth_header, create_user, login
from sqlalchemy import select

from app.models import Course, User

API = "/api/v1"

# 各主要列表端点：(method, path, 最小权限角色)
LIST_ENDPOINTS = [
    ("get", "/api/v1/courses", "teacher"),
    ("get", "/api/v1/assignments", "teacher"),
    ("get", "/api/v1/exams", "teacher"),
    ("get", "/api/v1/users", "admin"),
    ("get", "/api/v1/users/students", "teacher"),
    ("get", "/api/v1/academic-terms", "teacher"),
    ("get", "/api/v1/teaching-classes", "teacher"),
    # 注：/experiments/modules 是不带分页参数的全量列表，不在分页契约范围内
    ("get", "/api/v1/judge/submissions", "student"),
]


@pytest.fixture()
def tokens(client, db_session_factory):
    teacher = create_user(db_session_factory, "pg-teacher", "teacher")
    create_user(db_session_factory, "pg-student", "student")
    create_user(db_session_factory, "pg-admin", "admin")
    return {
        "teacher": login(client, "pg-teacher")[0],
        "student": login(client, "pg-student")[0],
        "admin": login(client, "pg-admin")[0],
    }


@pytest.mark.parametrize("params", [
    {"page": 0},
    {"page": -1},
    {"page_size": 0},
    {"page_size": -5},
    {"page_size": 101},
])
@pytest.mark.parametrize("endpoint", LIST_ENDPOINTS)
def test_invalid_pagination_rejected(client, tokens, endpoint, params):
    method, path, role = endpoint
    resp = getattr(client, method)(
        path, headers=auth_header(tokens[role]), params=params,
    )
    assert resp.status_code == 422, f"{path} {params} -> {resp.status_code} {resp.text[:120]}"


@pytest.mark.parametrize("params", [
    {"page": 1, "page_size": 1},
    {"page": 1, "page_size": 100},
    {"page": 3, "page_size": 20},
])
@pytest.mark.parametrize("endpoint", LIST_ENDPOINTS)
def test_valid_pagination_boundaries_accepted(client, tokens, endpoint, params):
    method, path, role = endpoint
    resp = getattr(client, method)(
        path, headers=auth_header(tokens[role]), params=params,
    )
    assert resp.status_code == 200, f"{path} {params} -> {resp.status_code} {resp.text[:120]}"
    body = resp.json()
    assert body["page"] == params["page"]
    assert body["page_size"] == params["page_size"]


def test_courses_list_still_returns_all_with_page_size_100(client, db_session_factory):
    """前端 100 条请求保持兼容：一次取回 100 条。"""
    teacher = create_user(db_session_factory, "pg-teacher2", "teacher")
    token, _ = login(client, "pg-teacher2")
    with db_session_factory() as db:
        for i in range(105):
            db.add(Course(
                title=f"课程{i}", description="d", status="draft",
                visibility="class", default_score=100, teacher_id=teacher.id,
            ))
        db.commit()
    resp = client.get(
        f"{API}/courses", headers=auth_header(token),
        params={"page": 1, "page_size": 100},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 105
    assert len(body["items"]) == 100
