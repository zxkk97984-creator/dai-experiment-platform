"""健康检查端点语义测试（TASK-003：Redis 是 ready 的关键依赖）。

- ready 在 MySQL/Redis 任一故障时返回 503，恢复后回到 200
- live 只反映进程存活，不检查任何依赖
- 响应不回显底层异常详情（checks 值仅为 ok / unavailable）
"""
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_db, get_redis_client
from app.main import create_app


class _DownRedis:
    """Redis 故障桩：ping 抛连接错误（模拟 Redis 不可达）"""

    def ping(self):
        raise ConnectionError("Redis connection refused")


class _DownDB:
    """MySQL 故障桩：execute 抛异常（模拟数据库不可达）"""

    def __init__(self):
        self.closed = False

    def execute(self, *args, **kwargs):
        raise RuntimeError("Lost connection to MySQL server")

    def close(self):
        self.closed = True


def _db_override_factory(db_session_factory):
    def override_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    return override_db


def _down_db_dependency():
    """MySQL 故障依赖桩：FastAPI generator dependency，yield 一个 execute 即抛异常的会话。"""
    yield _DownDB()


@pytest.fixture()
def health_app(test_settings, db_session_factory, redis_client):
    app = create_app(test_settings)
    app.dependency_overrides[get_db] = _db_override_factory(db_session_factory)
    app.dependency_overrides[get_redis_client] = lambda: redis_client
    return app


def _client_with_overrides(app, *, redis=None, db_factory=None):
    if redis is not None:
        app.dependency_overrides[get_redis_client] = lambda: redis
    if db_factory is not None:
        app.dependency_overrides[get_db] = db_factory
    return TestClient(app)


def test_live_always_ok(health_app):
    client = TestClient(health_app)
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_live_unaffected_by_dependency_failures(health_app):
    """liveness 不检查 MySQL/Redis：依赖全挂时仍返回 200。"""
    client = _client_with_overrides(
        health_app, redis=_DownRedis(), db_factory=_down_db_dependency,
    )
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_healthy(health_app):
    client = TestClient(health_app)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"mysql": "ok", "redis": "ok"}


def test_ready_redis_down(health_app):
    """Redis 故障时 ready 返回 503（认证/限流/队列唤醒均依赖 Redis）。"""
    client = _client_with_overrides(health_app, redis=_DownRedis())
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"] == "unavailable"
    assert body["checks"]["mysql"] == "ok"
    # 不回显底层异常详情
    assert "connection" not in str(body).lower()


def test_ready_mysql_down(health_app):
    client = _client_with_overrides(health_app, db_factory=_down_db_dependency)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["checks"] == {"mysql": "unavailable", "redis": "ok"}
    assert "db down" not in str(body)


def test_ready_both_down(health_app):
    client = _client_with_overrides(
        health_app, redis=_DownRedis(), db_factory=_down_db_dependency,
    )
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"mysql": "unavailable", "redis": "unavailable"}


def test_ready_recovers_after_redis_restored(health_app, redis_client):
    """Redis 恢复后 ready 回到 200（依赖恢复即可重新摘回流量）。"""
    client = _client_with_overrides(health_app, redis=_DownRedis())
    assert client.get("/api/v1/health/ready").status_code == 503

    # 恢复：依赖覆盖切回健康的 fakeredis（模拟 Redis 重新可用）
    health_app.dependency_overrides[get_redis_client] = lambda: redis_client
    recovered = TestClient(health_app)
    response = recovered.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"mysql": "ok", "redis": "ok"}


def test_root_health_alias_ok(health_app):
    """/health 别名端点保持可用（运维探测入口）。"""
    client = TestClient(health_app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
