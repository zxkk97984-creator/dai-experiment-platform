"""add Studio draft/version asset manifests and object entries

Revision ID: 20260819_0002
Revises: 20260819_0001
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_0002"
down_revision = "20260819_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bigint_pk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

    op.create_table(
        "studio_asset_manifests",
        sa.Column("id", bigint_pk, primary_key=True),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
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
            ["template_id"],
            ["notebook_templates.id"],
            name="fk_studio_asset_manifests_template",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["notebook_template_versions.id"],
            name="fk_studio_asset_manifests_version",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "template_id", name="uq_studio_asset_manifest_template"
        ),
        sa.UniqueConstraint("version_id", name="uq_studio_asset_manifest_version"),
        sa.CheckConstraint(
            "(template_id IS NOT NULL AND version_id IS NULL)"
            " OR (template_id IS NULL AND version_id IS NOT NULL)",
            name="ck_studio_asset_manifest_owner",
        ),
        sa.CheckConstraint(
            "revision >= 1", name="ck_studio_asset_manifest_revision_positive"
        ),
    )

    op.create_table(
        "studio_asset_manifest_entries",
        sa.Column("id", bigint_pk, primary_key=True),
        sa.Column("manifest_id", bigint_pk, nullable=False),
        sa.Column("storage_object_id", bigint_pk, nullable=False),
        sa.Column("relative_path", sa.String(length=500), nullable=False),
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
            ["manifest_id"],
            ["studio_asset_manifests.id"],
            name="fk_studio_asset_entries_manifest",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["storage_object_id"],
            ["storage_objects.id"],
            name="fk_studio_asset_entries_storage_object",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "manifest_id",
            "relative_path",
            name="uq_studio_asset_manifest_entry_path",
        ),
        sa.CheckConstraint(
            "relative_path <> ''",
            name="ck_studio_asset_manifest_entry_path_nonempty",
        ),
    )
    op.create_index(
        "ix_studio_asset_manifest_entries_manifest_id",
        "studio_asset_manifest_entries",
        ["manifest_id"],
        unique=False,
    )
    op.create_index(
        "ix_studio_asset_manifest_entries_storage_object_id",
        "studio_asset_manifest_entries",
        ["storage_object_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_studio_asset_manifest_entries_storage_object_id",
        table_name="studio_asset_manifest_entries",
    )
    op.drop_index(
        "ix_studio_asset_manifest_entries_manifest_id",
        table_name="studio_asset_manifest_entries",
    )
    op.drop_table("studio_asset_manifest_entries")
    op.drop_table("studio_asset_manifests")
