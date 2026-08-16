"""通知持久化与用户偏好

Revision ID: 20260816_0001
Revises: 13697fb5ecbf
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from alembic import op

revision = "20260816_0001"
down_revision = "13697fb5ecbf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.String(length=500), nullable=False),
        sa.Column("entity_kind", sa.String(length=30), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("route", sa.String(length=255), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("dedupe_key", sa.String(length=180), nullable=False),
        sa.Column("visible", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipient_id", "dedupe_key", name="uq_notification_recipient_dedupe"),
    )
    op.create_index("ix_notifications_recipient_visible", "notifications", ["recipient_id", "visible"], unique=False)
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"], unique=False)
    op.create_index("ix_notifications_type", "notifications", ["type"], unique=False)
    op.create_index("ix_notifications_priority", "notifications", ["priority"], unique=False)

    op.create_table(
        "notification_reads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("notification_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_id", "user_id", name="uq_notification_read_user"),
    )
    op.create_index("ix_notification_reads_notification_id", "notification_reads", ["notification_id"], unique=False)
    op.create_index("ix_notification_reads_user_id", "notification_reads", ["user_id"], unique=False)

    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_index("ix_notification_reads_user_id", table_name="notification_reads")
    op.drop_index("ix_notification_reads_notification_id", table_name="notification_reads")
    op.drop_table("notification_reads")
    op.drop_index("ix_notifications_priority", table_name="notifications")
    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_index("ix_notifications_recipient_id", table_name="notifications")
    op.drop_index("ix_notifications_recipient_visible", table_name="notifications")
    op.drop_table("notifications")
