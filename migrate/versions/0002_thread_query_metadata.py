"""增加对话查询、软删除和 Run 元数据字段。"""

import sqlalchemy as sa
from alembic import op

revision = "0002_thread_query_metadata"
down_revision = "0001_example"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """增加 Thread 查询和软删除所需字段与索引。"""
    op.add_column(
        "conversation",
        sa.Column("parent_conversation_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversation_parent_conversation_id",
        "conversation",
        "conversation",
        ["parent_conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_conversation_parent_conversation_id",
        "conversation",
        ["parent_conversation_id"],
    )
    op.add_column(
        "conversation",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_run",
        sa.Column(
            "run_metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.create_index(
        "ix_conversation_thread_list",
        "conversation",
        [
            "uid",
            "parent_conversation_id",
            "deleted_at",
            "updated_at",
            "id",
        ],
    )
    op.create_index(
        "ix_message_conversation_id_id",
        "message",
        ["conversation_id", "id"],
    )
    op.create_index(
        "ix_agent_run_conversation_status",
        "agent_run",
        ["conversation_id", "agent_status"],
    )
    op.create_index(
        "ix_attachment_conversation_id",
        "attachment",
        ["conversation_id"],
    )


def downgrade() -> None:
    """移除 Thread 查询和软删除所需字段与索引。"""
    op.drop_index("ix_attachment_conversation_id", table_name="attachment")
    op.drop_index(
        "ix_agent_run_conversation_status",
        table_name="agent_run",
    )
    op.drop_index("ix_message_conversation_id_id", table_name="message")
    op.drop_index("ix_conversation_thread_list", table_name="conversation")
    op.drop_column("agent_run", "run_metadata")
    op.drop_column("conversation", "deleted_at")
    op.drop_index(
        "ix_conversation_parent_conversation_id",
        table_name="conversation",
    )
    op.drop_constraint(
        "fk_conversation_parent_conversation_id",
        "conversation",
        type_="foreignkey",
    )
    op.drop_column("conversation", "parent_conversation_id")
