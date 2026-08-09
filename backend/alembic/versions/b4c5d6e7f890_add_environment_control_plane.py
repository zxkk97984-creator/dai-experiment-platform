"""add environment control plane

环境档位控制面（Phase 1：迁移 A）——五张控制面表：

- package_catalog：受控包目录（供应链输入唯一事实源）
- environment_profiles：环境档位（basic / data / torch-cpu）
- environment_versions：不可变环境版本（构建后冻结 digest）
- profile_version_packages：版本 × 包 关联（包必须关联版本，历史版本不受新版本影响）
- environment_build_jobs：构建任务状态机（queued/building/succeeded/failed/timed_out）

注意：
- 本迁移只建控制面数据表，不执行任何 Docker 构建。
- created_by_id / updated_by_id 引用 users.id（INTEGER），MySQL 外键要求两侧
  类型一致，故使用 Integer 而非 BigInteger。
- 降级仅删除控制面表，不删除任何 Docker 镜像或审计数据。

Revision ID: b4c5d6e7f890
Revises: a3b4c5d6e789
Create Date: 2026-08-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b4c5d6e7f890"
down_revision = "a3b4c5d6e789"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 包目录 ────────────────────────────────────────────────
    op.create_table(
        "package_catalog",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("normalized_name", sa.String(length=128), nullable=False),
        sa.Column("pip_name", sa.String(length=128), nullable=False),
        sa.Column("locked_version", sa.String(length=64), nullable=False),
        sa.Column("import_names", sa.JSON(), nullable=False),
        sa.Column("category_tags", sa.JSON(), nullable=False),
        sa.Column("source_key", sa.String(length=32), nullable=False),  # pypi | pytorch_cpu
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),  # active | inactive
        sa.Column("supersedes_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["supersedes_id"], ["package_catalog.id"], name="fk_pkg_catalog_supersedes"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_pkg_catalog_created_by"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_pkg_catalog_updated_by"),
        sa.PrimaryKeyConstraint("id", name="pk_package_catalog"),
        sa.UniqueConstraint(
            "normalized_name", "locked_version", "source_key", name="uq_pkg_name_version_source"
        ),
    )

    # ── 环境档位 ──────────────────────────────────────────────
    op.create_table(
        "environment_profiles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),  # active | inactive
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_env_profiles_created_by"),
        sa.PrimaryKeyConstraint("id", name="pk_environment_profiles"),
        sa.UniqueConstraint("slug", name="uq_env_profile_slug"),
    )

    # ── 环境版本（不可变） ────────────────────────────────────
    op.create_table(
        "environment_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_version_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        # draft | queued | building | available | failed | inactive
        sa.Column("base_image_ref", sa.String(length=255), nullable=False),
        sa.Column("image_tag", sa.String(length=255), nullable=True),
        sa.Column("image_digest", sa.String(length=255), nullable=True),
        sa.Column("python_version", sa.String(length=32), nullable=True),
        sa.Column("minimum_memory_mb", sa.Integer(), nullable=False),
        sa.Column("manifest_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("dockerfile_sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("resolved_packages", sa.JSON(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["environment_profiles.id"], name="fk_env_versions_profile"
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"], ["environment_versions.id"], name="fk_env_versions_source"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_env_versions_created_by"),
        sa.PrimaryKeyConstraint("id", name="pk_environment_versions"),
        sa.UniqueConstraint("profile_id", "version_number", name="uq_env_version_per_profile"),
        sa.UniqueConstraint("image_tag", name="uq_env_version_image_tag"),
        sa.UniqueConstraint("image_digest", name="uq_env_version_image_digest"),
    )
    op.create_index("ix_env_versions_profile_id", "environment_versions", ["profile_id"])
    op.create_index("ix_env_versions_status", "environment_versions", ["status"])

    # ── 版本 × 包 关联（复合主键） ────────────────────────────
    op.create_table(
        "profile_version_packages",
        sa.Column("environment_version_id", sa.BigInteger(), nullable=False),
        sa.Column("package_catalog_id", sa.BigInteger(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["environment_version_id"], ["environment_versions.id"],
            name="fk_pvp_environment_version",
        ),
        sa.ForeignKeyConstraint(
            ["package_catalog_id"], ["package_catalog.id"], name="fk_pvp_package_catalog"
        ),
        sa.PrimaryKeyConstraint(
            "environment_version_id", "package_catalog_id", name="pk_profile_version_packages"
        ),
    )

    # ── 构建任务 ──────────────────────────────────────────────
    op.create_table(
        "environment_build_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("environment_version_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        # queued | building | succeeded | failed | timed_out
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("retry_of_id", sa.BigInteger(), nullable=True),
        sa.Column("worker_id", sa.String(length=160), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("log_text", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["environment_version_id"], ["environment_versions.id"],
            name="fk_env_build_jobs_version",
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_id"], ["environment_build_jobs.id"], name="fk_env_build_jobs_retry_of"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_env_build_jobs_created_by"),
        sa.PrimaryKeyConstraint("id", name="pk_environment_build_jobs"),
    )
    op.create_index(
        "ix_env_build_jobs_status_created", "environment_build_jobs", ["status", "created_at"]
    )
    op.create_index(
        "ix_env_build_jobs_version_id", "environment_build_jobs", ["environment_version_id"]
    )


def downgrade() -> None:
    # 逆序删除：先子表后父表；不删除 Docker 镜像或任何审计数据
    op.drop_index("ix_env_build_jobs_version_id", table_name="environment_build_jobs")
    op.drop_index("ix_env_build_jobs_status_created", table_name="environment_build_jobs")
    op.drop_table("environment_build_jobs")
    op.drop_table("profile_version_packages")
    op.drop_index("ix_env_versions_status", table_name="environment_versions")
    op.drop_index("ix_env_versions_profile_id", table_name="environment_versions")
    op.drop_table("environment_versions")
    op.drop_table("environment_profiles")
    op.drop_table("package_catalog")
