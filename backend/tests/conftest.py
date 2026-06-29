import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
import fakeredis

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.database import Base, create_engine_from_url, sessionmaker_for_engine
from app.dependencies import get_db, get_redis_client
from app.main import create_app
from app.models import User
from app.security import hash_password


@pytest.fixture()
def test_settings(tmp_path):
    db_path = tmp_path / "test.db"
    return Settings(
        database_url=f"sqlite:///{db_path}",
        redis_url="redis://localhost:6379/15",
        secret_key="test-secret-key",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
        jupyter_base_url="http://localhost:8888",
        judge_use_docker=False,
        judge_timeout_seconds=5,
    )


@pytest.fixture()
def db_session_factory(test_settings):
    engine = create_engine_from_url(test_settings.database_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker_for_engine(engine)
    try:
        yield SessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def redis_client():
    client = fakeredis.FakeRedis(decode_responses=True)
    client.flushall()
    return client


@pytest.fixture()
def app(test_settings, db_session_factory, redis_client):
    os.environ["DAI_SECRET_KEY"] = test_settings.secret_key
    app = create_app(test_settings)

    def override_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis_client] = lambda: redis_client
    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


def create_user(db_session_factory, username, role, password="Passw0rd!", real_name=None):
    with db_session_factory() as db:
        user = User(
            username=username,
            real_name=real_name or username,
            role=role,
            status="active",
            password_hash=hash_password(password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def login(client, username, password="Passw0rd!"):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"], response.json()["refresh_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}
