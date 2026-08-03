"""add lesson publish status

Revision ID: d0e1f2a3b456
Revises: c9d0e1f2a345
Create Date: 2026-08-03 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d0e1f2a3b456"
down_revision = "c9d0e1f2a345"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 课时发布状态：存量数据视为已发布，新建课时由应用层默认草稿
    op.add_column(
        "lessons",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="published"),
    )


def downgrade() -> None:
    op.drop_column("lessons", "status")
