"""视频上传字段迁移测试：新增列 / 存量保持 external / downgrade 逆序删除

- 迁移只在隔离数据库上执行（SQLite 内存库 + 最小前置 schema）
- 真实 MySQL 验证见部署流程，不在本测试内
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "a3b4c5d6e789_add_lesson_video_uploads.py"
)

PREV_REVISION = "f2a3b4c5d678"


def _load_migration():
    spec = importlib.util.spec_from_file_location("lesson_video_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _minimal_schema(engine) -> None:
    """只创建 upgrade 需要引用的前置表（lessons），不依赖 ORM 模型。"""
    meta = sa.MetaData()
    sa.Table(
        "lessons",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chapter_id", sa.Integer()),
        sa.Column("title", sa.String(200)),
        sa.Column("content_type", sa.String(30)),
        sa.Column("video_url", sa.String(500), nullable=True),
        sa.Column("order_index", sa.Integer()),
    )
    meta.create_all(engine)


@pytest.fixture()
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
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


def test_revision_chain_points_to_current_head():
    """新迁移的 down_revision 必须指向实施时唯一 head f2a3b4c5d678"""
    migration = _load_migration()
    assert migration.revision
    assert migration.down_revision == PREV_REVISION


def test_upgrade_adds_columns_with_types_and_defaults(engine):
    """upgrade 增加五列：类型、可空性、默认值正确"""
    migration = _load_migration()
    _minimal_schema(engine)
    _run_upgrade(engine, migration)

    inspector = sa.inspect(engine)
    cols = {c["name"]: c for c in inspector.get_columns("lessons")}
    assert cols["video_source"]["nullable"] is False
    assert cols["video_source"]["type"].length == 20
    assert cols["video_storage_key"]["nullable"] is True
    assert cols["video_storage_key"]["type"].length == 500
    assert cols["video_filename"]["nullable"] is True
    assert cols["video_filename"]["type"].length == 255
    assert cols["video_content_type"]["nullable"] is True
    assert cols["video_content_type"]["type"].length == 100
    assert cols["video_size"]["nullable"] is True

    # 默认值为 external：新插入行自动生效
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO lessons (chapter_id, title, content_type, order_index) "
                "VALUES (1, 't', 'video', 0)"
            )
        )
        row = conn.execute(sa.text("SELECT video_source FROM lessons")).scalar()
    assert row == "external"


def test_upgrade_preserves_existing_video_url_rows(engine):
    """迁移前已有 video_url 的行迁移后为 external 且 URL 不变"""
    migration = _load_migration()
    _minimal_schema(engine)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO lessons (chapter_id, title, content_type, video_url, order_index) "
                "VALUES (1, 't1', 'video', 'https://v.example.com/a.mp4', 0), "
                "(1, 't2', 'markdown', NULL, 1)"
            )
        )

    _run_upgrade(engine, migration)

    with engine.connect() as conn:
        rows = conn.execute(
            sa.text("SELECT video_url, video_source FROM lessons ORDER BY id")
        ).all()
    assert rows == [
        ("https://v.example.com/a.mp4", "external"),
        (None, "external"),
    ]


def test_downgrade_drops_new_columns_keeps_video_url(engine):
    """downgrade：新增列全部删除，原 video_url 仍存在"""
    migration = _load_migration()
    _minimal_schema(engine)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO lessons (chapter_id, title, content_type, video_url, order_index) "
                "VALUES (1, 't', 'video', 'https://v.example.com/a.mp4', 0)"
            )
        )
    _run_upgrade(engine, migration)
    with engine.begin() as conn:
        conn.execute(
            sa.text("UPDATE lessons SET video_source='upload', video_storage_key='lessons/1/x.mp4'")
        )

    _run_downgrade(engine, migration)

    inspector = sa.inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("lessons")}
    for dropped in ("video_source", "video_storage_key", "video_filename", "video_content_type", "video_size"):
        assert dropped not in cols, f"{dropped} 应被降级删除"
    assert "video_url" in cols
    with engine.connect() as conn:
        url = conn.execute(sa.text("SELECT video_url FROM lessons")).scalar()
    assert url == "https://v.example.com/a.mp4"
