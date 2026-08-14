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

    seed_basic_environment(db_session_factory)
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

    seed_basic_environment(db_session_factory)
    with db_session_factory() as db:
        teacher = db.query(User).filter(User.username == teacher_username).first()
        kwargs = dict(
            course_id=course_id,
            title=title,
            status=status,
            due_at=due_at,
            created_by_id=teacher.id if teacher else None,
        )
        # 环境版本 NOT NULL：显式传 None 会绕过模型 default，仅非 None 时传参
        if environment_version_id is not None:
            kwargs["environment_version_id"] = environment_version_id
        assignment = Assignment(**kwargs)
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        return assignment.id


def seed_basic_environment(db_or_factory):
    """幂等 seed：basic 档位 available 版本（带 digest）。

    模型层 environment_version_id 已与迁移 B 对齐为 NOT NULL，
    未显式绑定环境的测试记录依赖 resolve_basic_env_version_id 惰性默认，
    需要库中存在 basic 可用版本；环境控制面自身的测试不要调用本 helper。
    参数可以是 session factory，也可以是一个已打开的 Session。
    """
    from app.models import EnvironmentProfile, EnvironmentVersion

    def _seed(session):
        if (
            session.query(EnvironmentProfile)
            .filter(EnvironmentProfile.slug == "basic")
            .first()
            is not None
        ):
            return
        profile = EnvironmentProfile(
            slug="basic", display_name="Python 基础", status="active"
        )
        session.add(profile)
        session.flush()
        version = EnvironmentVersion(
            profile_id=profile.id,
            version_number=1,
            status="available",
            base_image_ref="python:3.12-slim@sha256:" + "0" * 64,
            image_digest="sha256:" + "1" * 64,
            python_version="3.12",
            minimum_memory_mb=256,
            manifest_sha256="c" * 64,
        )
        session.add(version)
        session.commit()

    if hasattr(db_or_factory, "query") and hasattr(db_or_factory, "add"):
        _seed(db_or_factory)
    else:
        with db_or_factory() as session:
            _seed(session)


@pytest.fixture(autouse=True)
def _auto_seed_basic_environment(request, db_session_factory):
    """所有测试默认预置 basic 可用环境版本（模型层 environment_version_id 已 NOT NULL）。

    直接操作环境控制面表的测试（environment_*/seed_data）自行管理种子数据，
    通过 pytestmark = pytest.mark.no_auto_env_seed 关闭本 fixture。
    """
    marker = request.node.get_closest_marker("no_auto_env_seed")
    if marker is None:
        seed_basic_environment(db_session_factory)


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
