"""限制同一会话同时只允许一个执行中的 AgentRun。"""

import sqlalchemy as sa
from alembic import op

revision = "0023_single_agent_active_unique"
down_revision = "0022_agent_run_attempt_lease"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 迁移前若同一 thread_id 已存在多条未终态 Run，只保留最新一条，其余收敛为
    # failed 并关闭残留开放 attempt，避免创建唯一索引失败。
    op.execute(sa.text("""
        UPDATE agent_run
        SET agent_status = 'failed',
            error = 'duplicate active run resolved during migration',
            error_type = 'DuplicateActiveRunMigration',
            finished_at = CURRENT_TIMESTAMP,
            worker_id = NULL,
            heartbeat_at = NULL,
            lease_expires_at = NULL
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY thread_id
                           ORDER BY created_at DESC, id DESC
                       ) AS rn
                FROM agent_run
                WHERE agent_status IN ('pending', 'running', 'cancel_requested')
            ) AS ranked
            WHERE rn > 1
        )
    """))
    op.execute(sa.text("""
        UPDATE agent_run_attempt
        SET finished_at = CURRENT_TIMESTAMP,
            status = 'orphaned',
            error_type = 'OrphanedAttempt',
            error = 'Closed when duplicate active run was resolved during migration'
        WHERE finished_at IS NULL
          AND run_id IN (
              SELECT id
              FROM agent_run
              WHERE agent_status = 'failed'
                AND error_type = 'DuplicateActiveRunMigration'
          )
    """))
    op.create_index(
        "uq_agent_run_one_executing_per_thread",
        "agent_run",
        ["thread_id"],
        unique=True,
        postgresql_where=sa.text(
            "agent_status IN ('pending', 'running', 'cancel_requested')"
        ),
        sqlite_where=sa.text(
            "agent_status IN ('pending', 'running', 'cancel_requested')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_agent_run_one_executing_per_thread", table_name="agent_run")
