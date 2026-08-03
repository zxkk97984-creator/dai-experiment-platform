"""exam submission review_required 终态 + scheduler leases

Revision ID: c9d0e1f2a345
Revises: b8c9d0e1f234
Create Date: 2026-08-02
"""

from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a345"
down_revision = "b8c9d0e1f234"
branch_labels = None
depends_on = None

_OLD_CHECK = "status IN ('started', 'submitted', 'grading', 'graded')"
_NEW_CHECK = "status IN ('started', 'submitted', 'grading', 'graded', 'review_required')"


def _is_offline_mode() -> bool:
    try:
        return bool(op.get_context().as_sql)
    except AttributeError:
        return False


def _has_constraint(table: str, constraint_name: str) -> bool:
    if _is_offline_mode():
        return True
    insp = sa.inspect(op.get_bind())
    return any(c["name"] == constraint_name for c in insp.get_check_constraints(table))


def _has_column(table: str, column_name: str) -> bool:
    if _is_offline_mode():
        return False
    insp = sa.inspect(op.get_bind())
    return column_name in {c["name"] for c in insp.get_columns(table)}


def _create_table_if_missing(table_name: str, *columns_and_constraints) -> None:
    if not _is_offline_mode():
        existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
        if table_name in existing_tables:
            return
    op.create_table(table_name, *columns_and_constraints)


def upgrade() -> None:
    # ── exam_submissions：新增终态与脱敏原因 ────────────────────
    with op.batch_alter_table("exam_submissions") as batch_op:
        if not _has_column("exam_submissions", "review_reason"):
            batch_op.add_column(sa.Column("review_reason", sa.Text(), nullable=True))
        if not _has_column("exam_submissions", "review_required_at"):
            batch_op.add_column(sa.Column("review_required_at", sa.DateTime(timezone=True), nullable=True))
        if _has_constraint("exam_submissions", "ck_exam_submission_status"):
            batch_op.drop_constraint("ck_exam_submission_status", type_="check")
        batch_op.create_check_constraint("ck_exam_submission_status", _NEW_CHECK)

    # ── scheduler_leases：多实例任务租约表 ─────────────────────
    _create_table_if_missing(
        "scheduler_leases",
        sa.Column("task_name", sa.String(length=80), primary_key=True),
        sa.Column("owner_id", sa.String(length=120), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("scheduler_leases")

    with op.batch_alter_table("exam_submissions") as batch_op:
        if _has_constraint("exam_submissions", "ck_exam_submission_status"):
            batch_op.drop_constraint("ck_exam_submission_status", type_="check")
        batch_op.create_check_constraint("ck_exam_submission_status", _OLD_CHECK)
        if _has_column("exam_submissions", "review_required_at"):
            batch_op.drop_column("review_required_at")
        if _has_column("exam_submissions", "review_reason"):
            batch_op.drop_column("review_reason")
