"""将父子 Agent 会话关系迁移到独立关系表。"""

import sqlalchemy as sa
from alembic import op

revision = "0026_subagent_conversation_relation"
down_revision = "0025_knowledge_workspace"
branch_labels = None
depends_on = None


def _validate_existing_relations() -> None:
    bind = op.get_bind()
    mismatched_users = bind.execute(
        sa.text("""
            SELECT COUNT(*)
            FROM conversation AS child
            JOIN conversation AS parent
              ON parent.id = child.parent_conversation_id
            WHERE child.parent_conversation_id IS NOT NULL
              AND child.uid <> parent.uid
        """)
    ).scalar_one()
    if mismatched_users:
        raise RuntimeError("存在用户归属不一致的父子会话，无法迁移")

    missing_creator_runs = bind.execute(
        sa.text("""
            SELECT COUNT(*)
            FROM conversation AS child
            WHERE child.parent_conversation_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM agent_run AS child_run
                  WHERE child_run.conversation_id = child.id
                    AND child_run.run_type = 'subagent'
                    AND child_run.created_by_run_id IS NOT NULL
              )
        """)
    ).scalar_one()
    if missing_creator_runs:
        raise RuntimeError("存在缺少父 Run 来源的子 Agent 会话，无法迁移")


def upgrade() -> None:
    op.create_table(
        "subagent_conversation_relation",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "uid",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "parent_conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_run_id",
            sa.String(length=64),
            sa.ForeignKey("agent_run.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "parent_conversation_id <> child_conversation_id",
            name="ck_subagent_conversation_relation_not_self",
        ),
    )
    op.create_index(
        "uq_subagent_conversation_relation_active_child",
        "subagent_conversation_relation",
        ["child_conversation_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_subagent_conversation_relation_active_parent",
        "subagent_conversation_relation",
        ["uid", "parent_conversation_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    _validate_existing_relations()
    op.execute(
        sa.text("""
            INSERT INTO subagent_conversation_relation (
                uid,
                parent_conversation_id,
                child_conversation_id,
                created_by_run_id,
                created_at,
                deleted_at
            )
            SELECT
                child.uid,
                child.parent_conversation_id,
                child.id,
                (
                    SELECT child_run.created_by_run_id
                    FROM agent_run AS child_run
                    WHERE child_run.conversation_id = child.id
                      AND child_run.run_type = 'subagent'
                      AND child_run.created_by_run_id IS NOT NULL
                    ORDER BY child_run.created_at ASC, child_run.id ASC
                    LIMIT 1
                ),
                child.created_at,
                child.deleted_at
            FROM conversation AS child
            WHERE child.parent_conversation_id IS NOT NULL
        """)
    )

    op.drop_index("ix_conversation_thread_list", table_name="conversation")
    op.drop_index("ix_conversation_parent_conversation_id", table_name="conversation")
    with op.batch_alter_table("conversation") as batch_op:
        batch_op.drop_constraint(
            "fk_conversation_parent_conversation_id",
            type_="foreignkey",
        )
        batch_op.drop_column("parent_conversation_id")
    op.create_index(
        "ix_conversation_thread_list",
        "conversation",
        ["uid", "deleted_at", "updated_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_thread_list", table_name="conversation")
    with op.batch_alter_table("conversation") as batch_op:
        batch_op.add_column(sa.Column("parent_conversation_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_conversation_parent_conversation_id",
            "conversation",
            ["parent_conversation_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.execute(
        sa.text("""
            UPDATE conversation
            SET parent_conversation_id = (
                SELECT relation.parent_conversation_id
                FROM subagent_conversation_relation AS relation
                WHERE relation.child_conversation_id = conversation.id
                  AND relation.deleted_at IS NULL
            )
            WHERE EXISTS (
                SELECT 1
                FROM subagent_conversation_relation AS relation
                WHERE relation.child_conversation_id = conversation.id
                  AND relation.deleted_at IS NULL
            )
        """)
    )
    op.create_index(
        "ix_conversation_parent_conversation_id",
        "conversation",
        ["parent_conversation_id"],
    )
    op.create_index(
        "ix_conversation_thread_list",
        "conversation",
        ["uid", "parent_conversation_id", "deleted_at", "updated_at", "id"],
    )
    op.drop_table("subagent_conversation_relation")
