"""TASK-018：新增 lesson_progress（服务端学习进度）

- 唯一键 (lesson_id, student_id)；状态仅 in_progress/completed
- 打开课时记录 in_progress + last_accessed_at；完成显式操作；可撤回
- 依赖 TASK-012 迁移链；不与其他功能迁移并行
"""
import sqlalchemy as sa
from alembic import op

revision = "20260813_0003"
down_revision = "20260813_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lesson_id",
            sa.Integer(),
            sa.ForeignKey("lessons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column(
            "last_accessed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("lesson_id", "student_id", name="uq_lesson_progress_lesson_student"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_lesson_progress_lesson_id", "lesson_progress", ["lesson_id"])
    op.create_index("ix_lesson_progress_student_id", "lesson_progress", ["student_id"])
    op.create_index("ix_lesson_progress_student_status", "lesson_progress", ["student_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_lesson_progress_student_status", table_name="lesson_progress")
    op.drop_index("ix_lesson_progress_student_id", table_name="lesson_progress")
    op.drop_index("ix_lesson_progress_lesson_id", table_name="lesson_progress")
    op.drop_table("lesson_progress")
