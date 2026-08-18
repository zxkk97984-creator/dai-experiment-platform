"""Phase 2B additive Course/Lesson StorageObject binding migration tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


pytestmark = pytest.mark.no_auto_env_seed

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    BACKEND_DIR
    / "alembic"
    / "versions"
    / "20260819_0001_bind_course_media_storage_objects.py"
)
PREV_REVISION = "20260818_0001"
NEW_REVISION = "20260819_0001"


def _load_migration():
    spec = importlib.util.spec_from_file_location("course_media_storage_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _minimal_schema(engine) -> None:
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    sa.Table(
        "storage_objects",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    sa.Table(
        "courses",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("cover", sa.String(500), nullable=True),
    )
    sa.Table(
        "lessons",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chapter_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(30), nullable=False),
        sa.Column("video_url", sa.String(500), nullable=True),
        sa.Column("video_storage_key", sa.String(500), nullable=True),
    )
    metadata.create_all(engine)


def _run_migration(engine, function_name: str) -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = _load_migration()
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            getattr(migration, function_name)()


@pytest.fixture()
def engine():
    engine = sa.create_engine("sqlite://")
    _minimal_schema(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_revision_is_additive_child_of_storage_objects_head():
    migration = _load_migration()
    assert migration.revision == NEW_REVISION
    assert migration.down_revision == PREV_REVISION
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_upgrade_adds_nullable_foreign_keys_without_backfill(engine):
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO courses (id, title, cover) VALUES (1, 'legacy', 'data:image/png;base64,AAAA')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO lessons (id, chapter_id, title, content_type, video_url, video_storage_key) "
                "VALUES (1, 1, 'legacy video', 'video', 'https://example.test/a.mp4', 'lessons/1/a.mp4')"
            )
        )

    _run_migration(engine, "upgrade")
    inspector = sa.inspect(engine)
    course_columns = {column["name"]: column for column in inspector.get_columns("courses")}
    lesson_columns = {column["name"]: column for column in inspector.get_columns("lessons")}
    assert course_columns["cover_object_id"]["nullable"] is True
    assert lesson_columns["video_object_id"]["nullable"] is True
    assert any(
        fk["constrained_columns"] == ["cover_object_id"]
        and fk["referred_table"] == "storage_objects"
        for fk in inspector.get_foreign_keys("courses")
    )
    assert any(
        fk["constrained_columns"] == ["video_object_id"]
        and fk["referred_table"] == "storage_objects"
        for fk in inspector.get_foreign_keys("lessons")
    )

    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT cover, cover_object_id FROM courses")).one() == (
            "data:image/png;base64,AAAA",
            None,
        )
        assert connection.execute(
            sa.text("SELECT video_url, video_storage_key, video_object_id FROM lessons")
        ).one() == ("https://example.test/a.mp4", "lessons/1/a.mp4", None)


def test_downgrade_removes_only_new_binding_columns(engine):
    _run_migration(engine, "upgrade")
    _run_migration(engine, "downgrade")
    assert "cover_object_id" not in {column["name"] for column in sa.inspect(engine).get_columns("courses")}
    assert "video_object_id" not in {column["name"] for column in sa.inspect(engine).get_columns("lessons")}
    assert "cover" in {column["name"] for column in sa.inspect(engine).get_columns("courses")}
    assert "video_storage_key" in {column["name"] for column in sa.inspect(engine).get_columns("lessons")}
