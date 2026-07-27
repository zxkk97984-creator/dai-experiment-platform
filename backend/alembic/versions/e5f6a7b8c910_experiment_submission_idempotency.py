"""实验提交幂等：增加 client_request_id 字段和唯一约束。

Revision ID: e5f6a7b8c910
Revises: d4e5f6a7b809
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c910"
down_revision: Union[str, None] = "d4e5f6a7b809"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("experiment_submissions") as batch_op:
        batch_op.add_column(
            sa.Column("client_request_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_index(
            "ix_experiment_submissions_client_request_id",
            ["client_request_id"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "uq_experiment_submission_idempotency",
            ["record_id", "client_request_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("experiment_submissions") as batch_op:
        batch_op.drop_constraint("uq_experiment_submission_idempotency", type_="unique")
        batch_op.drop_index("ix_experiment_submissions_client_request_id")
        batch_op.drop_column("client_request_id")
