"""Tests for the additive environment editor V2 migration."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa


pytestmark = pytest.mark.no_auto_env_seed

BACKEND_DIR = Path(__file__).resolve().parents[2]
OLD_MIGRATION_PATH = (
    BACKEND_DIR / "alembic" / "versions" / "b4c5d6e7f890_add_environment_control_plane.py"
)
MIGRATION_PATH = (
    BACKEND_DIR / "alembic" / "versions" / "20260820_0001_environment_editor_v2.py"
)
OWNERSHIP_MIGRATION_PATH = (
    BACKEND_DIR / "alembic" / "versions" / "20260820_0002_environment_build_ownership.py"
)
LOCK_MIGRATION_PATH = (
    BACKEND_DIR / "alembic" / "versions" / "20260820_0003_environment_registry_lock.py"
)


def _load(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, migration, operation: str) -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            getattr(migration, operation)()


@pytest.fixture()
def engine():
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False})
    try:
        yield engine
    finally:
        engine.dispose()


def _seed_legacy_database(engine) -> None:
    old = _load(OLD_MIGRATION_PATH, "environment_control_plane_for_v2_test")
    meta = sa.MetaData()
    sa.Table(
        "users",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80)),
        sa.Column("role", sa.String(30)),
    ).create(engine)
    _run(engine, old, "upgrade")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO users (id, username, role) VALUES (1, 'admin', 'admin')"))
        conn.execute(
            sa.text(
                "INSERT INTO package_catalog "
                "(id, normalized_name, pip_name, locked_version, import_names, category_tags, "
                "source_key, status, created_by_id, updated_by_id) "
                "VALUES (:id, :normalized_name, :pip_name, :locked_version, :import_names, "
                ":category_tags, 'pypi', 'active', 1, 1)"
            ),
            [
                {
                    "id": 1,
                    "normalized_name": "numpy",
                    "pip_name": "numpy",
                    "locked_version": "2.1.3",
                    "import_names": json.dumps(["numpy"]),
                    "category_tags": json.dumps(["data"]),
                },
                {
                    "id": 2,
                    "normalized_name": "pandas",
                    "pip_name": "pandas",
                    "locked_version": "2.2.3",
                    "import_names": json.dumps(["pandas"]),
                    "category_tags": json.dumps(["data"]),
                },
            ],
        )
        conn.execute(
            sa.text(
                "INSERT INTO environment_profiles "
                "(id, slug, display_name, description, status, created_by_id) "
                "VALUES (1, 'data', 'Data', 'legacy profile', 'active', 1)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO environment_versions "
                "(id, profile_id, version_number, source_version_id, status, base_image_ref, "
                "image_tag, image_digest, python_version, minimum_memory_mb, manifest_sha256, "
                "resolved_packages, created_by_id, available_at) "
                "VALUES "
                "(1, 1, 1, NULL, 'available', 'python:3.12-slim', 'data:v1', "
                ":digest1, NULL, 256, :manifest1, :resolved1, 1, :available1), "
                "(2, 1, 2, 1, 'available', 'python:3.12-slim', 'data:v2', "
                ":digest2, '3.12', 512, :manifest2, :resolved2, 1, :available2), "
                "(3, 1, 3, 2, 'failed', 'python:3.12-slim', NULL, NULL, NULL, 512, "
                ":manifest3, NULL, 1, NULL)"
            ),
            {
                "digest1": "sha256:" + "1" * 64,
                "digest2": "sha256:" + "2" * 64,
                "manifest1": "a" * 64,
                "manifest2": "b" * 64,
                "manifest3": "c" * 64,
                "resolved1": json.dumps({"numpy": "2.1.3", "pip": "24.0"}),
                "resolved2": json.dumps({"numpy": "2.1.3", "pandas": "2.2.3", "pip": "24.0"}),
                "available1": now,
                "available2": now,
            },
        )
        conn.execute(
            sa.text(
                "INSERT INTO profile_version_packages "
                "(environment_version_id, package_catalog_id, display_order) VALUES "
                "(1, 1, 0), (2, 1, 0), (2, 2, 1)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO environment_build_jobs "
                "(id, environment_version_id, status, attempt_number, error_code) VALUES "
                "(10, 1, 'succeeded', 1, NULL), (11, 3, 'failed', 1, 'PIP_RESOLUTION_FAILED')"
            )
        )


def test_revision_and_additive_schema(engine):
    migration = _load(MIGRATION_PATH, "environment_editor_v2_migration_schema")
    assert migration.revision == "20260820_0001"
    assert migration.down_revision == "20260819_0003"

    _seed_legacy_database(engine)
    _run(engine, migration, "upgrade")

    inspector = sa.inspect(engine)
    assert {"environment_drafts", "environment_publications"}.issubset(
        inspector.get_table_names()
    )
    profile_columns = {column["name"]: column for column in inspector.get_columns("environment_profiles")}
    version_columns = {column["name"]: column for column in inspector.get_columns("environment_versions")}
    job_columns = {column["name"]: column for column in inspector.get_columns("environment_build_jobs")}
    assert profile_columns["current_version_id"]["nullable"] is True
    assert version_columns["requested_spec"]["nullable"] is False
    assert version_columns["python_version"]["nullable"] is False
    assert job_columns["phase"]["nullable"] is False
    assert {"error_detail", "result_summary"}.issubset(job_columns)


def test_upgrade_backfills_current_version_publication_and_legacy_specs(engine):
    migration = _load(MIGRATION_PATH, "environment_editor_v2_migration_data")
    _seed_legacy_database(engine)
    _run(engine, migration, "upgrade")

    with engine.connect() as conn:
        profile = conn.execute(
            sa.text("SELECT current_version_id FROM environment_profiles WHERE id = 1")
        ).one()
        assert profile.current_version_id == 2

        versions = {
            row.id: row
            for row in conn.execute(
                sa.text(
                    "SELECT id, python_version, requested_spec, resolved_spec, "
                    "first_published_at, first_published_by_id FROM environment_versions "
                    "ORDER BY id"
                )
            )
        }
        assert versions[1].python_version == "3.12"
        requested_spec = json.loads(versions[1].requested_spec)
        resolved_spec = json.loads(versions[1].resolved_spec)
        assert requested_spec["python_packages"][0]["version"] == "2.1.3"
        assert resolved_spec["resolution_quality"] == "legacy_inferred"
        assert versions[1].first_published_at is None
        assert versions[1].first_published_by_id is None
        assert versions[2].first_published_at is not None
        assert versions[2].first_published_by_id == 1
        assert versions[3].first_published_at is None

        publication = conn.execute(
            sa.text(
                "SELECT profile_id, version_id, previous_version_id, action "
                "FROM environment_publications"
            )
        ).one()
        assert tuple(publication) == (1, 2, None, "migration_baseline")

        phases = dict(conn.execute(sa.text("SELECT id, phase FROM environment_build_jobs")).all())
        assert phases == {10: "done", 11: "done"}


def test_lock_migration_adds_same_profile_constraints_and_guarded_downgrade(
    engine, monkeypatch
):
    _seed_legacy_database(engine)
    _run(engine, _load(MIGRATION_PATH, "environment_editor_v2_v3_schema"), "upgrade")
    _run(engine, _load(OWNERSHIP_MIGRATION_PATH, "environment_editor_v2_v3_ownership"), "upgrade")
    lock_migration = _load(LOCK_MIGRATION_PATH, "environment_editor_v2_v3_lock")
    _run(engine, lock_migration, "upgrade")

    inspector = sa.inspect(engine)
    version_columns = {column["name"] for column in inspector.get_columns("environment_versions")}
    assert {"resolution_lock", "resolution_lock_sha256"}.issubset(version_columns)
    uniques = inspector.get_unique_constraints("environment_versions")
    assert any(
        set(unique["column_names"]) == {"profile_id", "id"} for unique in uniques
    )
    profile_fks = inspector.get_foreign_keys("environment_profiles")
    assert any(
        fk["constrained_columns"] == ["id", "current_version_id"]
        for fk in profile_fks
    )

    monkeypatch.delenv("DAI_ALLOW_ENVIRONMENT_V2_DOWNGRADE", raising=False)
    with pytest.raises(RuntimeError, match="forward-only"):
        _run(engine, lock_migration, "downgrade")

    monkeypatch.setenv("DAI_ALLOW_ENVIRONMENT_V2_DOWNGRADE", "true")
    _run(engine, lock_migration, "downgrade")
    old_columns = {
        column["name"] for column in sa.inspect(engine).get_columns("environment_versions")
    }
    assert "resolution_lock" not in old_columns
    _run(engine, lock_migration, "upgrade")


def test_downgrade_removes_only_v2_schema(engine):
    migration = _load(MIGRATION_PATH, "environment_editor_v2_migration_downgrade")
    _seed_legacy_database(engine)
    _run(engine, migration, "upgrade")
    _run(engine, migration, "downgrade")

    inspector = sa.inspect(engine)
    assert "environment_drafts" not in inspector.get_table_names()
    assert "environment_publications" not in inspector.get_table_names()
    assert "current_version_id" not in {
        column["name"] for column in inspector.get_columns("environment_profiles")
    }
    assert "requested_spec" not in {
        column["name"] for column in inspector.get_columns("environment_versions")
    }
    assert "phase" not in {
        column["name"] for column in inspector.get_columns("environment_build_jobs")
    }

    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM environment_versions")).scalar_one() == 3
        assert conn.execute(sa.text("SELECT COUNT(*) FROM profile_version_packages")).scalar_one() == 3


def test_mysql_downgrade_drops_publication_table_before_its_indexes(monkeypatch):
    """MySQL owns the FK-supporting indexes when the publication table is dropped."""

    migration = _load(MIGRATION_PATH, "environment_editor_v2_migration_mysql_downgrade")

    class _Dialect:
        name = "mysql"

    class _Bind:
        dialect = _Dialect()

    class _RecordingOperations:
        def __init__(self):
            self.events = []

        def get_bind(self):
            return _Bind()

        def drop_table(self, table_name):
            self.events.append(("drop_table", table_name))

        def drop_index(self, index_name, table_name=None):
            self.events.append(("drop_index", index_name, table_name))

        def drop_constraint(self, constraint_name, table_name, type_=None):
            self.events.append(("drop_constraint", constraint_name, table_name, type_))

        def drop_column(self, column_name, table_name):
            self.events.append(("drop_column", column_name, table_name))

    operations = _RecordingOperations()
    monkeypatch.setattr(migration, "op", operations)

    migration.downgrade()

    publication_events = [
        event
        for event in operations.events
        if event[-1] == "environment_publications"
        or (event[0] == "drop_table" and event[1] == "environment_publications")
    ]
    assert publication_events == [("drop_table", "environment_publications")]
