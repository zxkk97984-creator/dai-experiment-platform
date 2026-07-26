"""v5 unified models: NotebookTemplate + Version, unified ExperimentRecord, ExamQuestion + ExamAnswer

Revision ID: a1b2c3d4e5f6
Revises: f81a7a35f73f
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f81a7a35f73f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 删除旧表 ──────────────────────────────────────────────
    op.execute("DROP TABLE IF EXISTS notebook_submissions")
    op.execute("DROP TABLE IF EXISTS notebook_records")

    # ── 新建 notebook_templates ──────────────────────────────
    op.create_table(
        "notebook_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("current_version_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("draft_cells", sa.JSON(), nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 新建 notebook_template_versions ──────────────────────
    op.create_table(
        "notebook_template_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("notebook_templates.id"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("cells", sa.JSON(), nullable=False),
        sa.Column("cell_order", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("assets_dir", sa.String(500), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("template_id", "version_number", name="uq_version_number_per_template"),
    )

    # ── 修改 lessons 表（SQLite batch 模式）──────────────────
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_lessons_template", "notebook_templates", ["template_id"], ["id"]
        )

    # ── 修改 experiment_modules 表 ───────────────────────────
    with op.batch_alter_table("experiment_modules") as batch_op:
        batch_op.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_experiment_modules_template", "notebook_templates", ["template_id"], ["id"]
        )

    # ── 重建 experiment_records（drop + create）───────────────
    op.execute("DROP TABLE IF EXISTS experiment_records")
    op.create_table(
        "experiment_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id"), nullable=True, index=True),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("experiment_modules.id"), nullable=True, index=True),
        sa.Column("template_version_id", sa.Integer(), sa.ForeignKey("notebook_template_versions.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="started"),
        sa.Column("cells_sources", sa.JSON(), nullable=False),
        sa.Column("cells_outputs", sa.JSON(), nullable=False),
        sa.Column("record_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("lesson_id", "student_id", name="uq_record_lesson_student"),
        sa.UniqueConstraint("module_id", "student_id", name="uq_record_module_student"),
        sa.CheckConstraint(
            "(lesson_id IS NULL) != (module_id IS NULL)",
            name="ck_record_entry_type",
        ),
    )

    # ── 新建 experiment_submissions ───────────────────────────
    op.create_table(
        "experiment_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("experiment_records.id"), nullable=False, index=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("cells_snapshot", sa.JSON(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("record_id", "attempt_number", name="uq_experiment_submission_attempt"),
    )

    # ── 补 FK: notebook_templates.current_version_id → notebook_template_versions.id ──
    # 循环依赖（Version 也引用 Template），batch 模式兼容 SQLite
    with op.batch_alter_table("notebook_templates") as batch_op:
        batch_op.create_foreign_key(
            "fk_template_current_version",
            "notebook_template_versions",
            ["current_version_id"], ["id"],
        )

    # ── 修改 exam_submissions（SQLite batch 模式）─────────────
    with op.batch_alter_table("exam_submissions") as batch_op:
        batch_op.drop_column("answers")
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_check_constraint(
            "ck_exam_submission_status",
            "status IN ('started', 'submitted', 'grading', 'graded')",
        )
    # 新的 CHECK 约束（先删除旧的如果有的话，SQLite 不支持 ALTER CHECK）
    # 实际部署时 SQLite 需要重建表；MySQL/PostgreSQL 可以直接添加

    # ── 新建 exam_questions ───────────────────────────────────
    op.create_table(
        "exam_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False, index=True),
        sa.Column("question_type", sa.String(20), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("correct_answer", sa.JSON(), nullable=False),
        sa.Column("points", sa.Float(), nullable=False, server_default="0"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starter_code", sa.Text(), nullable=True),
        sa.Column("public_cases", sa.JSON(), nullable=True),
        sa.Column("hidden_tests", sa.Text(), nullable=True),
        sa.Column("time_limit_ms", sa.Integer(), nullable=True),
        sa.Column("memory_limit_mb", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # CHECK 约束（SQLite batch 模式）
    with op.batch_alter_table("exam_questions") as batch_op:
        batch_op.create_check_constraint(
            "ck_exam_question_type",
            "question_type IN ('single_choice', 'multi_choice', 'code')",
        )

    # ── 新建 exam_answers ─────────────────────────────────────
    op.create_table(
        "exam_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("exam_submissions.id"), nullable=False, index=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("exam_questions.id"), nullable=False, index=True),
        sa.Column("selected_options", sa.JSON(), nullable=True),
        sa.Column("code_answer", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("grading_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result_details", sa.JSON(), nullable=True),
        sa.Column("system_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("submission_id", "question_id", name="uq_exam_answer_q"),
    )


def downgrade() -> None:
    # 先删除循环 FK（否则 notebook_template_versions 无法 drop）
    with op.batch_alter_table("notebook_templates") as batch_op:
        batch_op.drop_constraint("fk_template_current_version", type_="foreignkey")
    # 删除本迁移新增的 exam_submission CHECK 约束
    with op.batch_alter_table("exam_submissions") as batch_op:
        batch_op.drop_constraint("ck_exam_submission_status", type_="check")
    op.drop_table("exam_answers")
    op.drop_table("exam_questions")
    with op.batch_alter_table("exam_submissions") as batch_op:
        batch_op.drop_column("graded_at")
        batch_op.drop_column("expires_at")
        batch_op.add_column(sa.Column("answers", sa.JSON(), nullable=True))
    op.drop_table("experiment_submissions")
    op.drop_table("experiment_records")
    # 重建旧 experiment_records（初始迁移 downgrade 需要它存在）
    op.create_table(
        "experiment_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("experiment_modules.id"), index=True, nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), index=True, nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="started"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    with op.batch_alter_table("experiment_modules") as batch_op:
        batch_op.drop_column("template_id")
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.drop_column("template_id")
    op.drop_table("notebook_template_versions")
    op.drop_table("notebook_templates")
    # 重建旧表（不恢复数据）
    op.create_table(
        "notebook_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id"), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="started"),
        sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("template_hash", sa.String(64), nullable=True),
        sa.Column("cells_sources", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("cells_outputs", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("cell_order", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("lesson_id", "student_id", name="uq_notebook_lesson_student"),
    )
    op.create_table(
        "notebook_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("notebook_records.id"), nullable=False, index=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("cells_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("artifacts_dir", sa.String(255), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("record_id", "attempt_number", name="uq_notebook_submission_attempt"),
    )
