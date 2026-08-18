"""storage_objects additive migration tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.no_auto_env_seed

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    BACKEND_DIR / "alembic" / "versions" / "20260818_0001_storage_objects.py"
)
PREV_REVISION = "20260817_0001"
NEW_REVISION = "20260818_0001"


def _load_migration():
    spec = importlib.util.spec_from_file_location("storage_objects_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_upgrade(engine, migration):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()


def _run_downgrade(engine, migration):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.downgrade()


@pytest.fixture()
def engine():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
    )
    sa.Table(
        "courses",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
    )
    metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_revision_chain_points_to_current_head():
    migration = _load_migration()
    assert migration.revision == NEW_REVISION
    assert migration.down_revision == PREV_REVISION
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_upgrade_creates_metadata_schema_and_downgrade_removes_only_new_table(engine):
    migration = _load_migration()
    _run_upgrade(engine, migration)
    inspector = sa.inspect(engine)

    assert "storage_objects" in inspector.get_table_names()
    columns = {column["name"]: column for column in inspector.get_columns("storage_objects")}
    assert columns["namespace"]["nullable"] is False
    assert columns["object_key"]["nullable"] is False
    assert columns["backend"]["nullable"] is False
    assert columns["status"]["nullable"] is False
    assert columns["size_bytes"]["nullable"] is True
    assert columns["metadata_json"]["nullable"] is False
    assert columns["created_by_id"]["nullable"] is True
    assert columns["deleted_at"]["nullable"] is True
    assert columns["version"]["nullable"] is False

    uniques = inspector.get_unique_constraints("storage_objects")
    assert any(
        set(item["column_names"]) == {"namespace", "object_key"}
        for item in uniques
    )
    indexes = inspector.get_indexes("storage_objects")
    assert any(set(item["column_names"]) == {"namespace", "status"} for item in indexes)
    assert any(set(item["column_names"]) == {"status", "deleted_at"} for item in indexes)
    fks = inspector.get_foreign_keys("storage_objects")
    created_by_fk = next(fk for fk in fks if fk["constrained_columns"] == ["created_by_id"])
    assert created_by_fk["referred_table"] == "users"
    assert created_by_fk["options"].get("ondelete") == "SET NULL"

    _run_downgrade(engine, migration)
    inspector = sa.inspect(engine)
    assert "storage_objects" not in inspector.get_table_names()
    assert {"users", "courses"}.issubset(set(inspector.get_table_names()))


def test_upgrade_preserves_existing_business_rows_and_enforces_constraints(engine):
    migration = _load_migration()
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO courses (id, title) VALUES (1, 'unchanged')"))
    _run_upgrade(engine, migration)
    table = sa.Table("storage_objects", sa.MetaData(), autoload_with=engine)
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO users (id, username) VALUES (1, 'owner')"))
        connection.execute(
            table.insert().values(
                namespace="course-covers",
                object_key="covers/1/a.jpg",
                backend="local",
                status="staging",
                size_bytes=0,
                metadata_json={"source": "test"},
                created_by_id=1,
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                table.insert().values(
                    namespace="course-covers",
                    object_key="covers/1/a.jpg",
                    backend="s3",
                    status="staging",
                    size_bytes=0,
                    metadata_json={},
                )
            )

    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT title FROM courses WHERE id = 1")) == "unchanged"

    for values in (
        {"namespace": "invalid", "object_key": "negative", "backend": "local", "status": "staging", "size_bytes": -1, "metadata_json": {}},
        {"namespace": "invalid", "object_key": "status", "backend": "local", "status": "unknown", "size_bytes": 0, "metadata_json": {}},
    ):
        with engine.begin() as connection:
            with pytest.raises(IntegrityError):
                connection.execute(table.insert().values(**values))
