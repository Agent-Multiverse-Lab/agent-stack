"""为 Agent Run 增加 Worker 租约字段，支持 ARQ 执行期间续租与过期收敛。"""

import sqlalchemy as sa
from alembic import op

revision = "0019_agent_run_lease"
down_revision = "0018_agent_run_attempt_no"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_run", sa.Column(
        "heartbeat_at", sa.DateTime(timezone=True), nullable=True,
        comment="最近一次租约续期时间",
    ))
    op.add_column("agent_run", sa.Column(
        "lease_expires_at", sa.DateTime(timezone=True), nullable=True,
        comment="租约到期时间，过期后由 Worker 收敛为终态",
    ))
    op.create_index(
        "ix_agent_run_lease", "agent_run", ["agent_status", "lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_run_lease", table_name="agent_run")
    op.drop_column("agent_run", "lease_expires_at")
    op.drop_column("agent_run", "heartbeat_at")
