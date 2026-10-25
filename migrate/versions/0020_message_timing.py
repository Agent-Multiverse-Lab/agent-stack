"""为消息增加展示顺序与耗时字段。"""

import sqlalchemy as sa
from alembic import op

revision = "0020_message_timing"
down_revision = "0019_agent_run_lease"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("message", sa.Column("sequence", sa.BigInteger(), nullable=True, comment="同一会话内的稳定展示顺序"))
    op.add_column("message", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True, comment="观察到的开始时间"))
    op.add_column("message", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True, comment="观察到的结束时间"))
    op.add_column("message", sa.Column("duration_ms", sa.BigInteger(), nullable=True, comment="单调时钟计算的操作耗时"))
    op.add_column("message", sa.Column("execution_status", sa.String(32), nullable=True, comment="running/completed/failed/interrupted"))
    op.add_column("message", sa.Column("operation_id", sa.String(128), nullable=True, comment="同一 Run 内的 Model/Tool 稳定来源键"))
    op.add_column("message", sa.Column("usage", sa.JSON(), nullable=True, comment="Provider 返回的单次可靠 usage"))
    op.create_index("ix_message_conversation_sequence", "message", ["conversation_id", "sequence"])


def downgrade() -> None:
    op.drop_index("ix_message_conversation_sequence", table_name="message")
    for column in ("usage", "operation_id", "execution_status", "duration_ms", "finished_at", "started_at", "sequence"):
        op.drop_column("message", column)
