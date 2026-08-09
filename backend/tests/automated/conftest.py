import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
import fakeredis

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings, get_settings
from app.database import Base, create_engine_from_url, sessionmaker_for_engine
from app.dependencies import get_db, get_redis_client
from app.main import create_app
from app.models import User
from app.security import hash_password


@pytest.fixture()
def test_settings(tmp_path):
    # 可通过 DAI_DATABASE_URL 环境变量切换到 MySQL（CI job 设置此变量）
    # 仅在未设置环境变量时创建临时 SQLite 数据库
    db_url = os.environ.get("DAI_DATABASE_URL", "")
    if not db_url:
        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"
    return Settings(
        database_url=db_url,
        redis_url=os.environ.get("DAI_REDIS_URL", "redis://localhost:6379/15"),
        secret_key="test-secret-key",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
        jupyter_base_url="http://localhost:8888",
        judge_use_docker=False,
        judge_timeout_seconds=5,
        studio_storage_dir=str(tmp_path / "studio"),
        # 测试视频目录指向临时目录，绝不写入真实 backend/storage/videos/
        video_storage_dir=str(tmp_path / "videos"),
        video_max_upload_bytes=500 * 1024 * 1024,
        video_playback_url_ttl_seconds=3600,
        # 测试封面目录指向临时目录，绝不写入真实 backend/storage/covers/
        cover_storage_dir=str(tmp_path / "covers"),
        cover_max_upload_bytes=5 * 1024 * 1024,
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
    app.dependency_overrides[get_settings] = lambda: test_settings
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
    data = response.json()
    # refresh_token 在 HttpOnly Cookie 中，TestClient 不返回 Cookie 的值
    # 从 Set-Cookie 头中提取（测试需要）
    refresh_token = ""
    for cookie_str in response.headers.get_list("set-cookie"):
        if "dai_refresh_token=" in cookie_str:
            refresh_token = cookie_str.split("dai_refresh_token=")[1].split(";")[0]
            break
    return data["access_token"], refresh_token


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}
