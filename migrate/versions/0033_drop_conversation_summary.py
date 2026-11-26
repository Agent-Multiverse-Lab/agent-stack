"""移除 conversation 表未使用的 summary 字段。"""

import sqlalchemy as sa
from alembic import op

revision = "0033_drop_conversation_summary"
down_revision = "0032_model_provider_category_urls"
branch_labels = None
depends_on = None


def _has_summary_column() -> bool:
    bind = op.get_bind()
    if bind is None:
        return True
    return "summary" in {col["name"] for col in sa.inspect(bind).get_columns("conversation")}


def upgrade() -> None:
    if _has_summary_column():
        op.drop_column("conversation", "summary")


def downgrade() -> None:
    if not _has_summary_column():
        op.add_column(
            "conversation",
            sa.Column("summary", sa.Text(), nullable=True, comment="会话摘要"),
        )
