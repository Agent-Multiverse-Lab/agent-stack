"""同步当前知识库与 Agent Run 模型结构。"""

import sqlalchemy as sa
from alembic import op

revision = "0005_current_model_schema"
down_revision = "0004_remove_script_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建知识库表并移除 Agent Run 的旧状态字段。"""
    op.create_table(
        "knowledge_base",
        sa.Column(
            "kb_id",
            sa.String(length=128),
            nullable=False,
            comment="知识库业务标识",
        ),
        sa.Column(
            "uid",
            sa.String(length=128),
            nullable=False,
            comment="所属用户",
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
            comment="知识库名称",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            comment="知识库描述",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="知识库状态",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(
            ["uid"],
            ["user.uid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("kb_id"),
    )
    op.create_index(
        "ix_knowledge_base_uid",
        "knowledge_base",
        ["uid"],
    )
    op.create_index(
        "ix_knowledge_base_status",
        "knowledge_base",
        ["status"],
    )

    op.create_table(
        "knowledge_file",
        sa.Column(
            "file_id",
            sa.String(length=64),
            nullable=False,
            comment="文件业务标识",
        ),
        sa.Column(
            "kb_id",
            sa.String(length=128),
            nullable=False,
            comment="所属知识库",
        ),
        sa.Column(
            "original_file_name",
            sa.String(length=512),
            nullable=False,
            comment="原始文件名",
        ),
        sa.Column(
            "original_object_name",
            sa.String(length=1024),
            nullable=False,
            comment="原文件 MinIO 对象名",
        ),
        sa.Column(
            "markdown_object_name",
            sa.String(length=1024),
            nullable=True,
            comment="解析后 Markdown 对象名",
        ),
        sa.Column(
            "content_type",
            sa.String(length=128),
            nullable=False,
            comment="原文件 MIME 类型",
        ),
        sa.Column(
            "file_size",
            sa.Integer(),
            nullable=False,
            comment="原文件字节数",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="uploaded/parsing/parsed/indexing/indexed/failed",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="最近一次处理错误",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(
            ["kb_id"],
            ["knowledge_base.kb_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("file_id"),
        sa.UniqueConstraint("original_object_name"),
    )
    op.create_index(
        "ix_knowledge_file_kb_id",
        "knowledge_file",
        ["kb_id"],
    )
    op.create_index(
        "ix_knowledge_file_status",
        "knowledge_file",
        ["status"],
    )

    op.create_table(
        "knowledge_embedding_binding",
        sa.Column("uid", sa.String(length=128), nullable=False),
        sa.Column("kb_id", sa.String(length=128), nullable=False),
        sa.Column(
            "collection_name",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "embedding_model_spec",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("embedding_batch_size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["uid"],
            ["user.uid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["kb_id"],
            ["knowledge_base.kb_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uid", "kb_id"),
    )

    op.add_column(
        "agent_run",
        sa.Column(
            "run_type",
            sa.String(length=32),
            nullable=False,
            server_default="chat",
            comment="运行类型 chat, subagent",
        ),
    )
    op.execute(
        "UPDATE agent_run AS ar "
        "SET run_type = CASE "
        "WHEN a.role = 'subagent' THEN 'subagent' ELSE 'chat' END "
        "FROM agent AS a "
        "WHERE a.slug = ar.agent_id"
    )
    op.create_index(
        "ix_agent_run_run_type",
        "agent_run",
        ["run_type"],
    )
    op.drop_column("agent_run", "status")

    _set_current_comments()


def downgrade() -> None:
    """恢复 Agent Run 旧字段并移除知识库表。"""
    _restore_previous_comments()

    op.add_column(
        "agent_run",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
            comment="Agent运行状态",
        ),
    )
    op.execute("UPDATE agent_run SET status = agent_status")
    op.alter_column("agent_run", "status", server_default=None)
    op.drop_index("ix_agent_run_run_type", table_name="agent_run")
    op.drop_column("agent_run", "run_type")

    op.drop_table("knowledge_embedding_binding")
    op.drop_index("ix_knowledge_file_status", table_name="knowledge_file")
    op.drop_index("ix_knowledge_file_kb_id", table_name="knowledge_file")
    op.drop_table("knowledge_file")
    op.drop_index("ix_knowledge_base_status", table_name="knowledge_base")
    op.drop_index("ix_knowledge_base_uid", table_name="knowledge_base")
    op.drop_table("knowledge_base")


def _set_current_comments() -> None:
    """同步已有字段的当前模型注释。"""
    comments = (
        ("agent_run", "agent_status", sa.String(length=32), "运行状态 pending, running, cancel_requested, completed, failed, cancelled"),
        ("agent_run", "run_metadata", sa.JSON(), "单次运行元数据"),
        ("attachment", "file_id", sa.String(length=36), "附件业务标识"),
        ("attachment", "user_id", sa.Integer(), "所属用户ID"),
        ("attachment", "original_object_name", sa.String(length=1024), "原文件 MinIO 对象名"),
        ("attachment", "markdown_object_name", sa.String(length=1024), "解析后 Markdown 对象名"),
        ("attachment", "error_message", sa.Text(), "最近一次附件处理错误"),
        ("attachment", "deleted_at", sa.DateTime(timezone=True), "删除时间"),
        ("conversation", "parent_conversation_id", sa.Integer(), "父会话ID"),
        ("conversation", "deleted_at", sa.DateTime(timezone=True), "软删除时间"),
        ("message", "msg_metadata", sa.JSON(), "单次输入消息元数据"),
    )
    for table_name, column_name, column_type, comment in comments:
        op.alter_column(
            table_name,
            column_name,
            existing_type=column_type,
            comment=comment,
        )


def _restore_previous_comments() -> None:
    """恢复 0005 之前已有字段的注释。"""
    comments = (
        ("agent_run", "agent_status", sa.String(length=32), "运行状态"),
        ("agent_run", "run_metadata", sa.JSON(), None),
        ("attachment", "file_id", sa.String(length=36), None),
        ("attachment", "user_id", sa.Integer(), "用户ID"),
        ("attachment", "original_object_name", sa.String(length=1024), "MinIO对象路径"),
        ("attachment", "markdown_object_name", sa.String(length=1024), None),
        ("attachment", "error_message", sa.Text(), None),
        ("attachment", "deleted_at", sa.DateTime(timezone=True), None),
        ("conversation", "parent_conversation_id", sa.Integer(), None),
        ("conversation", "deleted_at", sa.DateTime(timezone=True), None),
        ("message", "msg_metadata", sa.JSON(), None),
    )
    for table_name, column_name, column_type, comment in comments:
        op.alter_column(
            table_name,
            column_name,
            existing_type=column_type,
            comment=comment,
        )
