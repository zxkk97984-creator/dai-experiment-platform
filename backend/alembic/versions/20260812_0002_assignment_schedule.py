"""add assignment first-published timestamp

Revision ID: 20260812_0002
Revises: 20260812_0001
Create Date: 2026-08-12 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260812_0002"
down_revision = "20260812_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))

    # 历史库没有发布事件，按产品确认使用创建时间估算当前已发布作业的首次发布时间。
    op.execute(
        sa.text(
            "UPDATE assignments "
            "SET published_at = created_at "
            "WHERE status = 'published' AND published_at IS NULL"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.drop_column("published_at")
