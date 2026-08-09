from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .base import Base


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="用户自增ID")
    # FIXME: 用户唯一登录账号统一为邮箱，不再维护重复的账号字段。
    email = Column(String(255), unique=True, index=True, nullable=False, comment="登录邮箱")
    uid = Column(String, nullable=False, unique=True, index=True, comment="登录标识")  

    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(
        ), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class Conversation(Base):
    __tablename__ = "conversation"
    __table_args__ = (
        Index(
            "ix_conversation_thread_list",
            "uid",
            "parent_conversation_id",
            "deleted_at",
            "updated_at",
            "id",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="会话表主键")
    uid = Column(String(64), index=True, nullable=False, comment="uid")
    thread_id = Column(String(64), unique=True, index=True, nullable=False, comment="会话的thread_id")
    parent_conversation_id = Column(
        Integer,
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="父会话ID",
    )
    agent_id = Column(String(64), index=True, nullable=False, comment="当前会话绑定的agent")
    title = Column(String(255), nullable=False, comment="会话标题")
    summary = Column(Text, nullable=True, comment="会话摘要")
    conversation_metadata = Column(JSON, nullable=False, default=dict, comment="会话元数据")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment="软删除时间")

    parent = relationship(
        "Conversation",
        remote_side=[id],
        back_populates="children",
    )
    children = relationship(
        "Conversation",
        back_populates="parent",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "message"
    __table_args__ = (
        Index("ix_message_conversation_id_id", "conversation_id", "id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="消息ID")
    conversation_id = Column(Integer, ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, comment="会话ID")
    agent_run_id = Column(String(64), ForeignKey("agent_run.id", ondelete="SET NULL"), nullable=True, comment="运行ID")
    role = Column(String(16), nullable=False, comment="消息角色")
    content = Column(Text, nullable=False, default="", comment="文本消息内容")
    image_content = Column(Text, nullable=True, comment="图像消息内容")
    msg_metadata = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="单次输入消息元数据",
    )

    status = Column(String(16), nullable=False, default="completed", comment="消息状态，是刚开始，还是执行中还是结束啥的")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    message_type = Column(String(30), default="text", comment="消息类型，是普通文本还是工具调用")

    request_id = Column(String(64), nullable=True, index=True, comment="Request ID for idempotency")

    conversation = relationship("Conversation", back_populates="messages")
    # FIXME: 恢复 AgentRun.messages 对应的反向关系，避免 ORM mapper 初始化失败。
    agent_run = relationship("AgentRun", back_populates="messages")
    tool_calls = relationship("ToolCall", back_populates="message", cascade="all, delete-orphan", order_by="ToolCall.tool_sequence")
    attachment_links = relationship(
        "MessageAttachment",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="MessageAttachment.position",
    )


class ToolCall(Base):
    __tablename__ = "tool_call"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="工具调用ID")
    message_id = Column(Integer, ForeignKey("message.id", ondelete="CASCADE"), nullable=False, comment="消息ID")
    tool_sequence = Column(Integer, nullable=False, comment="工具调用顺序")
    tool_call_id = Column(String(255), nullable=True, comment="模型返回的工具调用ID")
    tool_name = Column(String(255), nullable=False, comment="工具名称")
    tool_arguments = Column(JSON, nullable=False, default=dict, comment="工具参数")
    tool_input = Column(JSON , nullable=True, comment="工具输入")
    tool_result = Column(Text, nullable=True, comment="工具结果")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")

    message = relationship("Message", back_populates="tool_calls")


class AgentRun(Base):
    __tablename__ = "agent_run"
    __table_args__ = (
        Index(
            "ix_agent_run_conversation_status",
            "conversation_id",
            "agent_status",
        ),
    )

    id = Column(String(64), primary_key=True, comment="运行ID")
    thread_id = Column(String(64), index=True, nullable=False, comment="会话ID")
    conversation_id = Column(Integer, ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, comment="会话ID")
    uid = Column(String(64), ForeignKey("user.uid", ondelete="CASCADE"), nullable=False, comment="用户ID")
    agent_id = Column(String(128), nullable=False, comment="智能体ID")
    run_type = Column(
        String(32),
        nullable=False,
        default="chat",
        server_default="chat",
        index=True,
        comment="运行类型 chat, subagent",
    )
    agent_status = Column(String(32), nullable=False, default="pengding", comment="运行状态 pending, running, cancel_requested, completed, failed, cancelled")

    trigger_message_id = Column(Integer, nullable=True, comment="Input message ID")
    request_id = Column(String(128), unique=True, index=True, nullable=True, comment="请求ID")
    parent_run_id = Column(String(64), nullable=True, index=True, comment="当前runid的父id")
    run_metadata = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="单次运行元数据",
    )

    error = Column(Text, nullable=True, comment="错误信息")
    error_type = Column(String(64), nullable=True, comment="错误信息类型")
    started_at = Column(DateTime(timezone=True), nullable=True, comment="开始时间")
    finished_at = Column(DateTime(timezone=True), nullable=True, comment="结束时间")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    user = relationship("User")
    messages = relationship("Message", back_populates="agent_run")


