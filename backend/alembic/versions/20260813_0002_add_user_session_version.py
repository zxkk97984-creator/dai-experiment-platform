"""TASK-012：users 增加 session_version（全会话撤销版本号）

- 非空、默认 1：存量用户升级后 session_version=1，历史 token 因不含 sv 统一 401
- 改密/管理员重置/禁用时应用层原子 +1（不在此迁移内做任何数据变更）
- 独立迁移：不与其他功能迁移并行（TASK-018 将基于本 revision 链）
"""
import sqlalchemy as sa
from alembic import op

revision = "20260813_0002"
down_revision = "20260813_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch 模式：SQLite 重建表，MySQL 原生 ADD COLUMN（server_default 为常量，两方言均支持）
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "session_version",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("session_version")
