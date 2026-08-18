"""add storage object metadata foundation

Revision ID: 20260818_0001
Revises: 20260817_0001
Create Date: 2026-08-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260818_0001"
down_revision = "20260817_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bigint_pk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        "storage_objects",
        sa.Column("id", bigint_pk, nullable=False),
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("backend", sa.String(length=32), nullable=False, server_default="local"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="staging"),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("etag", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("namespace", "object_key", name="uq_storage_objects_namespace_key"),
        sa.CheckConstraint("namespace <> ''", name="ck_storage_objects_namespace_nonempty"),
        sa.CheckConstraint("object_key <> ''", name="ck_storage_objects_key_nonempty"),
        sa.CheckConstraint("backend <> ''", name="ck_storage_objects_backend_nonempty"),
        sa.CheckConstraint(
            "status IN ('staging', 'active', 'deleting', 'deleted', 'failed')",
            name="ck_storage_objects_status",
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="ck_storage_objects_size_nonnegative",
        ),
        sa.CheckConstraint(
            "sha256 IS NULL OR length(sha256) = 64",
            name="ck_storage_objects_sha256_length",
        ),
        sa.CheckConstraint("version >= 1", name="ck_storage_objects_version_positive"),
        sa.CheckConstraint(
            "(status = 'deleted' AND deleted_at IS NOT NULL)"
            " OR (status <> 'deleted' AND deleted_at IS NULL)",
            name="ck_storage_objects_deleted_at_status",
        ),
    )
    op.create_index(
        "ix_storage_objects_created_by_id",
        "storage_objects",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        "ix_storage_objects_namespace_status",
        "storage_objects",
        ["namespace", "status"],
        unique=False,
    )
    op.create_index(
        "ix_storage_objects_status_deleted_at",
        "storage_objects",
        ["status", "deleted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_storage_objects_status_deleted_at", table_name="storage_objects")
    op.drop_index("ix_storage_objects_namespace_status", table_name="storage_objects")
    op.drop_index("ix_storage_objects_created_by_id", table_name="storage_objects")
    op.drop_table("storage_objects")
