"""add AI code grading models and configuration columns

Revision ID: a7b8c9d0e112
Revises: 07b4d9e18a22
Create Date: 2026-07-29
"""

from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e112"
down_revision = "07b4d9e18a22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 作业题目 AI 评分字段 ──
    for col in [
        sa.Column("grading_mode", sa.String(length=20), nullable=False, server_default="legacy"),
        sa.Column("teacher_constraints", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("reference_solution", sa.Text(), nullable=True),
        sa.Column("test_groups", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("score_cap_rules", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    ]:
        op.add_column("judge_questions", col)

    # ── 考试题目 AI 评分字段 ──
    for col in [
        sa.Column("grading_mode", sa.String(length=20), nullable=False, server_default="legacy"),
        sa.Column("teacher_constraints", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("reference_solution", sa.Text(), nullable=True),
        sa.Column("test_groups", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("score_cap_rules", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    ]:
        op.add_column("exam_questions", col)

    # ── Rubric 版本表 ──
    op.create_table(
        "question_rubrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("judge_question_id", sa.Integer(), sa.ForeignKey("judge_questions.id"), nullable=True, index=True),
        sa.Column("exam_question_id", sa.Integer(), sa.ForeignKey("exam_questions.id"), nullable=True, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft", index=True),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("source_snapshot", sa.JSON(), nullable=False),
        sa.Column("rubric_json", sa.JSON(), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        # XOR: exactly one of judge_question_id / exam_question_id must be non-null
        sa.CheckConstraint(
            "(judge_question_id IS NULL) != (exam_question_id IS NULL)",
            name="ck_rubric_xor_target",
        ),
        sa.UniqueConstraint("judge_question_id", "version", name="uq_rubric_judge_version"),
        sa.UniqueConstraint("exam_question_id", "version", name="uq_rubric_exam_version"),
    )

    # ── 统一评分记录表 ──
    op.create_table(
        "code_grades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=True, unique=True),
        sa.Column("exam_answer_id", sa.Integer(), sa.ForeignKey("exam_answers.id"), nullable=True, unique=True),
        sa.Column("rubric_id", sa.Integer(), sa.ForeignKey("question_rubrics.id"), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending", index=True),
        sa.Column("functional_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("algorithm_score", sa.Float(), nullable=True),
        sa.Column("robustness_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("raw_total", sa.Float(), nullable=True),
        sa.Column("score_cap", sa.Float(), nullable=True),
        sa.Column("final_score_100", sa.Float(), nullable=True),
        sa.Column("scaled_score", sa.Float(), nullable=True),
        sa.Column("deterministic_details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("static_analysis", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("ai_result", sa.JSON(), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("needs_teacher_review", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        # XOR: exactly one of submission_id / exam_answer_id must be non-null
        sa.CheckConstraint(
            "(submission_id IS NULL) != (exam_answer_id IS NULL)",
            name="ck_code_grade_xor_target",
        ),
    )

    # ── 教师覆盖审计表 ──
    op.create_table(
        "grade_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code_grade_id", sa.Integer(), sa.ForeignKey("code_grades.id"), nullable=False, index=True),
        sa.Column("original_snapshot", sa.JSON(), nullable=False),
        sa.Column("replacement_snapshot", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── 索引 ──
    op.create_index("ix_judge_questions_grading_mode", "judge_questions", ["grading_mode"])
    op.create_index("ix_exam_questions_grading_mode", "exam_questions", ["grading_mode"])


def downgrade() -> None:
    # 逆序删除：先删依赖表
    op.drop_table("grade_overrides")
    op.drop_table("code_grades")
    op.drop_table("question_rubrics")

    # 删除考试题目 AI 列
    op.drop_index("ix_exam_questions_grading_mode", "exam_questions")
    for col_name in ["grading_mode", "teacher_constraints", "reference_solution", "test_groups", "score_cap_rules"]:
        op.drop_column("exam_questions", col_name)

    # 删除作业题目 AI 列
    op.drop_index("ix_judge_questions_grading_mode", "judge_questions")
    for col_name in ["grading_mode", "teacher_constraints", "reference_solution", "test_groups", "score_cap_rules"]:
        op.drop_column("judge_questions", col_name)
