"""Studio draft metadata/assets and experiment module ownership.

Revision ID: b2c3d4e5f607
Revises: a1b2c3d4e5f6
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f607"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add JSON nullable first so MySQL versions that reject JSON defaults can
    # upgrade existing rows. Backfill before tightening nullability.
    with op.batch_alter_table("notebook_templates") as batch_op:
        batch_op.add_column(sa.Column("draft_metadata", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("draft_assets_dir", sa.String(length=500), nullable=True)
        )
    op.execute(
        sa.text(
            "UPDATE notebook_templates "
            "SET draft_metadata = '{}' WHERE draft_metadata IS NULL"
        )
    )
    with op.batch_alter_table("notebook_templates") as batch_op:
        batch_op.alter_column(
            "draft_metadata", existing_type=sa.JSON(), nullable=False
        )

    with op.batch_alter_table("experiment_modules") as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_experiment_modules_owner", "users", ["owner_id"], ["id"]
        )
        batch_op.create_index(
            "ix_experiment_modules_owner_id", ["owner_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("experiment_modules") as batch_op:
        batch_op.drop_index("ix_experiment_modules_owner_id")
        batch_op.drop_constraint(
            "fk_experiment_modules_owner", type_="foreignkey"
        )
        batch_op.drop_column("owner_id")
    with op.batch_alter_table("notebook_templates") as batch_op:
        batch_op.drop_column("draft_assets_dir")
        batch_op.drop_column("draft_metadata")
