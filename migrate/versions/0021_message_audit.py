"""为消息审计增加 Run 内 operation 索引。"""

import sqlalchemy as sa
from alembic import op

revision = "0021_message_audit"
down_revision = "0020_message_timing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_message_run_operation",
        "message",
        ["agent_run_id", "operation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_message_run_operation", table_name="message")
