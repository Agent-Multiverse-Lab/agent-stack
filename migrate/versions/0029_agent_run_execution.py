"""将 Run 执行记录统一命名为 Execution，保留已有记录和租约。"""

import sqlalchemy as sa
from alembic import op

revision = "0029_agent_run_execution"
down_revision = "0028_agent_run_request"
branch_labels = None
depends_on = None


def _rename_execution_table(old_table: str, new_table: str, old_number: str, new_number: str) -> None:
    """成对重命名表、执行序号和约束，供升级与降级复用。"""
    op.rename_table(old_table, new_table)
    op.alter_column(new_table, old_number, new_column_name=new_number, existing_type=sa.Integer())
    if op.get_context().dialect.name == "sqlite":
        # SQLite 不支持直接重命名约束，通过 batch 重建保留行数据及外键行为。
        with op.batch_alter_table(new_table) as batch:
            batch.drop_constraint(f"uq_{old_table}_run_no", type_="unique")
            batch.create_unique_constraint(f"uq_{new_table}_run_no", ["run_id", new_number])
            batch.drop_constraint(f"fk_{old_table}_run", type_="foreignkey")
            batch.create_foreign_key(f"fk_{new_table}_run", "agent_run", ["run_id"], ["id"], ondelete="CASCADE")
        for index in sa.inspect(op.get_bind()).get_indexes(new_table):
            if old_table in index["name"]:
                op.drop_index(index["name"], table_name=new_table)
                op.create_index(
                    index["name"].replace(old_table, new_table, 1), new_table, index["column_names"],
                    unique=index["unique"], **index.get("dialect_options", {}),
                )
        return

    for old_name, new_name in (
        (f"{old_table}_pkey", f"{new_table}_pkey"),
        (f"uq_{old_table}_run_no", f"uq_{new_table}_run_no"),
        (f"fk_{old_table}_run", f"fk_{new_table}_run"),
    ):
        op.execute(f"ALTER TABLE {new_table} RENAME CONSTRAINT {old_name} TO {new_name}")
    # 迁移创建 run_started 索引，旧版 ORM create_all 创建 run_alive 索引。
    for prefix, suffix in (("ix", "run_started"), ("ix", "run_alive"), ("ix", "lease"), ("uq", "one_open")):
        op.execute(f"ALTER INDEX IF EXISTS {prefix}_{old_table}_{suffix} RENAME TO {prefix}_{new_table}_{suffix}")


def upgrade() -> None:
    _rename_execution_table("agent_run_attempt", "agent_run_execution", "attempt_no", "execution_no")


def downgrade() -> None:
    _rename_execution_table("agent_run_execution", "agent_run_attempt", "execution_no", "attempt_no")
