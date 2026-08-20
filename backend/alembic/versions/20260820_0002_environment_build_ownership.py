"""Persist environment build ownership and mode.

Revision ID: 20260820_0002
Revises: 20260820_0001
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260820_0002"
down_revision = "20260820_0001"
branch_labels = None
depends_on = None


def _alter_nullable(table: str, column: str, existing_type: sa.TypeEngine) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table, recreate="always") as batch_op:
            batch_op.alter_column(
                column,
                existing_type=existing_type,
                existing_nullable=True,
                nullable=False,
            )
        return
    op.alter_column(
        table,
        column,
        existing_type=existing_type,
        existing_nullable=True,
        nullable=False,
    )


def upgrade() -> None:
    op.add_column(
        "environment_versions",
        sa.Column("build_mode", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "environment_build_jobs",
        sa.Column("build_mode", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "environment_build_jobs",
        sa.Column("lease_token", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "environment_build_jobs",
        sa.Column("build_config_fingerprint", sa.CHAR(length=64), nullable=True),
    )

    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE environment_versions SET build_mode = 'legacy' WHERE build_mode IS NULL")
    )
    bind.execute(
        sa.text("UPDATE environment_build_jobs SET build_mode = 'legacy' WHERE build_mode IS NULL")
    )
    _alter_nullable("environment_versions", "build_mode", sa.String(length=16))
    _alter_nullable("environment_build_jobs", "build_mode", sa.String(length=16))


def downgrade() -> None:
    op.drop_column("environment_build_jobs", "build_config_fingerprint")
    op.drop_column("environment_build_jobs", "lease_token")
    op.drop_column("environment_build_jobs", "build_mode")
    op.drop_column("environment_versions", "build_mode")
