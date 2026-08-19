"""Additive migration tests for Studio asset manifests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


pytestmark = pytest.mark.no_auto_env_seed

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    BACKEND_DIR / "alembic" / "versions" / "20260819_0002_studio_asset_manifests.py"
)
PREV_REVISION = "20260819_0001"
NEW_REVISION = "20260819_0002"


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "studio_asset_manifest_migration", MIGRATION_PATH
    )
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
    for table_name in (
        "users",
        "notebook_templates",
        "notebook_template_versions",
        "storage_objects",
    ):
        sa.Table(table_name, metadata, sa.Column("id", sa.Integer(), primary_key=True))
    metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_revision_chain_points_to_phase_3_head():
    migration = _load_migration()
    assert migration.revision == NEW_REVISION
    assert migration.down_revision == PREV_REVISION
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_upgrade_creates_manifest_and_entry_tables_and_downgrade_is_additive(engine):
    migration = _load_migration()
    _run_upgrade(engine, migration)
    inspector = sa.inspect(engine)

    assert {
        "users",
        "notebook_templates",
        "notebook_template_versions",
        "storage_objects",
        "studio_asset_manifests",
        "studio_asset_manifest_entries",
    }.issubset(set(inspector.get_table_names()))

    manifest_columns = {
        column["name"]: column
        for column in inspector.get_columns("studio_asset_manifests")
    }
    assert manifest_columns["template_id"]["nullable"] is True
    assert manifest_columns["version_id"]["nullable"] is True
    assert manifest_columns["revision"]["nullable"] is False

    entry_columns = {
        column["name"]: column
        for column in inspector.get_columns("studio_asset_manifest_entries")
    }
    assert entry_columns["manifest_id"]["nullable"] is False
    assert entry_columns["storage_object_id"]["nullable"] is False
    assert entry_columns["relative_path"]["nullable"] is False

    manifest_uniques = inspector.get_unique_constraints("studio_asset_manifests")
    assert any(item["column_names"] == ["template_id"] for item in manifest_uniques)
    assert any(item["column_names"] == ["version_id"] for item in manifest_uniques)
    entry_uniques = inspector.get_unique_constraints("studio_asset_manifest_entries")
    assert any(
        item["column_names"] == ["manifest_id", "relative_path"]
        for item in entry_uniques
    )

    manifest_fks = inspector.get_foreign_keys("studio_asset_manifests")
    assert {
        fk["referred_table"] for fk in manifest_fks
    } == {"notebook_templates", "notebook_template_versions"}
    entry_fks = inspector.get_foreign_keys("studio_asset_manifest_entries")
    assert {
        fk["referred_table"] for fk in entry_fks
    } == {"studio_asset_manifests", "storage_objects"}
    storage_fk = next(
        fk for fk in entry_fks if fk["referred_table"] == "storage_objects"
    )
    assert storage_fk["options"].get("ondelete") == "RESTRICT"

    _run_downgrade(engine, migration)
    inspector = sa.inspect(engine)
    assert "studio_asset_manifests" not in inspector.get_table_names()
    assert "studio_asset_manifest_entries" not in inspector.get_table_names()
    assert {
        "users",
        "notebook_templates",
        "notebook_template_versions",
        "storage_objects",
    }.issubset(set(inspector.get_table_names()))


def test_upgrade_enforces_owner_and_path_uniqueness_without_touching_parent_rows(engine):
    migration = _load_migration()
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO users (id) VALUES (1)"))
        connection.execute(sa.text("INSERT INTO notebook_templates (id) VALUES (10)"))
        connection.execute(
            sa.text("INSERT INTO notebook_template_versions (id) VALUES (20)")
        )
        connection.execute(sa.text("INSERT INTO storage_objects (id) VALUES (30)"))
    _run_upgrade(engine, migration)

    metadata = sa.MetaData()
    manifests = sa.Table("studio_asset_manifests", metadata, autoload_with=engine)
    entries = sa.Table(
        "studio_asset_manifest_entries", metadata, autoload_with=engine
    )
    with engine.begin() as connection:
        connection.execute(manifests.insert().values(id=1, template_id=10, revision=1))
        connection.execute(
            entries.insert().values(
                id=1,
                manifest_id=1,
                storage_object_id=30,
                relative_path="assets/data.csv",
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                entries.insert().values(
                    id=2,
                    manifest_id=1,
                    storage_object_id=30,
                    relative_path="assets/data.csv",
                )
            )

        with pytest.raises(IntegrityError):
            connection.execute(
                manifests.insert().values(
                    id=2,
                    template_id=10,
                    version_id=20,
                    revision=1,
                )
            )

        connection.execute(manifests.insert().values(id=3, version_id=20, revision=1))
        with pytest.raises(IntegrityError):
            connection.execute(manifests.insert().values(id=4, version_id=20, revision=1))

        with pytest.raises(IntegrityError):
            connection.execute(
                entries.insert().values(
                    id=4,
                    manifest_id=1,
                    storage_object_id=30,
                    relative_path="",
                )
            )

    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT id FROM users")) == 1
        assert connection.scalar(sa.text("SELECT id FROM notebook_templates")) == 10
        assert connection.scalar(sa.text("SELECT id FROM storage_objects")) == 30
