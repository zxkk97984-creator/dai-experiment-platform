"""TASK-010：时间戳列回填并收紧 NOT NULL（ORM 与实库收敛，人工审核迁移）

背景：
- 模型 TimestampMixin 声明 created_at/updated_at 为 NOT NULL + server_default CURRENT_TIMESTAMP，
  但历史迁移在 MySQL 中创建为 nullable 列；experiment_submissions.submitted_at 同理。
- 本迁移先回填历史 NULL（CURRENT_TIMESTAMP），再收紧 NOT NULL，保留 server default。

禁止事项（TASK-010 约束）：
- 不重命名业务表、不删除任何索引；ix_submissions_gs_updated / ix_exam_answers_gs_updated
  等复合索引已在模型中显式声明保留，本迁移不触碰。
- 不混入任何其他功能迁移。

风险：MySQL 非事务 DDL；大表 ALTER 可能锁表——建议在低峰执行（教育规模单机可接受）。
"""
import sqlalchemy as sa
from alembic import op

revision = "20260813_0001"
down_revision = "20260812_0002"
branch_labels = None
depends_on = None

# 实库中 created_at/updated_at 仍为 nullable 的表（来自 alembic check 实测清单）
_TIMESTAMP_TABLES = [
    "users",
    "courses",
    "chapters",
    "lessons",
    "course_enrollments",
    "assignments",
    "judge_questions",
    "submissions",
    "exams",
    "exam_submissions",
    "exam_grades",
    "exam_questions",
    "exam_answers",
    "notebook_templates",
    "experiment_modules",
    "experiment_records",
    "experiment_submissions",
    "question_rubrics",
    "code_grades",
    "grade_overrides",
]

_SUBMITTED_AT_TABLES = ["experiment_submissions"]


def upgrade() -> None:
    for table in _TIMESTAMP_TABLES:
        for column in ("created_at", "updated_at"):
            op.execute(
                sa.text(
                    f"UPDATE {table} SET {column} = CURRENT_TIMESTAMP WHERE {column} IS NULL"
                )
            )
            op.alter_column(
                table,
                column,
                existing_type=sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
    for table in _SUBMITTED_AT_TABLES:
        op.execute(
            sa.text(
                f"UPDATE {table} SET submitted_at = CURRENT_TIMESTAMP WHERE submitted_at IS NULL"
            )
        )
        op.alter_column(
            table,
            "submitted_at",
            existing_type=sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )


def downgrade() -> None:
    """恢复 nullable（保留 server default，与升级前状态一致）。"""
    for table in _TIMESTAMP_TABLES:
        for column in ("created_at", "updated_at"):
            op.alter_column(
                table,
                column,
                existing_type=sa.DateTime(),
                nullable=True,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
    for table in _SUBMITTED_AT_TABLES:
        op.alter_column(
            table,
            "submitted_at",
            existing_type=sa.DateTime(),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
