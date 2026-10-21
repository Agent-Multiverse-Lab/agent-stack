"""使用 Run 内尝试序号，移除当前尝试指针并统一 Worker 字段命名。"""

import sqlalchemy as sa
from alembic import op

revision = "0018_agent_run_attempt_no"
down_revision = "0017_agent_run_attempt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agent_run") as batch:
        batch.drop_constraint("fk_agent_run_current_attempt", type_="foreignkey")
        batch.drop_column("current_attempt_id")
        batch.alter_column("owner_worker_id", new_column_name="worker_id", existing_type=sa.String(128))
    op.add_column("agent_run_attempt", sa.Column(
        "attempt_no", sa.Integer(), nullable=True, comment="Run内尝试序号，从1递增",
    ))
    # 旧结构没有序号，按开始时间及 ID 确定稳定的 Run 内顺序。
    op.execute(sa.text("""
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY run_id ORDER BY started_at, id
            ) AS attempt_no
            FROM agent_run_attempt
        )
        UPDATE agent_run_attempt
        SET attempt_no = (SELECT attempt_no FROM numbered WHERE numbered.id = agent_run_attempt.id)
    """))
    with op.batch_alter_table("agent_run_attempt") as batch:
        batch.drop_constraint("uq_agent_run_attempt_run_id_id", type_="unique")
        batch.alter_column("attempt_no", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint("uq_agent_run_attempt_run_no", ["run_id", "attempt_no"])


def downgrade() -> None:
    with op.batch_alter_table("agent_run_attempt") as batch:
        batch.drop_constraint("uq_agent_run_attempt_run_no", type_="unique")
        batch.drop_column("attempt_no")
        batch.create_unique_constraint("uq_agent_run_attempt_run_id_id", ["run_id", "id"])
    # 无法从最新尝试可靠推断原来的指针，恢复为空；Worker 字段只改名。
    with op.batch_alter_table("agent_run") as batch:
        batch.add_column(sa.Column(
            "current_attempt_id", sa.String(64), nullable=True, comment="当前执行尝试ID",
        ))
        batch.alter_column("worker_id", new_column_name="owner_worker_id", existing_type=sa.String(128))
        batch.create_foreign_key(
            "fk_agent_run_current_attempt", "agent_run_attempt",
            ["id", "current_attempt_id"], ["run_id", "id"],
        )
