"""TASK-012：users.session_version 全会话撤销（人工审核迁移）

新增非空 session_version=1；Access/Refresh 签发时写入 sv，
认证与刷新对比数据库值；改密、管理员重置、禁用用户时原子递增，
旧 Token（含上线前无 sv 的 Token）立即失效并要求重新登录。
"""

import sqlalchemy as sa
from alembic import op

revision = "20260813_0002"
down_revision = "20260813_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "session_version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("session_version")
