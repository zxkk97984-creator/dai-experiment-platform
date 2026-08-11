"""use teaching-class visibility as the default course scope

Revision ID: 20260811_0002
Revises: e7f8a9b0c123
Create Date: 2026-08-11 22:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_0002"
down_revision = "e7f8a9b0c123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 旧 public 表示课程可被学生发现；新模型用 class 表示“绑定教学班可见”。
    op.execute("UPDATE courses SET visibility = 'class' WHERE visibility = 'public'")
    with op.batch_alter_table("courses") as batch_op:
        batch_op.alter_column(
            "visibility",
            existing_type=sa.String(length=20),
            server_default=sa.text("'class'"),
            existing_nullable=False,
        )


def downgrade() -> None:
    op.execute("UPDATE courses SET visibility = 'public' WHERE visibility = 'class'")
    with op.batch_alter_table("courses") as batch_op:
        batch_op.alter_column(
            "visibility",
            existing_type=sa.String(length=20),
            server_default=sa.text("'private'"),
            existing_nullable=False,
        )
