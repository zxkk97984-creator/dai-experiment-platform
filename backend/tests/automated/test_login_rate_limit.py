"""登录限流测试：账户/IP 双维度、时间窗口、成功复位、未知用户、Redis 故障与转发头信任。

- 账户维度：规范化用户名 15 分钟窗口内最多 10 次失败。
- IP 维度：单 IP 15 分钟窗口内最多 30 次尝试（换用户名不可绕过）。
- 超限返回 429 + Retry-After；成功登录清除该账户失败计数。
- Redis 故障返回 503，不造成永久锁定。
- 仅当 trusted_proxy=True 时才信任 X-Forwarded-For 最右一跳。
"""

import time

import pytest
import redis as redis_lib

from conftest import create_user

WRONG = "wrong-password-1"
RIGHT = "Passw0rd!"


def login_attempt(client, username, password=RIGHT, headers=None):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers=headers or {},
    )


def test_user_dimension_blocks_after_10_failures(client, db_session_factory):
    create_user(db_session_factory, "alice", "student")
    for _ in range(10):
        assert login_attempt(client, "alice", WRONG).status_code == 401
    # 第 11 次即使密码正确也被限流
    blocked = login_attempt(client, "alice", RIGHT)
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "RATE_LIMITED"
    retry_after = blocked.headers.get("Retry-After")
    assert retry_after is not None and int(retry_after) >= 0


def test_ip_dimension_cannot_be_bypassed_by_switching_usernames(client):
    # 30 个不同用户名各失败一次 → IP 维度封禁
    for i in range(30):
        assert login_attempt(client, f"ghost{i}", WRONG).status_code == 401
    blocked = login_attempt(client, "ghost30", WRONG)
    assert blocked.status_code == 429


def test_success_clears_user_failure_count(client, db_session_factory):
    create_user(db_session_factory, "bob", "student")
    for _ in range(5):
        assert login_attempt(client, "bob", WRONG).status_code == 401
    # 成功登录清零账户失败计数
    assert login_attempt(client, "bob", RIGHT).status_code == 200
    # 重新计数：前 10 次失败均返回 401，第 11 次才被限流
    for _ in range(10):
        assert login_attempt(client, "bob", WRONG).status_code == 401
    assert login_attempt(client, "bob", WRONG).status_code == 429


def test_window_expiry_unblocks_account(client, redis_client, db_session_factory):
    create_user(db_session_factory, "carol", "student")
    for _ in range(10):
        assert login_attempt(client, "carol", WRONG).status_code == 401
    assert login_attempt(client, "carol", RIGHT).status_code == 429
    # 模拟窗口过期（将窗口缩短到 1 秒）
    for key in redis_client.scan_iter("rl:user:*"):
        redis_client.expire(key, 1)
    time.sleep(1.2)
    assert login_attempt(client, "carol", RIGHT).status_code == 200


def test_unknown_user_failures_count_toward_limits(client):
    for _ in range(10):
        assert login_attempt(client, "nobody", WRONG).status_code == 401
    assert login_attempt(client, "nobody", WRONG).status_code == 429


def test_redis_failure_returns_503_without_permanent_lockout(
    client, redis_client, monkeypatch, db_session_factory
):
    create_user(db_session_factory, "dave", "student")

    def boom(*args, **kwargs):
        raise redis_lib.ConnectionError("redis down")

    monkeypatch.setattr(redis_client, "get", boom)
    monkeypatch.setattr(redis_client, "incr", boom)
    response = login_attempt(client, "dave", RIGHT)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "SERVICE_UNAVAILABLE"
    # Redis 恢复后同一账户可正常登录（未被永久锁定）
    monkeypatch.undo()
    assert login_attempt(client, "dave", RIGHT).status_code == 200


def test_forged_xff_ignored_without_trusted_proxy(client, test_settings):
    assert test_settings.trusted_proxy is False
    for i in range(30):
        assert login_attempt(client, f"ghost{i}", WRONG).status_code == 401
    # 伪造不同来源 IP 不能绕过真实客户端 IP 的封禁
    blocked = login_attempt(
        client, "ghost30", WRONG, headers={"X-Forwarded-For": "1.2.3.4"}
    )
    assert blocked.status_code == 429


def test_xff_honored_only_with_trusted_proxy(client, test_settings, monkeypatch):
    monkeypatch.setattr(test_settings, "trusted_proxy", True)
    for i in range(30):
        response = login_attempt(
            client, f"ghost{i}", WRONG, headers={"X-Forwarded-For": "203.0.113.9"}
        )
        assert response.status_code == 401
    # 该转发 IP 已被封禁
    blocked = login_attempt(
        client, "ghost30", WRONG, headers={"X-Forwarded-For": "203.0.113.9"}
    )
    assert blocked.status_code == 429
    # 不带转发头的真实客户端 IP 不受该转发 IP 封禁影响
    assert login_attempt(client, "ghost31", WRONG).status_code == 401


def test_username_normalization_for_rate_limit_key(client, db_session_factory):
    create_user(db_session_factory, "eve", "student")
    for _ in range(10):
        assert login_attempt(client, "  EVE ", WRONG).status_code == 401
    # 规范化后同一账户被识别并限流
    assert login_attempt(client, "eve", RIGHT).status_code == 429
