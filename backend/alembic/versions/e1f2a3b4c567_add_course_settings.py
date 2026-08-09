"""add course settings fields

Revision ID: e1f2a3b4c567
Revises: d0e1f2a3b456
Create Date: 2026-08-04 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e1f2a3b4c567"
down_revision = "d0e1f2a3b456"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 课程设置：封面 / 开课时间 / 可见范围 / 默认评分
    # 存量课程可见范围视为 private（仅自己可见）、默认满分 100
    op.add_column("courses", sa.Column("cover", sa.String(length=500), nullable=True))
    op.add_column("courses", sa.Column("start_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "courses",
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default="private"),
    )
    op.add_column(
        "courses",
        sa.Column("default_score", sa.Float(), nullable=False, server_default="100"),
    )


def downgrade() -> None:
    op.drop_column("courses", "default_score")
    op.drop_column("courses", "visibility")
    op.drop_column("courses", "start_time")
    op.drop_column("courses", "cover")
