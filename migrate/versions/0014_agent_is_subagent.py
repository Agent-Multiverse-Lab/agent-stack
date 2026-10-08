"""为 Agent 增加子智能体标记，并按已有角色回填。"""

import sqlalchemy as sa
from alembic import op

revision = "0014_agent_is_subagent"
down_revision = "0013_satellite_business_scenes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent",
        sa.Column(
            "is_subagent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="是否为子智能体",
        ),
    )
    op.execute("UPDATE agent SET is_subagent = (role = 'subagent')")


def downgrade() -> None:
    op.drop_column("agent", "is_subagent")
