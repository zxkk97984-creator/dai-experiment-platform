"""add lesson video upload fields

Revision ID: a3b4c5d6e789
Revises: f2a3b4c5d678
Create Date: 2026-08-05 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a3b4c5d6e789"
down_revision = "f2a3b4c5d678"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 视频来源与文件元数据：video_source 区分外链（external）与本地上传（upload），
    # 存量数据全部保持 external，原 video_url 不改写。
    # batch_alter_table 保证 MySQL / SQLite 均可执行。
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.add_column(
            sa.Column(
                "video_source",
                sa.String(length=20),
                server_default="external",
                nullable=False,
            )
        )
        # 以下四个可空元数据列仅服务端使用
        batch_op.add_column(sa.Column("video_storage_key", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("video_filename", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("video_content_type", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("video_size", sa.BigInteger(), nullable=True))
    # 不创建索引：这些字段不参与列表过滤或关联查询


def downgrade() -> None:
    # 按逆序删除新增列；不自动删除磁盘文件，避免数据库回滚造成不可恢复的数据丢失
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.drop_column("video_size")
        batch_op.drop_column("video_content_type")
        batch_op.drop_column("video_filename")
        batch_op.drop_column("video_storage_key")
        batch_op.drop_column("video_source")
