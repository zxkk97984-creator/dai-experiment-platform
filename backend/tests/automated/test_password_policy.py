"""TASK-011：密码边界与改密语义。

- 所有密码入口共享同一形状校验：≥8 字符、UTF-8 ≤72 字节、不得全空白。
- 密码不得等同规范化用户名。
- 本人改密必须提交正确的 current_password；管理员重置无需旧密码。
"""

from conftest import auth_header, create_user, login

API = "/api/v1"

RIGHT = "Passw0rd!"


def _create_student(client, db_session_factory, username, password=RIGHT):
    create_user(db_session_factory, username, "student", password=password)
    token, _ = login(client, username, password=password)
    return token


def _create_admin(client, db_session_factory):
    create_user(db_session_factory, "pw_admin", "admin")
    token, _ = login(client, "pw_admin")
    return token


def test_create_user_rejects_short_password(client, db_session_factory):
    admin_tok = _create_admin(client, db_session_factory)
    resp = client.post(
        f"{API}/users",
        headers=auth_header(admin_tok),
        json={
            "username": "short_pw", "password": "Abc123!",
            "real_name": "短密码", "role": "student", "student_no": "S9001",
        },
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_create_user_rejects_overlong_multibyte_password(client, db_session_factory):
    admin_tok = _create_admin(client, db_session_factory)
    # 25 个 CJK 字符 = 75 字节 > 72
    resp = client.post(
        f"{API}/users",
        headers=auth_header(admin_tok),
        json={
            "username": "bytes_pw", "password": "密" * 25,
            "real_name": "字节超限", "role": "student", "student_no": "S9002",
        },
    )
    assert resp.status_code == 422, resp.text


def test_create_user_rejects_whitespace_only_password(client, db_session_factory):
    admin_tok = _create_admin(client, db_session_factory)
    resp = client.post(
        f"{API}/users",
        headers=auth_header(admin_tok),
        json={
            "username": "blank_pw", "password": "        ",
            "real_name": "空白密码", "role": "student", "student_no": "S9003",
        },
    )
    assert resp.status_code == 422, resp.text


def test_password_equal_username_rejected_on_create_and_change(client, db_session_factory):
    admin_tok = _create_admin(client, db_session_factory)
    resp = client.post(
        f"{API}/users",
        headers=auth_header(admin_tok),
        json={
            "username": "samepw_1", "password": "samepw_1",
            "real_name": "同名密码", "role": "student", "student_no": "S9004",
        },
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["code"] == "PASSWORD_EQUALS_USERNAME"


def test_self_change_requires_correct_current_password(client, db_session_factory):
    token = _create_student(client, db_session_factory, "self_pw")
    me = client.get(f"{API}/auth/me", headers=auth_header(token)).json()
    # 缺 current_password → 401
    resp = client.patch(
        f"{API}/users/{me['id']}/password",
        headers=auth_header(token),
        json={"password": "NewPass123!"},
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["code"] == "CURRENT_PASSWORD_INVALID"
    # 错误旧密码 → 401
    resp = client.patch(
        f"{API}/users/{me['id']}/password",
        headers=auth_header(token),
        json={"password": "NewPass123!", "current_password": "WrongOld"},
    )
    assert resp.status_code == 401, resp.text
    # 正确旧密码 → 200，新密码可登录
    resp = client.patch(
        f"{API}/users/{me['id']}/password",
        headers=auth_header(token),
        json={"password": "NewPass123!", "current_password": RIGHT},
    )
    assert resp.status_code == 200, resp.text
    assert login(client, "self_pw", password="NewPass123!")


def test_admin_reset_without_old_password(client, db_session_factory):
    _create_student(client, db_session_factory, "rst_stu")
    admin_tok = _create_admin(client, db_session_factory)
    target = client.get(f"{API}/users", headers=auth_header(admin_tok), params={"role": "student"}).json()["items"]
    uid = next(u["id"] for u in target if u["username"] == "rst_stu")
    resp = client.patch(
        f"{API}/users/{uid}/password",
        headers=auth_header(admin_tok),
        json={"password": "ResetPass1!"},
    )
    assert resp.status_code == 200, resp.text
    assert login(client, "rst_stu", password="ResetPass1!")


def test_self_change_rejects_password_equal_username(client, db_session_factory):
    token = _create_student(client, db_session_factory, "pw_eq_us")
    me = client.get(f"{API}/auth/me", headers=auth_header(token)).json()
    resp = client.patch(
        f"{API}/users/{me['id']}/password",
        headers=auth_header(token),
        json={"password": "pw_eq_us", "current_password": RIGHT},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["code"] == "PASSWORD_EQUALS_USERNAME"


def test_self_change_rejects_invalid_shape(client, db_session_factory):
    token = _create_student(client, db_session_factory, "shape_pw")
    me = client.get(f"{API}/auth/me", headers=auth_header(token)).json()
    resp = client.patch(
        f"{API}/users/{me['id']}/password",
        headers=auth_header(token),
        json={"password": "short", "current_password": RIGHT},
    )
    assert resp.status_code == 422, resp.text
