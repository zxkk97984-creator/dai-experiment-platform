"""add academic terms, teaching classes, student numbers and roster origins

Revision ID: e7f8a9b0c123
Revises: d6e7f8a9b012
Create Date: 2026-08-11 19:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c123"
down_revision = "d6e7f8a9b012"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "academic_terms",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="planned", nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_academic_terms_code"),
    )
    op.create_index("ix_academic_terms_status", "academic_terms", ["status"])

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("student_no", sa.String(80), nullable=True))
        batch_op.create_index("ix_users_student_no", ["student_no"], unique=True)
    op.execute("UPDATE users SET student_no = username WHERE role = 'student' AND student_no IS NULL")

    with op.batch_alter_table("courses") as batch_op:
        batch_op.add_column(sa.Column("academic_term_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_courses_academic_term_id", ["academic_term_id"])
        batch_op.create_foreign_key("fk_courses_academic_term", "academic_terms", ["academic_term_id"], ["id"])

    with op.batch_alter_table("course_enrollments") as batch_op:
        batch_op.add_column(sa.Column("origin", sa.String(20), server_default="manual", nullable=False))
        batch_op.create_index("ix_course_enrollments_origin", ["origin"])

    op.create_table(
        "teaching_classes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("academic_term_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["academic_term_id"], ["academic_terms.id"], name="fk_teaching_classes_term"),
        sa.UniqueConstraint("academic_term_id", "code", name="uq_teaching_class_term_code"),
    )
    op.create_index("ix_teaching_classes_academic_term_id", "teaching_classes", ["academic_term_id"])
    op.create_index("ix_teaching_classes_code", "teaching_classes", ["code"])
    op.create_index("ix_teaching_classes_status", "teaching_classes", ["status"])

    op.create_table(
        "teaching_class_students",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("teaching_class_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["teaching_class_id"], ["teaching_classes.id"], name="fk_class_students_class", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], name="fk_class_students_student", ondelete="CASCADE"),
        sa.UniqueConstraint("teaching_class_id", "student_id", name="uq_teaching_class_student"),
    )
    op.create_index("ix_class_students_class", "teaching_class_students", ["teaching_class_id"])
    op.create_index("ix_class_students_student", "teaching_class_students", ["student_id"])
    op.create_index("ix_class_students_status", "teaching_class_students", ["status"])

    op.create_table(
        "course_teaching_classes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("teaching_class_id", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name="fk_course_classes_course", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teaching_class_id"], ["teaching_classes.id"], name="fk_course_classes_class", ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "teaching_class_id", name="uq_course_teaching_class"),
    )
    op.create_index("ix_course_classes_course", "course_teaching_classes", ["course_id"])
    op.create_index("ix_course_classes_class", "course_teaching_classes", ["teaching_class_id"])


def downgrade() -> None:
    op.drop_table("course_teaching_classes")
    op.drop_table("teaching_class_students")
    op.drop_table("teaching_classes")
    with op.batch_alter_table("course_enrollments") as batch_op:
        batch_op.drop_index("ix_course_enrollments_origin")
        batch_op.drop_column("origin")
    with op.batch_alter_table("courses", recreate="always" if op.get_bind().dialect.name == "sqlite" else "auto") as batch_op:
        if op.get_bind().dialect.name != "sqlite":
            batch_op.drop_constraint("fk_courses_academic_term", type_="foreignkey")
        batch_op.drop_index("ix_courses_academic_term_id")
        batch_op.drop_column("academic_term_id")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_student_no")
        batch_op.drop_column("student_no")
    op.drop_table("academic_terms")
