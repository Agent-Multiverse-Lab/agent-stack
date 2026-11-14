"""保存聊天请求与输入关联，在独立事务中创建 Run。"""

import sqlalchemy as sa
from alembic import op

revision = "0028_agent_run_request"
down_revision = "0027_agent_run_uid_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_run_request",
        sa.Column("request_id", sa.String(128), primary_key=True),
        sa.Column("uid", sa.String(64), nullable=False),
        sa.Column(
            "conversation_id", sa.Integer(),
            sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("thread_id", sa.String(64), nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column(
            "trigger_message_id", sa.Integer(),
            sa.ForeignKey("message.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_agent_run_request_conversation_id", "agent_run_request", ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_run_request_conversation_id", table_name="agent_run_request")
    op.drop_table("agent_run_request")
