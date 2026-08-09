"""收敛用户附件文件字段。"""

import sqlalchemy as sa
from alembic import op

revision = "0006_attachment_file_contract"
down_revision = "0005_current_model_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """移除解析状态并统一文件字段名。"""
    op.drop_index("ix_attachment_status_created_at", table_name="attachment")
    op.alter_column(
        "attachment",
        "attachment_name",
        new_column_name="file_name",
        existing_type=sa.String(length=255),
        existing_nullable=False,
        comment="文件名",
    )
    op.alter_column(
        "attachment",
        "attachment_type",
        new_column_name="content_type",
        existing_type=sa.String(length=128),
        existing_nullable=False,
        comment="文件 MIME 类型",
    )
    op.alter_column(
        "attachment",
        "attachment_size",
        new_column_name="file_size",
        existing_type=sa.Integer(),
        existing_nullable=False,
        comment="文件字节数",
    )
    op.alter_column(
        "attachment",
        "original_object_name",
        new_column_name="object_name",
        existing_type=sa.String(length=1024),
        existing_nullable=False,
        comment="当前 MinIO 对象名",
    )
    op.drop_column("attachment", "status")
    op.drop_column("attachment", "error_message")
    op.drop_column("attachment", "markdown_object_name")


def downgrade() -> None:
    """恢复旧附件处理字段。"""
    op.add_column(
        "attachment",
        sa.Column("markdown_object_name", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "attachment",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "attachment",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="uploaded",
        ),
    )
    op.alter_column(
        "attachment",
        "object_name",
        new_column_name="original_object_name",
        existing_type=sa.String(length=1024),
        existing_nullable=False,
    )
    op.alter_column(
        "attachment",
        "file_size",
        new_column_name="attachment_size",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "attachment",
        "content_type",
        new_column_name="attachment_type",
        existing_type=sa.String(length=128),
        existing_nullable=False,
    )
    op.alter_column(
        "attachment",
        "file_name",
        new_column_name="attachment_name",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
    op.create_index(
        "ix_attachment_status_created_at",
        "attachment",
        ["status", "created_at"],
    )
