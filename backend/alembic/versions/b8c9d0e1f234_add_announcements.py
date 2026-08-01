"""add announcements and read receipts

Revision ID: b8c9d0e1f234
Revises: a7b8c9d0e112
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa


revision = "b8c9d0e1f234"
down_revision = "a7b8c9d0e112"
branch_labels = None
depends_on = None


def _is_offline_mode() -> bool:
    """离线 SQL 生成没有可检查的数据库，保持 Alembic 的普通 DDL 输出。"""
    try:
        return bool(op.get_context().as_sql)
    except AttributeError:
        return False


def _create_table_if_missing(table_name: str, *columns_and_constraints) -> None:
    if not _is_offline_mode():
        existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
        if table_name in existing_tables:
            return
    op.create_table(table_name, *columns_and_constraints)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if not _is_offline_mode():
        existing_indexes = {
            index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)
        }
        if index_name in existing_indexes:
            return
    op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    # ── 公告表 ──
    _create_table_if_missing(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── 已读回执表 ──
    _create_table_if_missing(
        "announcement_reads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("announcement_id", sa.Integer(), sa.ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("announcement_id", "user_id", name="uq_announcement_read_user"),
    )

    # ── 索引 ──
    _create_index_if_missing("ix_announcements_priority", "announcements", ["priority"])
    _create_index_if_missing("ix_announcements_scope", "announcements", ["scope"])
    _create_index_if_missing("ix_announcements_course_id", "announcements", ["course_id"])
    _create_index_if_missing("ix_announcements_author_id", "announcements", ["author_id"])
    _create_index_if_missing("ix_announcement_reads_announcement_id", "announcement_reads", ["announcement_id"])
    _create_index_if_missing("ix_announcement_reads_user_id", "announcement_reads", ["user_id"])


def downgrade() -> None:
    # 逆序删除：先删依赖表
    op.drop_table("announcement_reads")
    op.drop_table("announcements")
