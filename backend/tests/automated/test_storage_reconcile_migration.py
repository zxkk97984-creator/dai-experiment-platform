"""Persistent storage quarantine migration tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


pytestmark = pytest.mark.no_auto_env_seed

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    BACKEND_DIR / "alembic" / "versions" / "20260819_0003_storage_reconcile.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("storage_reconcile_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, migration, operation):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            getattr(migration, operation)()


@pytest.fixture()
def engine():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("storage_objects", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_upgrade_creates_quarantine_ledger_and_downgrade_removes_only_it(engine):
    migration = _load_migration()
    _run(engine, migration, "upgrade")

    inspector = sa.inspect(engine)
    assert "storage_quarantines" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("storage_quarantines")}
    assert {
        "id",
        "backend",
        "area",
        "object_key",
        "object_id",
        "kind",
        "status",
        "first_seen_at",
        "quarantine_until",
        "attempts",
        "last_error",
        "details_json",
        "resolved_at",
        "created_at",
        "updated_at",
    }.issubset(columns)
    indexes = inspector.get_indexes("storage_quarantines")
    assert any(set(index["column_names"]) == {"status", "quarantine_until"} for index in indexes)
    assert any(set(index["column_names"]) == {"object_id", "status"} for index in indexes)

    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO storage_objects (id) VALUES (1)"))
        connection.execute(
            sa.text(
                "INSERT INTO storage_quarantines "
                "(backend, area, object_key, object_id, kind, quarantine_until, details_json) "
                "VALUES ('local', 'covers', 'covers/1/a.png', 1, 'untracked_physical', "
                "CURRENT_TIMESTAMP, '{}')"
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO storage_quarantines "
                    "(backend, area, object_key, kind, quarantine_until, details_json) "
                    "VALUES ('local', 'covers', 'covers/1/a.png', 'untracked_physical', "
                    "CURRENT_TIMESTAMP, '{}')"
                )
            )

    _run(engine, migration, "downgrade")
    inspector = sa.inspect(engine)
    assert "storage_quarantines" not in inspector.get_table_names()
    assert "storage_objects" in inspector.get_table_names()