class Agent(Base):
    __tablename__ = "agent"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="智能体ID")
    slug = Column(String(128), unique=True, index=True, nullable=False, comment="URL 标识")
    backend_id = Column(String(128), nullable=False, comment="虚拟文件系统")
    name = Column(String(128), nullable=False, comment="智能体名称")
    role = Column(String(32), nullable=False, default="orchestrator", comment="智能体角色")
    description = Column(Text, nullable=False, default="", comment="智能体描述")
    agent_config = Column(JSON, nullable=False, default=dict, comment="智能体配置")
    internal_only = Column(Boolean, nullable=False, default=True, comment="是否仅内部可见")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class Skill(Base):
    __tablename__ = "skill"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="技能ID")
    uid = Column(String(64), ForeignKey("user.uid", ondelete="SET NULL"), nullable=True, comment="创建用户ID")
    slug = Column(String(128), unique=True, index=True, nullable=False, comment="URL 友好的稳定标识")
    name = Column(String(128), nullable=False, comment="技能名称")
    skill_type = Column(String(32), nullable=False, default="general", comment="技能类型")
    description = Column(Text, nullable=False, default="", comment="技能描述")
    instruction = Column(Text, nullable=False, default="", comment="技能说明")
    skill_assets = Column(JSON, nullable=False, default=dict, comment="示例、规则、模板等技能资产")
    visibility = Column(String(16), nullable=False, default="private", comment="可见范围")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    created_by = Column(String(64), nullable=True, comment="skill创建记录")
    updated_by = Column(String(64), nullable=True, comment="skill修改记录")
        
    user = relationship("User")


class Attachment(Base):
    __tablename__ = "attachment"
    __table_args__ = (
        UniqueConstraint("file_id", name="uq_attachment_file_id"),
        Index("ix_attachment_user_library", "user_id", "deleted_at", "id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="附件ID")
    file_id = Column(String(36), nullable=False, comment="附件业务标识")
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, comment="所属用户ID")
    file_name = Column(String(255), nullable=False, comment="文件名")
    content_type = Column(String(128), nullable=False, comment="文件 MIME 类型")
    file_size = Column(Integer, nullable=False, comment="文件字节数")
    object_name = Column(String(1024), nullable=False, comment="当前 MinIO 对象名")
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment="删除时间")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    user = relationship("User")
    message_links = relationship(
        "MessageAttachment",
        back_populates="attachment",
        passive_deletes=True,
    )


class MessageAttachment(Base):
    """记录消息对用户附件的引用。"""

    __tablename__ = "message_attachment"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "position",
            name="uq_message_attachment_position",
        ),
        Index("ix_message_attachment_attachment_id", "attachment_id"),
    )

    message_id = Column(
        Integer,
        ForeignKey("message.id", ondelete="CASCADE"),
        primary_key=True,
    )
    attachment_id = Column(
        Integer,
        ForeignKey("attachment.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position = Column(Integer, nullable=False)

    message = relationship("Message", back_populates="attachment_links")
    attachment = relationship("Attachment", back_populates="message_links")


class KnowledgeBase(Base):
    """用户拥有的逻辑知识库。"""

    __tablename__ = "knowledge_base"

    kb_id = Column(String(128), primary_key=True, comment="知识库业务标识")
    uid = Column(
        String(128),
        ForeignKey("user.uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属用户",
    )
    name = Column(String(255), nullable=False, comment="知识库名称")
    description = Column(Text, nullable=False, default="", comment="知识库描述")
    status = Column(
        String(32),
        nullable=False,
        default="active",
        index=True,
        comment="知识库状态",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    files = relationship(
        "KnowledgeFile",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )


class KnowledgeFile(Base):
    """知识库中的独立文件及其解析生命周期。"""

    __tablename__ = "knowledge_file"

    file_id = Column(String(64), primary_key=True, comment="文件业务标识")
    kb_id = Column(
        String(128),
        ForeignKey("knowledge_base.kb_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属知识库",
    )
    original_file_name = Column(String(512), nullable=False, comment="原始文件名")
    original_object_name = Column(
        String(1024),
        nullable=False,
        unique=True,
        comment="原文件 MinIO 对象名",
    )
    markdown_object_name = Column(
        String(1024),
        nullable=True,
        comment="解析后 Markdown 对象名",
    )
    content_type = Column(String(128), nullable=False, comment="原文件 MIME 类型")
    file_size = Column(Integer, nullable=False, comment="原文件字节数")
    status = Column(
        String(32),
        nullable=False,
        default="uploaded",
        index=True,
        comment="uploaded/parsing/parsed/indexing/indexed/failed",
    )
    error_message = Column(Text, nullable=True, comment="最近一次处理错误")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    knowledge_base = relationship("KnowledgeBase", back_populates="files")


class KnowledgeEmbeddingBinding(Base):
    """持久化知识库唯一的 Embedding 与向量集合契约。"""

    __tablename__ = "knowledge_embedding_binding"

    uid = Column(
        String(128),
        ForeignKey("user.uid", ondelete="CASCADE"),
        primary_key=True,
    )
    kb_id = Column(
        String(128),
        ForeignKey("knowledge_base.kb_id", ondelete="CASCADE"),
        primary_key=True,
    )
    collection_name = Column(String(64), nullable=False)
    embedding_model_spec = Column(String(255), nullable=False)
    embedding_dimension = Column(Integer, nullable=False)
    embedding_batch_size = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Knowledge(Base):
    __tablename__ = "knowledge"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="知识库ID")
    uid = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    kind = Column(String(32), nullable=False, default="screenplay", comment="知识库类型")
    title = Column(String(255), nullable=False, comment="标题")
    summary = Column(Text, nullable=False, default="", comment="摘要")
    content_text = Column(Text, nullable=True, comment="文本内容")
    knowlege_file_name = Column(String(512), nullable=True, comment="文件名")
    knowlege_file_name_og = Column(String(512), nullable=True, comment="原始文件名")
    knowlege_file_path = Column(String(1024), nullable=True, comment="原始文件MinIO路径")
    knowlege_file_minio_url = Column(String(1024), nullable=True, comment="原始文件MinIO URL")
    knowlege_markdown = Column(String(1024), nullable=True, comment="解析后Markdown文件路径")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")
