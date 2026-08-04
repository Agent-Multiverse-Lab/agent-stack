"""建立用户附件生命周期与消息引用结构。"""

import sqlalchemy as sa
from alembic import op

revision = "0003_attachment_library"
down_revision = "0002_thread_query_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """将附件改为用户资源并增加消息引用。"""
    op.drop_index(
        "ix_attachment_conversation_id",
        table_name="attachment",
        if_exists=True,
    )
    op.drop_constraint(
        "attachment_conversation_id_fkey",
        "attachment",
        type_="foreignkey",
        if_exists=True,
    )
    op.drop_constraint(
        "attachment_uid_fkey",
        "attachment",
        type_="foreignkey",
        if_exists=True,
    )
    op.alter_column(
        "attachment",
        "uid",
        new_column_name="user_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "attachment",
        "attachment_path",
        new_column_name="original_object_name",
        existing_type=sa.String(length=1024),
        existing_nullable=False,
    )
    op.drop_column("attachment", "conversation_id")
    op.add_column(
        "attachment",
        sa.Column("file_id", sa.String(length=36), nullable=False),
    )
    op.create_unique_constraint(
        "uq_attachment_file_id",
        "attachment",
        ["file_id"],
    )
    op.add_column(
        "attachment",
        sa.Column(
            "markdown_object_name",
            sa.String(length=1024),
            nullable=True,
        ),
    )
    op.add_column(
        "attachment",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "attachment",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_attachment_user_id_user",
        "attachment",
        "user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_attachment_user_library",
        "attachment",
        ["user_id", "deleted_at", "id"],
    )
    op.create_index(
        "ix_attachment_status_created_at",
        "attachment",
        ["status", "created_at"],
    )
    op.create_table(
        "message_attachment",
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["message.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["attachment.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id", "attachment_id"),
        sa.UniqueConstraint(
            "message_id",
            "position",
            name="uq_message_attachment_position",
        ),
    )
    op.create_index(
        "ix_message_attachment_attachment_id",
        "message_attachment",
        ["attachment_id"],
    )
    op.add_column(
        "message",
        sa.Column(
            "msg_metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )


def downgrade() -> None:
    """恢复旧的 Conversation 附件结构。"""
    op.drop_column("message", "msg_metadata")
    op.drop_index(
        "ix_message_attachment_attachment_id",
        table_name="message_attachment",
    )
    op.drop_table("message_attachment")
    op.drop_index(
        "ix_attachment_status_created_at",
        table_name="attachment",
    )
    op.drop_index(
        "ix_attachment_user_library",
        table_name="attachment",
    )
    op.drop_constraint(
        "fk_attachment_user_id_user",
        "attachment",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_attachment_file_id",
        "attachment",
        type_="unique",
    )
    op.drop_column("attachment", "file_id")
    op.drop_column("attachment", "deleted_at")
    op.drop_column("attachment", "error_message")
    op.drop_column("attachment", "markdown_object_name")
    op.add_column(
        "attachment",
        sa.Column("conversation_id", sa.Integer(), nullable=True),
    )
    op.alter_column(
        "attachment",
        "original_object_name",
        new_column_name="attachment_path",
        existing_type=sa.String(length=1024),
        existing_nullable=False,
    )
    op.alter_column(
        "attachment",
        "user_id",
        new_column_name="uid",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.create_foreign_key(
        "attachment_uid_fkey",
        "attachment",
        "user",
        ["uid"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "attachment_conversation_id_fkey",
        "attachment",
        "conversation",
        ["conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_attachment_conversation_id",
        "attachment",
        ["conversation_id"],
    )
