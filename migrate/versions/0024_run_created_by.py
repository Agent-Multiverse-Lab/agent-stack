"""将 Run 来源字段重命名为 created_by_run_id，保留已有关系。"""

from alembic import op

revision = "0024_run_created_by"
down_revision = "0023_single_agent_active_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Worker 可能已用当前 ORM 在新库创建新列；已有库只重命名，不复制或删除数据。
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_attribute
                WHERE attrelid = 'agent_run'::regclass
                  AND attname = 'parent_run_id' AND NOT attisdropped
            ) THEN
                ALTER TABLE agent_run RENAME COLUMN parent_run_id TO created_by_run_id;
            END IF;
        END $$;
    """)
    op.execute("ALTER INDEX IF EXISTS ix_agent_run_parent_run_id RENAME TO ix_agent_run_created_by_run_id")
    op.alter_column("agent_run", "created_by_run_id", comment="创建当前 Run 的来源 Run ID")


def downgrade() -> None:
    op.alter_column("agent_run", "created_by_run_id", new_column_name="parent_run_id")
    op.execute("ALTER INDEX ix_agent_run_created_by_run_id RENAME TO ix_agent_run_parent_run_id")
    op.alter_column("agent_run", "parent_run_id", comment="当前runid的父id")
