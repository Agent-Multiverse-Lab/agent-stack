"""为 model_provider 表新增 embedding_base_url 和 rerank_base_url 字段。"""

import sqlalchemy as sa
from alembic import op

revision = "0032_model_provider_category_urls"
down_revision = "0031_request_dispatch_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_provider",
        sa.Column("embedding_base_url", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "model_provider",
        sa.Column("rerank_base_url", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("model_provider", "rerank_base_url")
    op.drop_column("model_provider", "embedding_base_url")
