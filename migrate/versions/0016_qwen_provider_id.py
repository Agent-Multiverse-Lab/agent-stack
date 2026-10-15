"""统一 Qwen Provider 标识为现有 Run 使用的 dashscope。"""

import sqlalchemy as sa
from alembic import op

revision = "0016_qwen_provider_id"
down_revision = "0015_model_provider_global"
branch_labels = None
depends_on = None


def _rename(source: str, target: str) -> None:
    connection = op.get_bind()
    rows = set(
        connection.execute(
            sa.text(
                "SELECT provider_id FROM model_provider "
                "WHERE provider_id IN (:source, :target)"
            ),
            {"source": source, "target": target},
        ).scalars()
    )
    if source in rows and target in rows:
        raise RuntimeError(
            f"模型供应商 {source} 与 {target} 同时存在，原数据未修改"
        )
    if source in rows:
        connection.execute(
            sa.text(
                "UPDATE model_provider SET provider_id=:target "
                "WHERE provider_id=:source"
            ),
            {"source": source, "target": target},
        )


def upgrade() -> None:
    _rename("qwen", "dashscope")


def downgrade() -> None:
    _rename("dashscope", "qwen")
