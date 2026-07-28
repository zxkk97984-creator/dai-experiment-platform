"""add immutable experiment output snapshots

Revision ID: 07b4d9e18a22
Revises: f6a7b8c9d011
"""

from alembic import op
import sqlalchemy as sa


revision = "07b4d9e18a22"
down_revision = "f6a7b8c9d011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable preserves compatibility with submissions created before this migration.
    op.add_column(
        "experiment_submissions",
        sa.Column("outputs_snapshot", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("experiment_submissions", "outputs_snapshot")
