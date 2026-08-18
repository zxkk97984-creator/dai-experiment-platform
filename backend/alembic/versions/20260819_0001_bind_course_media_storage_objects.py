"""bind newly uploaded course media to storage object metadata

Revision ID: 20260819_0001
Revises: 20260818_0001
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_0001"
down_revision = "20260818_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bigint_fk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

    with op.batch_alter_table("courses") as batch_op:
        batch_op.add_column(sa.Column("cover_object_id", bigint_fk, nullable=True))
        batch_op.create_index("ix_courses_cover_object_id", ["cover_object_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_courses_cover_object_id_storage_objects",
            "storage_objects",
            ["cover_object_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("lessons") as batch_op:
        batch_op.add_column(sa.Column("video_object_id", bigint_fk, nullable=True))
        batch_op.create_index("ix_lessons_video_object_id", ["video_object_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_lessons_video_object_id_storage_objects",
            "storage_objects",
            ["video_object_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.drop_constraint(
            "fk_lessons_video_object_id_storage_objects", type_="foreignkey"
        )
        batch_op.drop_index("ix_lessons_video_object_id")
        batch_op.drop_column("video_object_id")

    with op.batch_alter_table("courses") as batch_op:
        batch_op.drop_constraint(
            "fk_courses_cover_object_id_storage_objects", type_="foreignkey"
        )
        batch_op.drop_index("ix_courses_cover_object_id")
        batch_op.drop_column("cover_object_id")
