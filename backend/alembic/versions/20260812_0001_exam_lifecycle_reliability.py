"""exam lifecycle, review visibility, autosave versions, and fill blanks

Revision ID: 20260812_0001
Revises: 20260811_0002
Create Date: 2026-08-12 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260812_0001"
down_revision = "20260811_0002"
branch_labels = None
depends_on = None

_OLD_QUESTION_CHECK = "question_type IN ('single_choice', 'multi_choice', 'code')"
_NEW_QUESTION_CHECK = "question_type IN ('single_choice', 'multi_choice', 'fill_blank', 'code')"


def upgrade() -> None:
    with op.batch_alter_table("exams") as batch_op:
        batch_op.add_column(sa.Column("show_score_after_grading", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("show_questions_after_review", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("show_answers_after_review", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("review_released_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("review_released_by_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_exams_review_released_by", "users", ["review_released_by_id"], ["id"])

    with op.batch_alter_table("exam_submissions") as batch_op:
        batch_op.add_column(sa.Column("last_saved_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("submission_reason", sa.String(length=30), nullable=True))
        batch_op.create_index("ix_exam_submissions_status_expires", ["status", "expires_at"], unique=False)

    with op.batch_alter_table("exam_answers") as batch_op:
        batch_op.add_column(sa.Column("text_answers", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")))

    with op.batch_alter_table("exam_questions") as batch_op:
        batch_op.drop_constraint("ck_exam_question_type", type_="check")
        batch_op.create_check_constraint("ck_exam_question_type", _NEW_QUESTION_CHECK)


def downgrade() -> None:
    with op.batch_alter_table("exam_questions") as batch_op:
        batch_op.drop_constraint("ck_exam_question_type", type_="check")
        batch_op.create_check_constraint("ck_exam_question_type", _OLD_QUESTION_CHECK)

    with op.batch_alter_table("exam_answers") as batch_op:
        batch_op.drop_column("version")
        batch_op.drop_column("text_answers")

    with op.batch_alter_table("exam_submissions") as batch_op:
        batch_op.drop_index("ix_exam_submissions_status_expires")
        batch_op.drop_column("submission_reason")
        batch_op.drop_column("last_saved_at")

    with op.batch_alter_table("exams") as batch_op:
        batch_op.drop_constraint("fk_exams_review_released_by", type_="foreignkey")
        batch_op.drop_column("review_released_by_id")
        batch_op.drop_column("review_released_at")
        batch_op.drop_column("show_answers_after_review")
        batch_op.drop_column("show_questions_after_review")
        batch_op.drop_column("show_score_after_grading")
