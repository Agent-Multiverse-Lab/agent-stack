"""会话 Project 归属与置顶。"""

import sqlalchemy as sa
from alembic import op

revision = "0030_project_and_pinned"
down_revision = "0029_agent_run_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("uid", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_project_project_id", "project", ["project_id"], unique=True)
    op.create_index("ix_project_uid", "project", ["uid"])
    op.create_index("ix_project_user_list", "project", ["uid", "deleted_at", "pinned_at", "updated_at", "id"])
    with op.batch_alter_table("conversation") as batch:
        batch.add_column(sa.Column("project_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_conversation_project", "project", ["project_id"], ["project_id"], ondelete="SET NULL")
        batch.create_index("ix_conversation_project_id", ["project_id"])
        batch.create_index("ix_conversation_project_list", ["uid", "deleted_at", "project_id", "pinned_at", "updated_at", "id"])


def downgrade() -> None:
    with op.batch_alter_table("conversation") as batch:
        batch.drop_index("ix_conversation_project_list")
        batch.drop_index("ix_conversation_project_id")
        batch.drop_constraint("fk_conversation_project", type_="foreignkey")
        batch.drop_column("pinned_at")
        batch.drop_column("project_id")
    op.drop_table("project")
