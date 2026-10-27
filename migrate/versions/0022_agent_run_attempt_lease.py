"""把执行尝试接入租约：attempt 拥有心跳、到期时间与唯一开放约束。"""

import sqlalchemy as sa
from alembic import op

revision = "0022_agent_run_attempt_lease"
down_revision = "0021_message_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_run_attempt", sa.Column(
        "heartbeat_at", sa.DateTime(timezone=True), nullable=True,
        comment="本 attempt 最近一次续租时间",
    ))
    op.add_column("agent_run_attempt", sa.Column(
        "lease_expires_at", sa.DateTime(timezone=True), nullable=True,
        comment="本 attempt 租约到期时间",
    ))
    op.create_index(
        "ix_agent_run_attempt_lease",
        "agent_run_attempt",
        ["finished_at", "lease_expires_at"],
    )
    # 同一 Run 只能有一条开放 attempt；旧数据中若存在多条，先保留最新一条，
    # 其余以 orphaned 结束，避免创建唯一索引失败。
    op.execute(sa.text("""
        UPDATE agent_run_attempt
        SET finished_at = CURRENT_TIMESTAMP,
            status = 'orphaned',
            error_type = 'OrphanedAttempt',
            error = 'Closed before adding the one-open-attempt constraint'
        WHERE finished_at IS NULL
          AND id NOT IN (
              SELECT keep_id FROM (
                  SELECT MAX(id) AS keep_id
                  FROM agent_run_attempt
                  WHERE finished_at IS NULL
                  GROUP BY run_id
              ) AS keepers
          )
    """))
    op.create_index(
        "uq_agent_run_attempt_one_open",
        "agent_run_attempt",
        ["run_id"],
        unique=True,
        postgresql_where=sa.text("finished_at IS NULL"),
        sqlite_where=sa.text("finished_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_agent_run_attempt_one_open", table_name="agent_run_attempt")
    op.drop_index("ix_agent_run_attempt_lease", table_name="agent_run_attempt")
    op.drop_column("agent_run_attempt", "lease_expires_at")
    op.drop_column("agent_run_attempt", "heartbeat_at")
