"""add course whitelist table

Revision ID: f2a3b4c5d678
Revises: e1f2a3b4c567
Create Date: 2026-08-04 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f2a3b4c5d678"
down_revision = "e1f2a3b4c567"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 课程白名单关联表——外键与唯一约束随 CREATE TABLE 内联声明，
    # 保证 MySQL / SQLite 均可用且带命名与级联语义。
    op.create_table(
        "course_whitelist_students",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name="fk_course_whitelist_course", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], name="fk_course_whitelist_student", ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "student_id", name="uq_course_whitelist_student"),
    )
    # 反向复合索引：学生课程列表中的相关子查询
    op.create_index(
        "ix_course_whitelist_students_student_course",
        "course_whitelist_students",
        ["student_id", "course_id"],
    )
    # 不修改任何现有 courses.visibility，也不从 course_enrollments 回填白名单


def downgrade() -> None:
    # 旧版后端无法编辑 public/whitelist 课程，降级时归一化为 private
    op.execute(
        "UPDATE courses SET visibility = 'private' "
        "WHERE visibility IN ('public', 'whitelist')"
    )
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        # MySQL InnoDB：外键列依赖反向复合索引，必须先删外键约束才能删索引
        op.drop_constraint("fk_course_whitelist_course", "course_whitelist_students", type_="foreignkey")
        op.drop_constraint("fk_course_whitelist_student", "course_whitelist_students", type_="foreignkey")
    op.drop_index("ix_course_whitelist_students_student_course", table_name="course_whitelist_students")
    op.drop_table("course_whitelist_students")
