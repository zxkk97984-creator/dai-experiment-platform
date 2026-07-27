"""为 Submission 和 ExamAnswer 增加判题队列状态机字段。

Revision ID: c3d4e5f6a708
Revises: b2c3d4e5f607
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a708"
down_revision: Union[str, None] = "b2c3d4e5f607"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── submissions 表 ──────────────────────────────────────────
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.add_column(
            sa.Column("grading_status", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("attempt_count", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_error", sa.Text(), nullable=True)
        )

    # 为历史数据补默认值：已有 status 映射到 grading_status
    op.execute(
        sa.text(
            "UPDATE submissions SET grading_status = "
            "CASE "
            "  WHEN status = 'queued' THEN 'queued' "
            "  WHEN status = 'running' THEN 'running' "
            "  WHEN status IN ('accepted', 'wrong_answer', 'runtime_error', 'time_limit_exceeded') THEN 'completed' "
            "  WHEN status = 'system_error' THEN 'system_error' "
            "  ELSE 'pending' "
            "END "
            "WHERE grading_status IS NULL"
        )
    )
    op.execute(sa.text("UPDATE submissions SET attempt_count = 0 WHERE attempt_count IS NULL"))

    with op.batch_alter_table("submissions") as batch_op:
        batch_op.alter_column("grading_status", existing_type=sa.String(20), nullable=False)
        batch_op.alter_column("attempt_count", existing_type=sa.Integer(), nullable=False)

    # 索引：(grading_status, updated_at) 用于恢复扫描
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.create_index(
            "ix_submissions_gs_updated",
            ["grading_status", "updated_at"],
            unique=False,
        )

    # ── exam_answers 表 ─────────────────────────────────────────
    with op.batch_alter_table("exam_answers") as batch_op:
        batch_op.add_column(
            sa.Column("attempt_count", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_error", sa.Text(), nullable=True)
        )

    # 为历史数据补默认值
    op.execute(
        sa.text(
            "UPDATE exam_answers SET attempt_count = 0 WHERE attempt_count IS NULL"
        )
    )

    with op.batch_alter_table("exam_answers") as batch_op:
        batch_op.alter_column("attempt_count", existing_type=sa.Integer(), nullable=False)

    # grading_status 已有，补索引
    with op.batch_alter_table("exam_answers") as batch_op:
        batch_op.create_index(
            "ix_exam_answers_gs_updated",
            ["grading_status", "updated_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("exam_answers") as batch_op:
        batch_op.drop_index("ix_exam_answers_gs_updated")
        batch_op.drop_column("last_error")
        batch_op.drop_column("finished_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("queued_at")
        batch_op.drop_column("attempt_count")

    with op.batch_alter_table("submissions") as batch_op:
        batch_op.drop_index("ix_submissions_gs_updated")
        batch_op.drop_column("last_error")
        batch_op.drop_column("finished_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("queued_at")
        batch_op.drop_column("attempt_count")
        batch_op.drop_column("grading_status")
