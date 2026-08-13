"""登录双维限流测试（TASK-005 / F-14）。

- 账户维度：15 分钟窗口内最多 N 次失败（含未知用户名）
- IP 维度：同窗口最多 M 次尝试，换用户名无法绕过
- 成功登录清除账户计数；超限返回 429 + Retry-After
- 伪造 X-Forwarded-For 在直连 peer 不可信时被忽略
- Redis 故障 → 登录 503 失败关闭，绝不绕过限流
"""
import pytest
import redis as redis_lib
from fastapi.testclient import TestClient

from conftest import create_user
from app.config import Settings
from app.dependencies import get_db, get_redis_client, get_settings
from app.main import create_app

API = "/api/v1"


@pytest.fixture()
def rate_ctx(test_settings, db_session_factory):
    import fakeredis

    redis_client = fakeredis.FakeRedis(decode_responses=True)
    settings = Settings(
        **{
            **test_settings.model_dump(),
            "login_max_failures_per_username": 3,
            "login_max_attempts_per_ip": 5,
            "login_rate_limit_window_seconds": 900,
        }
    )
    app = create_app(settings)

    def override_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis_client] = lambda: redis_client
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app), redis_client, settings, db_session_factory


def _fail(client, username, password="WrongPass1!", headers=None):
    return client.post(
        f"{API}/auth/login",
        json={"username": username, "password": password},
        headers=headers or {},
    )


def test_account_dimension_blocks_after_threshold(rate_ctx):
    client, redis_client, settings, db = rate_ctx
    create_user(db, "rl-user", "student", password="RightPass1!")
    for _ in range(settings.login_max_failures_per_username):
        response = _fail(client, "rl-user")
        assert response.status_code == 401, response.text

    # 即使密码正确，账户维度超限后仍被 429 拦截
    response = client.post(
        f"{API}/auth/login",
        json={"username": "rl-user", "password": "RightPass1!"},
    )
    assert response.status_code == 429, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "LOGIN_RATE_LIMITED"
    assert int(response.headers["Retry-After"]) > 0


def test_unknown_username_failures_counted(rate_ctx):
    client, redis_client, settings, db = rate_ctx
    for _ in range(settings.login_max_failures_per_username):
        assert _fail(client, "rl-ghost").status_code == 401
    response = _fail(client, "rl-ghost")
    assert response.status_code == 429, response.text
    # 统一文案：不泄露用户名是否存在
    assert response.json()["detail"]["message"] == "尝试次数过多，请稍后再试"


def test_ip_dimension_blocks_username_rotation(rate_ctx):
    client, redis_client, settings, db = rate_ctx
    # 每个用户名各失败一次（均低于账户阈值），但 IP 总尝试达到阈值
    for index in range(settings.login_max_attempts_per_ip):
        response = _fail(client, f"rl-rot-{index}")
        assert response.status_code == 401, response.text
    # 全新用户名也被 IP 维度拦截
    response = _fail(client, "rl-rot-brand-new")
    assert response.status_code == 429, response.text


def test_success_clears_account_counter(rate_ctx):
    client, redis_client, settings, db = rate_ctx
    create_user(db, "rl-reset", "student", password="RightPass1!")
    for _ in range(settings.login_max_failures_per_username - 1):
        assert _fail(client, "rl-reset").status_code == 401
    # 成功登录清除账户计数
    ok = client.post(
        f"{API}/auth/login",
        json={"username": "rl-reset", "password": "RightPass1!"},
    )
    assert ok.status_code == 200, ok.text
    assert not redis_client.exists("login:fail:user:rl-reset")
    # 再失败 N-1 次仍未触发账户限流（计数已复位）
    for _ in range(settings.login_max_failures_per_username - 1):
        assert _fail(client, "rl-reset").status_code == 401
    # 第 N 次失败（累计达到阈值）→ 后续拦截；成功登录本身不受影响
    assert _fail(client, "rl-reset").status_code == 401
    blocked = client.post(
        f"{API}/auth/login",
        json={"username": "rl-reset", "password": "RightPass1!"},
    )
    assert blocked.status_code == 429, blocked.text


def test_window_expiry_restores_access(rate_ctx):
    client, redis_client, settings, db = rate_ctx
    create_user(db, "rl-window", "student", password="RightPass1!")
    for _ in range(settings.login_max_failures_per_username):
        assert _fail(client, "rl-window").status_code == 401
    assert client.post(
        f"{API}/auth/login",
        json={"username": "rl-window", "password": "RightPass1!"},
    ).status_code == 429
    # 模拟窗口过期（删除计数键）
    redis_client.delete("login:fail:user:rl-window")
    ok = client.post(
        f"{API}/auth/login",
        json={"username": "rl-window", "password": "RightPass1!"},
    )
    assert ok.status_code == 200, ok.text


def test_forged_forwarded_header_ignored_without_trusted_proxy(rate_ctx):
    """直连 peer 不在可信代理列表：伪造 X-Forwarded-For 不能分散 IP 计数。"""
    client, redis_client, settings, db = rate_ctx
    for index in range(settings.login_max_attempts_per_ip):
        response = _fail(
            client, f"rl-xff-{index}",
            headers={"X-Forwarded-For": f"203.0.113.{index + 1}"},
        )
        assert response.status_code == 401, response.text
    assert _fail(client, "rl-xff-final").status_code == 429


def test_trusted_proxy_forwarded_header_honored(rate_ctx):
    """配置可信代理后，X-Forwarded-For 首地址才作为客户端 IP 参与限流。"""
    client, redis_client, settings, db = rate_ctx
    settings.trusted_proxies = "testclient"
    # 每个伪造客户端 IP 各失败一次：均未达到 IP 阈值 → 不被拦截
    for index in range(settings.login_max_attempts_per_ip):
        response = _fail(
            client, f"rl-trust-{index}",
            headers={"X-Forwarded-For": f"203.0.113.{index + 1}"},
        )
        assert response.status_code == 401, response.text
    assert _fail(client, "rl-trust-final").status_code == 401


def test_redis_down_login_fails_closed(rate_ctx):
    client, redis_client, settings, db = rate_ctx
    create_user(db, "rl-redis", "student", password="RightPass1!")

    class DownRedis:
        def get(self, *args, **kwargs):
            raise redis_lib.exceptions.ConnectionError("down")

        def exists(self, *args, **kwargs):
            raise redis_lib.exceptions.ConnectionError("down")

        def incr(self, *args, **kwargs):
            raise redis_lib.exceptions.ConnectionError("down")

        def ttl(self, *args, **kwargs):
            raise redis_lib.exceptions.ConnectionError("down")

    app = client.app
    app.dependency_overrides[get_redis_client] = lambda: DownRedis()
    down = TestClient(app)
    response = down.post(
        f"{API}/auth/login",
        json={"username": "rl-redis", "password": "RightPass1!"},
    )
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["code"] == "AUTH_SERVICE_UNAVAILABLE"
