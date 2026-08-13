"""密码边界与改密语义测试（TASK-011 / F-15）。

- 统一密码规则：≥8 字符、UTF-8 ≤72 字节、非全空白、不等同规范化用户名
- 本人改密必须提交 current_password；管理员重置无需旧密码
- 越权改密 403；所有入口（创建/本人改密/管理员重置）共享同一校验
"""
import pytest
from conftest import auth_header, create_user, login
from pydantic import ValidationError

from app.schemas import UserCreate
from app.security import validate_password_rules

API = "/api/v1"


# ── 规则单元校验 ───────────────────────────────────────────────


@pytest.mark.parametrize("password", ["short", "abc", "", "        ", "  a b  "])
def test_reject_short_or_blank(password):
    with pytest.raises(ValueError):
        validate_password_rules(password)


def test_accept_minimum_length():
    validate_password_rules("12345678")


def test_reject_over_72_utf8_bytes():
    # 25 个汉字 = 75 字节 > 72
    with pytest.raises(ValueError):
        validate_password_rules("汉" * 25)


def test_accept_24_chinese_chars_exactly_72_bytes():
    validate_password_rules("汉" * 24)


def test_reject_username_equality_casefolded():
    with pytest.raises(ValueError):
        validate_password_rules("alice2024", "Alice2024")
    with pytest.raises(ValueError):
        validate_password_rules("  Alice2024  ", "Alice2024")


def test_schema_user_create_enforces_rules():
    UserCreate(username="u", password="12345678", real_name="U", role="student")
    with pytest.raises(ValidationError):
        UserCreate(username="u", password="short", real_name="U", role="student")


# ── API：创建入口 ──────────────────────────────────────────────


def test_admin_create_user_rejects_weak_password(client, db_session_factory):
    create_user(db_session_factory, "pw-admin", "admin")
    admin_token, _ = login(client, "pw-admin")
    response = client.post(
        f"{API}/users", headers=auth_header(admin_token),
        json={"username": "pw-target", "password": "short", "real_name": "T", "role": "student"},
    )
    assert response.status_code in (400, 422), response.text


# ── API：本人改密 ──────────────────────────────────────────────


def test_self_change_without_current_password_422(client, db_session_factory):
    create_user(db_session_factory, "pw-self2", "student", password="OldPass1!")
    token, _ = login(client, "pw-self2", "OldPass1!")
    me = client.get(f"{API}/auth/me", headers=auth_header(token)).json()
    response = client.patch(
        f"{API}/users/{me['id']}/password", headers=auth_header(token),
        json={"password": "NewPass1!"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "CURRENT_PASSWORD_REQUIRED"


def test_self_change_with_wrong_current_password(client, db_session_factory):
    create_user(db_session_factory, "pw-self3", "student", password="OldPass1!")
    token, _ = login(client, "pw-self3", "OldPass1!")
    me = client.get(f"{API}/auth/me", headers=auth_header(token)).json()
    response = client.patch(
        f"{API}/users/{me['id']}/password", headers=auth_header(token),
        json={"password": "NewPass1!", "current_password": "WrongPass1!"},
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "CURRENT_PASSWORD_INCORRECT"


def test_self_change_success(client, db_session_factory):
    create_user(db_session_factory, "pw-self4", "student", password="OldPass1!")
    token, _ = login(client, "pw-self4", "OldPass1!")
    me = client.get(f"{API}/auth/me", headers=auth_header(token)).json()
    response = client.patch(
        f"{API}/users/{me['id']}/password", headers=auth_header(token),
        json={"password": "NewPass1!", "current_password": "OldPass1!"},
    )
    assert response.status_code == 200, response.text
    # 新密码可登录
    ok, _ = login(client, "pw-self4", "NewPass1!")
    assert ok


def test_self_change_rejects_username_equality(client, db_session_factory):
    create_user(db_session_factory, "pw-self5", "student", password="OldPass1!")
    token, _ = login(client, "pw-self5", "OldPass1!")
    me = client.get(f"{API}/auth/me", headers=auth_header(token)).json()
    response = client.patch(
        f"{API}/users/{me['id']}/password", headers=auth_header(token),
        json={"password": "pw-self5", "current_password": "OldPass1!"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "INVALID_PASSWORD"


# ── API：管理员重置 ────────────────────────────────────────────


def test_admin_reset_without_current_password(client, db_session_factory):
    create_user(db_session_factory, "pw-admin2", "admin")
    target = create_user(db_session_factory, "pw-target2", "student", password="OldPass1!")
    token, _ = login(client, "pw-admin2")
    response = client.patch(
        f"{API}/users/{target.id}/password", headers=auth_header(token),
        json={"password": "NewPass1!"},
    )
    assert response.status_code == 200, response.text
    ok, _ = login(client, "pw-target2", "NewPass1!")
    assert ok


def test_admin_reset_rejects_weak_password(client, db_session_factory):
    create_user(db_session_factory, "pw-admin3", "admin")
    target = create_user(db_session_factory, "pw-target3", "student", password="OldPass1!")
    token, _ = login(client, "pw-admin3")
    response = client.patch(
        f"{API}/users/{target.id}/password", headers=auth_header(token),
        json={"password": "short"},
    )
    assert response.status_code in (400, 422), response.text


def test_non_admin_cannot_change_others_password(client, db_session_factory):
    create_user(db_session_factory, "pw-a", "student", password="OldPass1!")
    other = create_user(db_session_factory, "pw-b", "student", password="OldPass1!")
    token, _ = login(client, "pw-a", "OldPass1!")
    response = client.patch(
        f"{API}/users/{other.id}/password", headers=auth_header(token),
        json={"password": "NewPass1!", "current_password": "OldPass1!"},
    )
    assert response.status_code == 403, response.text
