"""make judge_questions.environment_version_id nullable

修复迁移 B（c5d6e7f8a901）步骤 4 的误伤：judge_questions.environment_version_id
在迁移 B 中被 alter_column 改成 non-null，但题目环境列的语义是「NULL = 继承作业默认环境」：

- 模型层（models/__init__.py JudgeQuestion）定义 nullable=True，注释明确 NULL 语义为继承；
- 服务层（app/api/assignments.py create_question）对未提供的环境显式置 None 表示继承，
  不做 basic 兜底解析（与作业/Notebook 草稿的「省略时解析 basic」不同——题目的 None 是合法
  语义而非未选择），运行时由 `question.environment_version_id or assignment.environment_version_id`
  解析生效环境；
- 因此该列必须接受 NULL，否则 `POST /assignments/{id}/questions` 传 `environment_version_id: null`
  （默认「继承作业默认」）会 500（IntegrityError: Column 'environment_version_id' cannot be null）。

其余 5 张业务表的同批绑定列（assignments / submissions / notebook_templates /
notebook_template_versions / experiment_records）保持 NOT NULL：其创建链路均有服务层
basic 兜底或从模板版本/提交解析复制，正常不会落 NULL，不属于本次问题范围。

Revision ID: d6e7f8a9b012
Revises: c5d6e7f8a901
Create Date: 2026-08-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "d6e7f8a9b012"
down_revision = "c5d6e7f8a901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MySQL 直接 ALTER MODIFY（batch 模式在 MySQL 下不做表重建），
    # 仅改 nullable 属性，不影响既有外键 fk_judge_questions_env_version 与索引。
    with op.batch_alter_table("judge_questions") as batch_op:
        batch_op.alter_column(
            "environment_version_id",
            existing_type=sa.BigInteger(),
            nullable=True,
        )


def downgrade() -> None:
    # 还原迁移 B 步骤 4 的 non-null 状态（回滚前需确保无 NULL 存量行）
    with op.batch_alter_table("judge_questions") as batch_op:
        batch_op.alter_column(
            "environment_version_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
