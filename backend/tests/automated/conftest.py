import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
import fakeredis

ROOT = Path(__file__).resolve().parents[2]
PYTEST_TEMP_ROOT = ROOT / ".pytest-temp-root"
PYTEST_TEMP_ROOT.mkdir(exist_ok=True)
os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(PYTEST_TEMP_ROOT))
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
        # 隔离本地 backend/.env：测试永不携带真实 AI Key，杜绝外呼
        ai_api_key="",
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


def create_course_db(
    db_session_factory,
    *,
    teacher_username="teacher",
    title="测试课程",
    description="测试课程描述",
    status="draft",
    visibility="class",
    default_score=100.0,
    cover=None,
    start_time=None,
    academic_term_id=None,
):
    """领域 fixture：直接创建课程行（绕过 API 发布门禁）。

    用于与「课程发布」无关的测试；发布门禁本身由
    test_course_publish_requirements.py 走 API 覆盖。
    """
    from app.models import Course

    with db_session_factory() as db:
        teacher = db.query(User).filter(User.username == teacher_username).first()
        course = Course(
            title=title,
            description=description,
            status=status,
            visibility=visibility,
            default_score=default_score,
            teacher_id=teacher.id if teacher else None,
            cover=cover,
            start_time=start_time,
            academic_term_id=academic_term_id,
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        return course.id


def create_assignment_db(
    db_session_factory,
    *,
    course_id,
    teacher_username="teacher",
    title="测试作业",
    status="draft",
    due_at=None,
    environment_version_id=None,
):
    """领域 fixture：直接创建作业行（绕过 API 发布门禁）。

    用于与「作业发布」无关的测试；发布门禁本身由
    test_assignment_publish_gate.py 走 API 覆盖。
    """
    from app.models import Assignment

    with db_session_factory() as db:
        teacher = db.query(User).filter(User.username == teacher_username).first()
        assignment = Assignment(
            course_id=course_id,
            title=title,
            status=status,
            due_at=due_at,
            environment_version_id=environment_version_id,
            created_by_id=teacher.id if teacher else None,
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        return assignment.id


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
