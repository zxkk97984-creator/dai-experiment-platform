"""课程可见范围迁移测试：白名单表 / 约束 / 级联删除 / downgrade 归一化

- 迁移只在隔离数据库上执行（SQLite 内存库 + 最小前置 schema）
- 真实 MySQL 验证见部署流程，不在本测试内
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, event

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "f2a3b4c5d678_add_course_whitelist.py"
)

PREV_REVISION = "e1f2a3b4c567"


def _load_migration():
    spec = importlib.util.spec_from_file_location("course_whitelist_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _minimal_schema(engine) -> None:
    """只创建 upgrade 需要引用的前置表（courses / users），不依赖 ORM 模型。"""
    meta = sa.MetaData()
    sa.Table(
        "courses",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200)),
        sa.Column("teacher_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30)),
        sa.Column("visibility", sa.String(20)),
    )
    sa.Table(
        "users",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80)),
    )
    meta.create_all(engine)


@pytest.fixture()
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    try:
        yield engine
    finally:
        engine.dispose()


def _run_upgrade(engine, migration):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.upgrade()


def _run_downgrade(engine, migration):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.downgrade()


def _insert_visibility(engine, visibility):
    with engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO courses (title, status, visibility) VALUES (:t, 'published', :v)"),
            {"t": f"课程-{visibility}", "v": visibility},
        )


def test_revision_chain_points_to_course_settings_head():
    """新迁移的 down_revision 必须指向当前 head e1f2a3b4c567"""
    migration = _load_migration()
    assert migration.revision
    assert migration.down_revision == PREV_REVISION


def test_upgrade_creates_whitelist_table_with_constraints(engine):
    """upgrade 创建表、唯一约束、级联外键与反向复合索引"""
    migration = _load_migration()
    _minimal_schema(engine)
    _run_upgrade(engine, migration)

    inspector = sa.inspect(engine)
    assert "course_whitelist_students" in inspector.get_table_names()

    cols = {c["name"]: c for c in inspector.get_columns("course_whitelist_students")}
    assert cols["course_id"]["nullable"] is False
    assert cols["student_id"]["nullable"] is False
    assert "created_at" in cols
    assert "updated_at" in cols

    # 唯一约束
    uq_names = {c["name"] for c in inspector.get_unique_constraints("course_whitelist_students")}
    assert "uq_course_whitelist_student" in uq_names

    # 两个级联外键
    fks = inspector.get_foreign_keys("course_whitelist_students")
    fk_map = {tuple(fk["constrained_columns"]): fk for fk in fks}
    assert set(fk_map) == {("course_id",), ("student_id",)}
    assert fk_map[("course_id",)]["referred_table"] == "courses"
    assert fk_map[("student_id",)]["referred_table"] == "users"
    assert fk_map[("course_id",)]["options"].get("ondelete") == "CASCADE"
    assert fk_map[("student_id",)]["options"].get("ondelete") == "CASCADE"

    # 反向复合索引
    idx = {i["name"] for i in inspector.get_indexes("course_whitelist_students")}
    assert "ix_course_whitelist_students_student_course" in idx


def test_upgrade_preserves_existing_visibility_values(engine):
    """upgrade 不修改任何现有 courses.visibility 值"""
    migration = _load_migration()
    _minimal_schema(engine)
    for vis in ("private", "public", "whitelist"):
        _insert_visibility(engine, vis)
    _run_upgrade(engine, migration)

    with engine.connect() as conn:
        rows = conn.execute(
            sa.text("SELECT visibility FROM courses ORDER BY id")
        ).scalars().all()
    assert rows == ["private", "public", "whitelist"]


def test_orm_create_all_enforces_unique_entry(db_session_factory):
    """ORM create_all 建表下，(course_id, student_id) 唯一约束生效"""
    from app.models import Course, CourseWhitelistStudent, User

    with db_session_factory() as db:
        teacher = User(username="t-uniq", real_name="T", role="teacher", password_hash="x")
        student = User(username="s-uniq", real_name="S", role="student", password_hash="x")
        db.add_all([teacher, student])
        db.commit()
        course = Course(title="唯一约束课程", teacher_id=teacher.id)
        db.add(course)
        db.commit()
        db.add_all([
            CourseWhitelistStudent(course_id=course.id, student_id=student.id),
            CourseWhitelistStudent(course_id=course.id, student_id=student.id),
        ])
        with pytest.raises(sa.exc.IntegrityError):
            db.commit()
        db.rollback()


def test_cascade_delete_on_course_and_user(engine):
    """删除课程或用户时白名单关联行级联删除"""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = _load_migration()
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(80))"))
        conn.execute(
            sa.text("CREATE TABLE courses (id INTEGER PRIMARY KEY, title VARCHAR(200), teacher_id INTEGER, status VARCHAR(30), visibility VARCHAR(20))")
        )
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.upgrade()
        conn.execute(sa.text("INSERT INTO users (id, username) VALUES (1, 's1')"))
        conn.execute(sa.text("INSERT INTO courses (id, title, status, visibility) VALUES (1, 'c1', 'published', 'whitelist')"))
        conn.execute(sa.text("INSERT INTO course_whitelist_students (course_id, student_id) VALUES (1, 1)"))

    # 删除课程 → 关联行消失
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM courses WHERE id = 1"))
        n = conn.execute(sa.text("SELECT COUNT(*) FROM course_whitelist_students")).scalar()
        assert n == 0

    # 重建并删除用户 → 关联行消失
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO courses (id, title, status, visibility) VALUES (2, 'c2', 'published', 'whitelist')"))
        conn.execute(sa.text("INSERT INTO course_whitelist_students (course_id, student_id) VALUES (2, 1)"))
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM users WHERE id = 1"))
        n = conn.execute(sa.text("SELECT COUNT(*) FROM course_whitelist_students")).scalar()
        assert n == 0


def test_downgrade_normalizes_visibility_and_drops_table(engine):
    """downgrade：public/whitelist 归一化为 private，并删除白名单表"""
    migration = _load_migration()
    _minimal_schema(engine)
    for vis in ("private", "public", "whitelist"):
        _insert_visibility(engine, vis)
    _run_upgrade(engine, migration)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO users (id, username) VALUES (1, 's1')"))
        conn.execute(sa.text("INSERT INTO course_whitelist_students (course_id, student_id) VALUES (1, 1)"))

    _run_downgrade(engine, migration)

    inspector = sa.inspect(engine)
    assert "course_whitelist_students" not in inspector.get_table_names()
    with engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT visibility FROM courses ORDER BY id")).scalars().all()
    assert rows == ["private", "private", "private"]
