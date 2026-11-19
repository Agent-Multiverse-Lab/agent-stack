"""会话请求分发策略与等待区。"""

import sqlalchemy as sa
from alembic import op

revision = "0031_request_dispatch_queue"
down_revision = "0030_project_and_pinned"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_agent_run_request_conversation_id", table_name="agent_run_request")
    op.drop_column("agent_run_request", "conversation_id")
    op.add_column("agent_run_request", sa.Column("dispatch_policy", sa.String(16), nullable=False, server_default="enqueue"))
    op.add_column("agent_run_request", sa.Column("status", sa.String(16), nullable=False, server_default="dispatched"))
    op.add_column("agent_run_request", sa.Column("queue_seq", sa.Integer(), nullable=True))
    op.create_index("ix_agent_run_request_thread_id", "agent_run_request", ["thread_id"])
    op.create_index("ix_agent_run_request_thread_queued", "agent_run_request", ["thread_id", "queue_seq"], postgresql_where=sa.text("status = 'queued'"))


def downgrade() -> None:
    op.drop_index("ix_agent_run_request_thread_queued", table_name="agent_run_request")
    op.drop_index("ix_agent_run_request_thread_id", table_name="agent_run_request")
    op.add_column("agent_run_request", sa.Column("conversation_id", sa.Integer(), nullable=True))
    op.execute("UPDATE agent_run_request SET conversation_id = message.conversation_id FROM message WHERE message.id = agent_run_request.trigger_message_id")
    op.alter_column("agent_run_request", "conversation_id", nullable=False)
    op.create_foreign_key("agent_run_request_conversation_id_fkey", "agent_run_request", "conversation", ["conversation_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_agent_run_request_conversation_id", "agent_run_request", ["conversation_id"])
    op.drop_column("agent_run_request", "queue_seq")
    op.drop_column("agent_run_request", "status")
    op.drop_column("agent_run_request", "dispatch_policy")
