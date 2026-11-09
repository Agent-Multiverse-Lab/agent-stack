"""将 AgentRun.uid 改为不依赖用户生命周期的归属快照。"""

from alembic import op

revision = "0027_agent_run_uid_snapshot"
down_revision = "0026_subagent_conversation_relation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "agent_run_uid_fkey",
        "agent_run",
        type_="foreignkey",
    )


def downgrade() -> None:
    op.create_foreign_key(
        "agent_run_uid_fkey",
        "agent_run",
        "user",
        ["uid"],
        ["uid"],
        ondelete="CASCADE",
    )
