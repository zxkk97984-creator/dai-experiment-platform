"""健康端点语义测试：ready 必须真实反映 MySQL + Redis 双依赖，live 只判断进程存活。

Redis 承载 Refresh Token、黑名单与队列唤醒，是认证关键依赖；
Redis 故障时 ready 必须返回 503，且响应不得回显底层异常详情。
"""

import pytest

import redis as redis_lib


class _HealthyRedis:
    def __init__(self, **kwargs):
        pass

    def ping(self):
        return True

    @classmethod
    def from_url(cls, url, **kwargs):
        return cls()


class _DownRedis:
    @classmethod
    def from_url(cls, url, **kwargs):
        raise redis_lib.ConnectionError("redis host unreachable")


class _HealthyDB:
    def execute(self, stmt):
        return None

    def close(self):
        pass


class _DownDB:
    def execute(self, stmt):
        raise RuntimeError("mysql connection refused")

    def close(self):
        pass


@pytest.fixture
def healthy_deps(monkeypatch):
    monkeypatch.setattr(redis_lib.Redis, "from_url", _HealthyRedis.from_url)
    monkeypatch.setattr("app.database.SessionLocal", lambda: _HealthyDB())


@pytest.fixture
def redis_down(monkeypatch):
    monkeypatch.setattr(redis_lib.Redis, "from_url", _DownRedis.from_url)
    monkeypatch.setattr("app.database.SessionLocal", lambda: _HealthyDB())


@pytest.fixture
def mysql_down(monkeypatch):
    monkeypatch.setattr(redis_lib.Redis, "from_url", _HealthyRedis.from_url)
    monkeypatch.setattr("app.database.SessionLocal", lambda: _DownDB())


@pytest.fixture
def all_down(monkeypatch):
    monkeypatch.setattr(redis_lib.Redis, "from_url", _DownRedis.from_url)
    monkeypatch.setattr("app.database.SessionLocal", lambda: _DownDB())


def test_ready_returns_200_when_mysql_and_redis_healthy(client, healthy_deps):
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["mysql"] == "ok"
    assert body["checks"]["redis"] == "ok"


def test_ready_returns_503_when_redis_down(client, redis_down):
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_ready_returns_503_when_mysql_down(client, mysql_down):
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503


def test_ready_returns_503_when_both_down(client, all_down):
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503


def test_ready_recovers_when_dependencies_restored(client, monkeypatch, all_down):
    assert client.get("/api/v1/health/ready").status_code == 503
    monkeypatch.setattr(redis_lib.Redis, "from_url", _HealthyRedis.from_url)
    monkeypatch.setattr("app.database.SessionLocal", lambda: _HealthyDB())
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200


def test_live_does_not_check_dependencies(client, all_down):
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_does_not_leak_exception_details(client, all_down):
    body = client.get("/api/v1/health/ready").json()
    raw = str(body)
    assert "unavailable" in raw
    for leaked in ("ConnectionError", "RuntimeError", "unreachable", "refused", "Traceback"):
        assert leaked not in raw
