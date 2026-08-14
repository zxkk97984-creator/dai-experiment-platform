"""TASK-031：恢复 MySQL 时间戳列 server default（修复 20260813_0001 的方言副作用）

20260813_0001（时间戳列收紧 NOT NULL）在 MySQL 上以 MODIFY COLUMN 执行，
未重新声明 DEFAULT 子句导致各列 server default 丢失（MySQL 的 MODIFY
不会保留原默认值）。后果：任何依赖 DB 侧默认值的时间戳 INSERT 报
1364 "Field 'created_at' doesn't have a default value"——生产部署后
首条写入即失败（本地 CI 等价空库流程已复现）。

SQLite 上 batch 重建会保留反射到的默认值，本迁移对 SQLite 幂等无副作用。
"""
import sqlalchemy as sa
from alembic import op

revision = "20260815_0001"
down_revision = "20260813_0003"
branch_labels = None
depends_on = None

# 与 20260813_0001 相同的表/列清单（模型层全部为 server_default=func.now()）
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
    for table, columns in TIMESTAMP_TABLES:
        with op.batch_alter_table(table) as batch_op:
            for col in columns:
                batch_op.alter_column(
                    col,
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    server_default=sa.func.now(),
                )


def downgrade() -> None:
    for table, columns in TIMESTAMP_TABLES:
        with op.batch_alter_table(table) as batch_op:
            for col in columns:
                batch_op.alter_column(
                    col,
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    server_default=None,
                )
