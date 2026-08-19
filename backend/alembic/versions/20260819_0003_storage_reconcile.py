"""add persistent storage reconcile quarantine ledger

Revision ID: 20260819_0003
Revises: 20260819_0002
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_0003"
down_revision = "20260819_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bigint_pk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

    op.create_table(
        "storage_quarantines",
        sa.Column("id", bigint_pk, primary_key=True),
        sa.Column("backend", sa.String(length=32), nullable=False),
        sa.Column("area", sa.String(length=32), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("object_id", bigint_pk, nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="quarantined",
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("quarantine_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["object_id"],
            ["storage_objects.id"],
            name="fk_storage_quarantines_object",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "backend",
            "area",
            "object_key",
            "kind",
            name="uq_storage_quarantine_target_kind",
        ),
        sa.CheckConstraint(
            "backend IN ('local', 's3')",
            name="ck_storage_quarantine_backend",
        ),
        sa.CheckConstraint(
            "status IN ('quarantined', 'failed', 'resolved')",
            name="ck_storage_quarantine_status",
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_storage_quarantine_attempts_nonnegative",
        ),
        sa.CheckConstraint(
            "(status = 'resolved' AND resolved_at IS NOT NULL)"
            " OR (status <> 'resolved' AND resolved_at IS NULL)",
            name="ck_storage_quarantine_resolved_at_status",
        ),
    )
    op.create_index(
        "ix_storage_quarantines_status_until",
        "storage_quarantines",
        ["status", "quarantine_until"],
        unique=False,
    )
    op.create_index(
        "ix_storage_quarantines_object_status",
        "storage_quarantines",
        ["object_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_storage_quarantines_object_status", table_name="storage_quarantines")
    op.drop_index("ix_storage_quarantines_status_until", table_name="storage_quarantines")
    op.drop_table("storage_quarantines")
