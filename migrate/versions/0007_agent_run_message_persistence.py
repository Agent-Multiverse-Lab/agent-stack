"""持久化 Agent Run 输出消息和工具结果。"""

import sqlalchemy as sa
from alembic import op

revision = "0007_message_persistence"
down_revision = "0006_attachment_file_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """增加 Run 输出指针并移除工具调用排序字段。"""
    op.add_column(
        "agent_run",
        sa.Column("output_message_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_run_output_message_id_message",
        "agent_run",
        "message",
        ["output_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("tool_call", "tool_sequence")
    op.add_column(
        "tool_call",
        sa.Column("status", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    """恢复工具调用排序字段并移除 Run 输出指针。"""
    op.drop_column("tool_call", "status")
    op.add_column(
        "tool_call",
        sa.Column(
            "tool_sequence",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.alter_column("tool_call", "tool_sequence", server_default=None)
    op.drop_constraint(
        "fk_agent_run_output_message_id_message",
        "agent_run",
        type_="foreignkey",
    )
    op.drop_column("agent_run", "output_message_id")
