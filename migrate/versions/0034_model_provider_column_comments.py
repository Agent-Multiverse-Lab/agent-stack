"""为 model_provider 表各列补齐中文注释。"""

import sqlalchemy as sa
from alembic import op

revision = "0034_model_provider_column_comments"
down_revision = "0033_drop_conversation_summary"
branch_labels = None
depends_on = None

_COLUMN_COMMENTS = (
    ("provider_id", sa.String(64), "模型供应商唯一标识"),
    ("name", sa.String(255), "供应商展示名称"),
    ("base_url", sa.Text(), "Chat 接口基础地址"),
    ("embedding_base_url", sa.Text(), "Embedding 接口基础地址"),
    ("rerank_base_url", sa.Text(), "Rerank 接口基础地址"),
    ("protocol", sa.String(32), "模型协议类型（openai_compatible/anthropic/gemini）"),
    ("api_key", sa.String(), "API 密钥或环境变量名"),
    ("extra_headers", sa.JSON(), "附加请求头配置"),
    ("is_enabled", sa.Boolean(), "是否启用该供应商"),
    ("enabled_models", sa.JSON(), "已启用的模型清单（含分类与能力）"),
    ("created_at", sa.DateTime(timezone=True), "创建时间"),
    ("updated_at", sa.DateTime(timezone=True), "更新时间"),
)


def upgrade() -> None:
    for name, col_type, comment in _COLUMN_COMMENTS:
        op.alter_column(
            "model_provider",
            name,
            existing_type=col_type,
            existing_nullable=False,
            comment=comment,
        )


def downgrade() -> None:
    for name, col_type, _comment in _COLUMN_COMMENTS:
        op.alter_column(
            "model_provider",
            name,
            existing_type=col_type,
            existing_nullable=False,
            comment=None,
        )
