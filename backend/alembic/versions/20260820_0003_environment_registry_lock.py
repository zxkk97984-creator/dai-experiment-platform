"""Persist reproducible V2 locks and allow digest reuse across profiles.

Revision ID: 20260820_0003
Revises: 20260820_0002
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "20260820_0003"
down_revision = "20260820_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "environment_versions",
        sa.Column("resolution_lock", sa.JSON(), nullable=True),
    )
    op.add_column(
        "environment_versions",
        sa.Column("resolution_lock_sha256", sa.CHAR(length=64), nullable=True),
    )
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("environment_versions", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_env_version_image_tag", type_="unique")
            batch_op.drop_constraint("uq_env_version_image_digest", type_="unique")
            batch_op.create_unique_constraint("uq_env_version_profile_id", ["profile_id", "id"])
        with op.batch_alter_table("environment_profiles", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_env_profiles_current_version", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_env_profiles_current_version_profile",
                "environment_versions",
                ["id", "current_version_id"],
                ["profile_id", "id"],
            )
        with op.batch_alter_table("environment_drafts", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_env_drafts_source_version", type_="foreignkey")
            batch_op.drop_constraint("fk_env_drafts_candidate_version", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_env_drafts_source_version_profile",
                "environment_versions",
                ["profile_id", "source_version_id"],
                ["profile_id", "id"],
            )
            batch_op.create_foreign_key(
                "fk_env_drafts_candidate_version_profile",
                "environment_versions",
                ["profile_id", "candidate_version_id"],
                ["profile_id", "id"],
            )
        with op.batch_alter_table("environment_publications", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_env_publications_version", type_="foreignkey")
            batch_op.drop_constraint("fk_env_publications_previous_version", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_env_publications_version_profile",
                "environment_versions",
                ["profile_id", "version_id"],
                ["profile_id", "id"],
                ondelete="RESTRICT",
            )
            batch_op.create_foreign_key(
                "fk_env_publications_previous_version_profile",
                "environment_versions",
                ["profile_id", "previous_version_id"],
                ["profile_id", "id"],
                ondelete="RESTRICT",
            )
    else:
        op.drop_constraint(
            "uq_env_version_image_tag",
            "environment_versions",
            type_="unique",
        )
        op.drop_constraint(
            "uq_env_version_image_digest",
            "environment_versions",
            type_="unique",
        )
        op.create_unique_constraint(
            "uq_env_version_profile_id", "environment_versions", ["profile_id", "id"]
        )
        op.drop_constraint(
            "fk_env_profiles_current_version", "environment_profiles", type_="foreignkey"
        )
        op.create_foreign_key(
            "fk_env_profiles_current_version_profile",
            "environment_profiles",
            "environment_versions",
            ["id", "current_version_id"],
            ["profile_id", "id"],
        )
        op.drop_constraint("fk_env_drafts_source_version", "environment_drafts", type_="foreignkey")
        op.drop_constraint("fk_env_drafts_candidate_version", "environment_drafts", type_="foreignkey")
        op.create_foreign_key(
            "fk_env_drafts_source_version_profile",
            "environment_drafts",
            "environment_versions",
            ["profile_id", "source_version_id"],
            ["profile_id", "id"],
        )
        op.create_foreign_key(
            "fk_env_drafts_candidate_version_profile",
            "environment_drafts",
            "environment_versions",
            ["profile_id", "candidate_version_id"],
            ["profile_id", "id"],
        )
        op.drop_constraint("fk_env_publications_version", "environment_publications", type_="foreignkey")
        op.drop_constraint(
            "fk_env_publications_previous_version", "environment_publications", type_="foreignkey"
        )
        op.create_foreign_key(
            "fk_env_publications_version_profile",
            "environment_publications",
            "environment_versions",
            ["profile_id", "version_id"],
            ["profile_id", "id"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            "fk_env_publications_previous_version_profile",
            "environment_publications",
            "environment_versions",
            ["profile_id", "previous_version_id"],
            ["profile_id", "id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    if os.getenv("DAI_ALLOW_ENVIRONMENT_V2_DOWNGRADE", "").lower() not in {"1", "true", "yes"}:
        raise RuntimeError(
            "Environment V2 downgrade is forward-only by default; set "
            "DAI_ALLOW_ENVIRONMENT_V2_DOWNGRADE=true only for a disposable, backed-up test database"
        )
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("environment_publications", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_env_publications_version_profile", type_="foreignkey")
            batch_op.drop_constraint("fk_env_publications_previous_version_profile", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_env_publications_version", "environment_versions", ["version_id"], ["id"]
            )
            batch_op.create_foreign_key(
                "fk_env_publications_previous_version", "environment_versions", ["previous_version_id"], ["id"]
            )
        with op.batch_alter_table("environment_drafts", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_env_drafts_source_version_profile", type_="foreignkey")
            batch_op.drop_constraint("fk_env_drafts_candidate_version_profile", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_env_drafts_source_version", "environment_versions", ["source_version_id"], ["id"]
            )
            batch_op.create_foreign_key(
                "fk_env_drafts_candidate_version", "environment_versions", ["candidate_version_id"], ["id"]
            )
        with op.batch_alter_table("environment_profiles", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_env_profiles_current_version_profile", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_env_profiles_current_version", "environment_versions", ["current_version_id"], ["id"]
            )
        with op.batch_alter_table("environment_versions", recreate="always") as batch_op:
            batch_op.create_unique_constraint("uq_env_version_image_tag", ["image_tag"])
            batch_op.create_unique_constraint(
                "uq_env_version_image_digest", ["image_digest"]
            )
            batch_op.drop_constraint("uq_env_version_profile_id", type_="unique")
            batch_op.drop_column("resolution_lock_sha256")
            batch_op.drop_column("resolution_lock")
    else:
        op.drop_constraint(
            "fk_env_publications_version_profile", "environment_publications", type_="foreignkey"
        )
        op.drop_constraint(
            "fk_env_publications_previous_version_profile", "environment_publications", type_="foreignkey"
        )
        op.create_foreign_key(
            "fk_env_publications_version", "environment_publications", "environment_versions",
            ["version_id"], ["id"], ondelete="RESTRICT"
        )
        op.create_foreign_key(
            "fk_env_publications_previous_version", "environment_publications", "environment_versions",
            ["previous_version_id"], ["id"], ondelete="RESTRICT"
        )
        op.drop_constraint("fk_env_drafts_source_version_profile", "environment_drafts", type_="foreignkey")
        op.drop_constraint("fk_env_drafts_candidate_version_profile", "environment_drafts", type_="foreignkey")
        op.create_foreign_key(
            "fk_env_drafts_source_version", "environment_drafts", "environment_versions",
            ["source_version_id"], ["id"]
        )
        op.create_foreign_key(
            "fk_env_drafts_candidate_version", "environment_drafts", "environment_versions",
            ["candidate_version_id"], ["id"]
        )
        op.drop_constraint("fk_env_profiles_current_version_profile", "environment_profiles", type_="foreignkey")
        op.create_foreign_key(
            "fk_env_profiles_current_version", "environment_profiles", "environment_versions",
            ["current_version_id"], ["id"]
        )
        op.drop_constraint("uq_env_version_profile_id", "environment_versions", type_="unique")
        op.create_unique_constraint(
            "uq_env_version_image_tag", "environment_versions", ["image_tag"]
        )
        op.create_unique_constraint(
            "uq_env_version_image_digest", "environment_versions", ["image_digest"]
        )
        op.drop_column("environment_versions", "resolution_lock_sha256")
        op.drop_column("environment_versions", "resolution_lock")
