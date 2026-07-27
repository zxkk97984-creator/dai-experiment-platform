"""实验提交评分反馈：增加 score/feedback/reviewed_by_id/reviewed_at。

Revision ID: f6a7b8c9d011
Revises: e5f6a7b8c910
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d011"
down_revision: Union[str, None] = "e5f6a7b8c910"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("experiment_submissions") as batch_op:
        batch_op.add_column(sa.Column("score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("feedback", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reviewed_by_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_experiment_submissions_reviewed_by",
            "users", ["reviewed_by_id"], ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("experiment_submissions") as batch_op:
        batch_op.drop_constraint("fk_experiment_submissions_reviewed_by", type_="foreignkey")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("reviewed_by_id")
        batch_op.drop_column("feedback")
        batch_op.drop_column("score")
