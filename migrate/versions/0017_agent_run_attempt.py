"""增加 Run 执行归属字段和尝试历史表，不改动现有运行数据或流程。"""

import sqlalchemy as sa
from alembic import op

revision = "0017_agent_run_attempt"
down_revision = "0016_qwen_provider_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_run_attempt",
        sa.Column("id", sa.String(64), primary_key=True, comment="执行尝试ID"),
        sa.Column("run_id", sa.String(64), nullable=False, comment="所属Run ID"),
        sa.Column("worker_id", sa.String(128), nullable=False, comment="执行Worker标识"),
        sa.Column("status", sa.String(32), nullable=False, comment="执行尝试状态"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(), comment="开始时间",
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True, comment="结束时间"),
        sa.Column("error", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("error_type", sa.String(64), nullable=True, comment="错误信息类型"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_run.id"],
            name="fk_agent_run_attempt_run", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("run_id", "id", name="uq_agent_run_attempt_run_id_id"),
    )
    op.create_index(
        "ix_agent_run_attempt_run_started", "agent_run_attempt", ["run_id", "started_at"]
    )
    with op.batch_alter_table("agent_run") as batch:
        batch.add_column(sa.Column(
            "current_attempt_id", sa.String(64), nullable=True, comment="当前执行尝试ID"
        ))
        batch.add_column(sa.Column(
            "owner_worker_id", sa.String(128), nullable=True, comment="当前执行Worker标识"
        ))
        # 默认 NO ACTION：当前指针不能指向其他 Run，也不能删除仍被引用的尝试。
        batch.create_foreign_key(
            "fk_agent_run_current_attempt", "agent_run_attempt",
            ["id", "current_attempt_id"], ["run_id", "id"],
        )


def downgrade() -> None:
    # 先移除反向外键，避免 Run 与 Attempt 的引用环阻止降级。
    with op.batch_alter_table("agent_run") as batch:
        batch.drop_constraint("fk_agent_run_current_attempt", type_="foreignkey")
        batch.drop_column("owner_worker_id")
        batch.drop_column("current_attempt_id")
    op.drop_index("ix_agent_run_attempt_run_started", table_name="agent_run_attempt")
    op.drop_table("agent_run_attempt")
