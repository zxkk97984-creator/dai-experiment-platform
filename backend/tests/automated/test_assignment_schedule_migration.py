"""作业首次发布时间迁移验证。"""

import importlib.util
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _load_migration():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260812_0002_assignment_schedule.py"
    )
    spec = importlib.util.spec_from_file_location("assignment_schedule_migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_backfills_only_currently_published_assignments():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    assignments = sa.Table(
        "assignments",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    metadata.create_all(engine)
    published_created = datetime(2026, 7, 1, 8, 0)
    draft_created = datetime(2026, 7, 2, 8, 0)

    with engine.begin() as connection:
        connection.execute(
            assignments.insert(),
            [
                {"id": 1, "status": "published", "created_at": published_created},
                {"id": 2, "status": "draft", "created_at": draft_created},
            ],
        )
        migration = _load_migration()
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()

        migrated = sa.Table("assignments", sa.MetaData(), autoload_with=connection)
        rows = connection.execute(
            sa.select(migrated.c.id, migrated.c.published_at).order_by(migrated.c.id)
        ).all()

    assert rows == [(1, published_created), (2, None)]
