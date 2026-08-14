"""TASK-010：时间戳列收敛为 NOT NULL（人工审核迁移，禁止 autogenerate 直接落库）

将模型（TimestampMixin：Mapped[datetime] 非空）与实库对齐：
- created_at / updated_at 回填历史 NULL 后设 NOT NULL；
- experiment_submissions.submitted_at 同样回填后设 NOT NULL；
- 保留各列既有 server default（now()/CURRENT_TIMESTAMP）；
- published_at 保持 nullable，不在本迁移处理。

索引/约束名已在模型层对齐（uq_academic_terms_code、
ix_submissions_gs_updated、ix_exam_answers_gs_updated 等），
本迁移不删除、不重命名任何索引。
"""

import sqlalchemy as sa
from alembic import op

revision = "20260813_0001"
down_revision = "20260812_0002"
branch_labels = None
depends_on = None

# (table, columns...) —— DB 中当前可空、需回填后收紧的时间戳列
TIMESTAMP_TABLES = [
    ("users", ("created_at", "updated_at")),
    ("assignments", ("created_at", "updated_at")),
    ("chapters", ("created_at", "updated_at")),
    ("code_grades", ("created_at", "updated_at")),
    ("course_enrollments", ("created_at", "updated_at")),
    ("courses", ("created_at", "updated_at")),
    ("exam_answers", ("created_at", "updated_at")),
    ("exam_grades", ("created_at", "updated_at")),
    ("exam_questions", ("created_at", "updated_at")),
    ("exam_submissions", ("created_at", "updated_at")),
    ("exams", ("created_at", "updated_at")),
    ("experiment_modules", ("created_at", "updated_at")),
    ("experiment_records", ("created_at", "updated_at")),
    ("experiment_submissions", ("created_at", "updated_at", "submitted_at")),
    ("grade_overrides", ("created_at", "updated_at")),
    ("judge_questions", ("created_at", "updated_at")),
    ("lessons", ("created_at", "updated_at")),
    ("notebook_templates", ("created_at", "updated_at")),
    ("question_rubrics", ("created_at", "updated_at")),
    ("submissions", ("created_at", "updated_at")),
]


def upgrade() -> None:
    # 1) 回填历史 NULL（MySQL 允许 UPDATE 同一语句改多列）
    for table, columns in TIMESTAMP_TABLES:
        assignments = ", ".join(f"{col} = CURRENT_TIMESTAMP" for col in columns)
        op.execute(
            sa.text(
                f"UPDATE {table} SET {assignments} "
                f"WHERE {' OR '.join(f'{col} IS NULL' for col in columns)}"
            )
        )
    # 2) 收紧为 NOT NULL（保留既有 server default）
    for table, columns in TIMESTAMP_TABLES:
        with op.batch_alter_table(table) as batch_op:
            for col in columns:
                batch_op.alter_column(
                    col,
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True,
                    nullable=False,
                )


def downgrade() -> None:
    # 仅恢复可空（不回退回填数据）
    for table, columns in TIMESTAMP_TABLES:
        with op.batch_alter_table(table) as batch_op:
            for col in columns:
                batch_op.alter_column(
                    col,
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True,
                )
