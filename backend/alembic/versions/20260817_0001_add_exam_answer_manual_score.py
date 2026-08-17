"""add manual score reason to exam answers

Revision ID: 20260817_0001
Revises: 936ca2d19666
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260817_0001"
down_revision = "936ca2d19666"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("exam_answers", sa.Column("manual_score_reason", sa.Text(), nullable=True))
    op.add_column("exam_answers", sa.Column("manual_score_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("exam_answers", "manual_score_at")
    op.drop_column("exam_answers", "manual_score_reason")
