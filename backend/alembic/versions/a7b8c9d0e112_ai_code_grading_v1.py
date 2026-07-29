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


def _json_server_default(value: str):
    literal = f"'{value}'"
    if op.get_bind().dialect.name == "mysql":
        literal = f"({literal})"
    return sa.text(literal)


def _is_offline_mode() -> bool:
    """离线 SQL 生成没有可检查的数据库，保持 Alembic 的普通 DDL 输出。"""
    try:
        return bool(op.get_context().as_sql)
    except AttributeError:
        return False


def _add_missing_columns(table_name: str, columns: list[sa.Column]) -> None:
    existing_columns = set()
    if not _is_offline_mode():
        existing_columns = {
            column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)
        }
    for column in columns:
        if column.name not in existing_columns:
            op.add_column(table_name, column)


def _create_table_if_missing(table_name: str, *columns_and_constraints) -> None:
    if not _is_offline_mode():
        existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
        if table_name in existing_tables:
            return
    op.create_table(table_name, *columns_and_constraints)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if not _is_offline_mode():
        existing_indexes = {
            index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)
        }
        if index_name in existing_indexes:
            return
    op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    # ── 作业题目 AI 评分字段 ──
    _add_missing_columns("judge_questions", [
        sa.Column("grading_mode", sa.String(length=20), nullable=False, server_default="legacy"),
        sa.Column("teacher_constraints", sa.JSON(), nullable=False, server_default=_json_server_default("{}")),
        sa.Column("reference_solution", sa.Text(), nullable=True),
        sa.Column("test_groups", sa.JSON(), nullable=False, server_default=_json_server_default("[]")),
        sa.Column("score_cap_rules", sa.JSON(), nullable=False, server_default=_json_server_default("[]")),
    ])

    # ── 考试题目 AI 评分字段 ──
    _add_missing_columns("exam_questions", [
        sa.Column("grading_mode", sa.String(length=20), nullable=False, server_default="legacy"),
        sa.Column("teacher_constraints", sa.JSON(), nullable=False, server_default=_json_server_default("{}")),
        sa.Column("reference_solution", sa.Text(), nullable=True),
        sa.Column("test_groups", sa.JSON(), nullable=False, server_default=_json_server_default("[]")),
        sa.Column("score_cap_rules", sa.JSON(), nullable=False, server_default=_json_server_default("[]")),
    ])

    # ── Rubric 版本表 ──
    _create_table_if_missing(
        "question_rubrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("judge_question_id", sa.Integer(), sa.ForeignKey("judge_questions.id"), nullable=True),
        sa.Column("exam_question_id", sa.Integer(), sa.ForeignKey("exam_questions.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
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
    _create_table_if_missing(
        "code_grades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=True, unique=True),
        sa.Column("exam_answer_id", sa.Integer(), sa.ForeignKey("exam_answers.id"), nullable=True, unique=True),
        sa.Column("rubric_id", sa.Integer(), sa.ForeignKey("question_rubrics.id"), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("functional_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("algorithm_score", sa.Float(), nullable=True),
        sa.Column("robustness_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("raw_total", sa.Float(), nullable=True),
        sa.Column("score_cap", sa.Float(), nullable=True),
        sa.Column("final_score_100", sa.Float(), nullable=True),
        sa.Column("scaled_score", sa.Float(), nullable=True),
        sa.Column("deterministic_details", sa.JSON(), nullable=False, server_default=_json_server_default("{}")),
        sa.Column("static_analysis", sa.JSON(), nullable=False, server_default=_json_server_default("{}")),
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
    _create_table_if_missing(
        "grade_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code_grade_id", sa.Integer(), sa.ForeignKey("code_grades.id"), nullable=False),
        sa.Column("original_snapshot", sa.JSON(), nullable=False),
        sa.Column("replacement_snapshot", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── 索引 ──
    _create_index_if_missing(
        "ix_question_rubrics_judge_question_id",
        "question_rubrics",
        ["judge_question_id"],
    )
    _create_index_if_missing(
        "ix_question_rubrics_exam_question_id",
        "question_rubrics",
        ["exam_question_id"],
    )
    _create_index_if_missing(
        "ix_question_rubrics_status",
        "question_rubrics",
        ["status"],
    )
    _create_index_if_missing("ix_code_grades_status", "code_grades", ["status"])
    _create_index_if_missing(
        "ix_grade_overrides_code_grade_id",
        "grade_overrides",
        ["code_grade_id"],
    )
    _create_index_if_missing("ix_judge_questions_grading_mode", "judge_questions", ["grading_mode"])
    _create_index_if_missing("ix_exam_questions_grading_mode", "exam_questions", ["grading_mode"])


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
