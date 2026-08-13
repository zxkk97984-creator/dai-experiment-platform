"""TASK-012（F-16）：改密/管理员重置/禁用后立即撤销该用户全部会话。

- Access/Refresh token 写入 sv；认证与刷新时与 users.session_version 比对
- 旧 token（无 sv 或 sv 落后）统一 401 SESSION_REVOKED，重新登录获得新会话
- session_version 原子递增（改密/重置/禁用），不重构 Redis 会话体系
"""
from datetime import UTC, datetime, timedelta

import pytest
from conftest import auth_header, create_user, login
from jose import jwt
from sqlalchemy import select

from app.models import User

API = "/api/v1"


def _old_token_no_sv(settings, user_id: int, token_type: str = "access") -> str:
    """模拟升级前签发的 token：无 sv 声明（用测试同款密钥/算法构造）。"""
    expires_at = datetime.now(UTC) + timedelta(minutes=30)
    payload = {
        "sub": str(user_id),
        "role": "student",
        "type": token_type,
        "jti": f"legacy-{token_type}-{user_id}",
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _me(client, token):
    return client.get(f"{API}/auth/me", headers=auth_header(token))


def _refresh(client, refresh_token):
    """显式以指定 refresh token 刷新（清空客户端 cookie，避免用错上次登录的会话）。"""
    client.cookies.clear()
    return client.post(f"{API}/auth/refresh", cookies={"dai_refresh_token": refresh_token})


def _login_and_refresh(client, username, password="Passw0rd!"):
    """登录并额外刷一次得到第二代 token 对（用于验证刷新链同样被撤销）。"""
    token, refresh = login(client, username, password)
    refreshed = _refresh(client, refresh)
    assert refreshed.status_code == 200, refreshed.text
    new_refresh = ""
    for cookie_str in refreshed.headers.get_list("set-cookie"):
        if "dai_refresh_token=" in cookie_str:
            new_refresh = cookie_str.split("dai_refresh_token=")[1].split(";")[0]
    return refreshed.json()["access_token"], new_refresh


def test_session_version_defaults_to_one(db_session_factory):
    with db_session_factory() as db:
        user = User(username="sv-default", real_name="x", role="student",
                    status="active", password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.session_version == 1


def test_old_token_without_sv_is_rejected(client, db_session_factory, test_settings):
    """升级前签发的旧 token（无 sv）统一 401，要求重新登录。"""
    user = create_user(db_session_factory, "sv-legacy", "student")
    token, _ = login(client, "sv-legacy")
    assert _me(client, token).status_code == 200

    legacy = _old_token_no_sv(test_settings, user.id)
    resp = _me(client, legacy)
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "SESSION_REVOKED"


def test_password_change_revokes_all_sessions(client, db_session_factory):
    create_user(db_session_factory, "sv-pw", "student", password="OldPass123!")
    access1, refresh1 = _login_and_refresh(client, "sv-pw", "OldPass123!")
    assert _me(client, access1).status_code == 200

    # 本人改密：改密动作本身用改密前的 token 提交成功，sv 在事务内递增
    resp = client.patch(
        f"{API}/users/1/password",
        json={"password": "NewPass123!", "current_password": "OldPass123!"},
        headers=auth_header(access1),
    )
    assert resp.status_code == 200, resp.text

    # 改密完成：旧 Access 与旧 Refresh（含刷新链二代）全部立即 401
    assert _me(client, access1).status_code == 401
    assert _refresh(client, refresh1).status_code == 401

    # 新密码登录成功
    access2, _ = login(client, "sv-pw", "NewPass123!")
    assert _me(client, access2).status_code == 200


def test_admin_password_reset_revokes_sessions(client, db_session_factory):
    create_user(db_session_factory, "sv-reset-target", "student", password="OldPass123!")
    create_user(db_session_factory, "sv-admin", "admin")
    access1, refresh1 = _login_and_refresh(client, "sv-reset-target", "OldPass123!")
    assert _me(client, access1).status_code == 200

    admin_token, _ = login(client, "sv-admin")
    resp = client.patch(
        f"{API}/users/1/password",
        json={"password": "AdminReset123!"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200, resp.text

    assert _me(client, access1).status_code == 401
    assert _refresh(client, refresh1).status_code == 401

    access2, _ = login(client, "sv-reset-target", "AdminReset123!")
    assert _me(client, access2).status_code == 200


def test_disable_revokes_sessions_and_reenable_does_not_restore(client, db_session_factory):
    create_user(db_session_factory, "sv-disable-target", "student")
    create_user(db_session_factory, "sv-admin2", "admin")
    access1, refresh1 = _login_and_refresh(client, "sv-disable-target")
    assert _me(client, access1).status_code == 200

    admin_token, _ = login(client, "sv-admin2")
    resp = client.patch(
        f"{API}/users/1/status",
        json={"status": "disabled"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200, resp.text

    # 禁用：旧 token 全部失效（USER_NOT_ACTIVE 或 SESSION_REVOKED 均为 401）
    assert _me(client, access1).status_code == 401
    assert _refresh(client, refresh1).status_code == 401
    # 禁用用户无法登录
    denied = client.post(f"{API}/auth/login", json={"username": "sv-disable-target", "password": "Passw0rd!"})
    assert denied.status_code == 401

    # 重新启用：旧 token 仍失效（sv 不回退），新登录可用
    client.patch(f"{API}/users/1/status", json={"status": "active"}, headers=auth_header(admin_token))
    assert _me(client, access1).status_code == 401
    assert _refresh(client, refresh1).status_code == 401
    access2, _ = login(client, "sv-disable-target")
    assert _me(client, access2).status_code == 200


def test_self_password_change_works_after_bump(client, db_session_factory):
    """改密成功后本人会话递增——新 token 正常，旧 token 失效。"""
    create_user(db_session_factory, "sv-self", "student", password="OldPass123!")
    access1, _ = login(client, "sv-self", "OldPass123!")
    assert _me(client, access1).status_code == 200

    resp = client.patch(
        f"{API}/users/1/password",
        json={"password": "Fresh12345!", "current_password": "OldPass123!"},
        headers=auth_header(access1),
    )
    assert resp.status_code == 200, resp.text
    assert _me(client, access1).status_code == 401  # 改密后旧 access 失效
    access2, _ = login(client, "sv-self", "Fresh12345!")
    assert _me(client, access2).status_code == 200


def test_sv_bump_is_atomic_increment(client, db_session_factory):
    """session_version 使用 SQL 原子自增：多次变更单调递增且无回退。"""
    create_user(db_session_factory, "sv-atomic", "student", password="OldPass123!")
    create_user(db_session_factory, "sv-admin3", "admin")
    admin_token, _ = login(client, "sv-admin3")
    with db_session_factory() as db:
        before = db.scalar(select(User.session_version).where(User.username == "sv-atomic"))
        assert before == 1

    client.patch(f"{API}/users/1/password", json={"password": "BumpOnce123!"}, headers=auth_header(admin_token))
    client.patch(f"{API}/users/1/status", json={"status": "disabled"}, headers=auth_header(admin_token))
    client.patch(f"{API}/users/1/status", json={"status": "active"}, headers=auth_header(admin_token))

    with db_session_factory() as db:
        after = db.scalar(select(User.session_version).where(User.username == "sv-atomic"))
        assert after == 3  # 重置 +1、禁用 +1；重新启用不递增
