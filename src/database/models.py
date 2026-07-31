import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
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

    id = Column(Integer, primary_key=True, autoincrement=True, comment="消息ID")
    conversation_id = Column(Integer, ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, comment="会话ID")
    agent_run_id = Column(String(64), ForeignKey("agent_run.id", ondelete="SET NULL"), nullable=True, comment="运行ID")
    role = Column(String(16), nullable=False, comment="消息角色")
    content = Column(Text, nullable=False, default="", comment="文本消息内容")
    image_content = Column(Text, nullable=True, comment="图像消息内容")

    status = Column(String(16), nullable=False, default="completed", comment="消息状态，是刚开始，还是执行中还是结束啥的")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    message_type = Column(String(30), default="text", comment="消息类型，是普通文本还是工具调用")

    request_id = Column(String(64), nullable=True, index=True, comment="Request ID for idempotency")

    conversation = relationship("Conversation", back_populates="messages")
    # FIXME: 恢复 AgentRun.messages 对应的反向关系，避免 ORM mapper 初始化失败。
    agent_run = relationship("AgentRun", back_populates="messages")
    tool_calls = relationship("ToolCall", back_populates="message", cascade="all, delete-orphan", order_by="ToolCall.tool_sequence")


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


class ScriptProject(Base):
    __tablename__ = "script_project"
    __table_args__ = (
        UniqueConstraint(
            "uid",
            "workspace_key",
            name="uq_script_project_uid_workspace_key",
        ),
    )

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="剧本项目ID",
    )
    uid = Column(
        String(64),
        ForeignKey("user.uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属用户ID",
    )
    workspace_key = Column(
        String(128),
        nullable=False,
        comment="前端工作区稳定标识",
    )
    title = Column(String(255), nullable=False, default="", comment="项目标题")
    description = Column(Text, nullable=False, default="", comment="项目描述")
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

    user = relationship("User")
    episodes = relationship(
        "Episode",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Episode.number",
    )
    characters = relationship(
        "Character",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Character.name",
    )


class Episode(Base):
    __tablename__ = "episode"
    __table_args__ = (
        CheckConstraint("number > 0", name="ck_episode_number_positive"),
        UniqueConstraint(
            "project_id",
            "number",
            name="uq_episode_project_number",
        ),
    )

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Episode ID",
    )
    project_id = Column(
        String(64),
        ForeignKey("script_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属剧本项目ID",
    )
    number = Column(Integer, nullable=False, comment="分集序号")
    title = Column(String(255), nullable=False, default="", comment="分集标题")
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

    project = relationship("ScriptProject", back_populates="episodes")
    outline = relationship(
        "EpisodeOutline",
        back_populates="episode",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )
    script = relationship(
        "EpisodeScript",
        back_populates="episode",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )
    storyboard_frames = relationship(
        "StoryboardFrame",
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="StoryboardFrame.position",
    )


class EpisodeOutline(Base):
    __tablename__ = "episode_outline"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_episode_outline_revision_positive"),
        UniqueConstraint(
            "episode_id",
            name="uq_episode_outline_episode",
        ),
    )

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="分集大纲ID",
    )
    episode_id = Column(
        String(64),
        ForeignKey("episode.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属Episode ID",
    )
    content_markdown = Column(
        Text,
        nullable=False,
        default="",
        comment="Markdown格式的大纲正文",
    )
    revision = Column(
        Integer,
        nullable=False,
        default=1,
        comment="大纲乐观锁版本号",
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

    episode = relationship("Episode", back_populates="outline")


class EpisodeScript(Base):
    __tablename__ = "episode_script"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_episode_script_revision_positive"),
        CheckConstraint(
            "format_version > 0",
            name="ck_episode_script_format_version_positive",
        ),
    )
    episode_id = Column(
        String(64),
        ForeignKey("episode.id", ondelete="CASCADE"),
        primary_key=True,
        comment="所属Episode ID",
    )
    revision = Column(
        Integer,
        nullable=False,
        default=1,
        comment="剧本乐观锁版本号",
    )
    format_version = Column(
        Integer,
        nullable=False,
        default=1,
        comment="关系型剧本格式版本",
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

    episode = relationship("Episode", back_populates="script")
    scenes = relationship(
        "ScriptScene",
        back_populates="script",
        cascade="all, delete-orphan",
        order_by="ScriptScene.position",
    )


class Character(Base):
    __tablename__ = "character"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "name",
            name="uq_character_project_name",
        ),
    )

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="角色ID",
    )
    project_id = Column(
        String(64),
        ForeignKey("script_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属剧本项目ID",
    )
    name = Column(String(255), nullable=False, comment="角色名称")
    role = Column(String(128), nullable=False, default="", comment="角色定位")
    description = Column(Text, nullable=False, default="", comment="角色说明")
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

    project = relationship("ScriptProject", back_populates="characters")
    lines = relationship("ScriptLine", back_populates="character")


class ScriptScene(Base):
    __tablename__ = "script_scene"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_script_scene_position"),
        CheckConstraint(
            "interior IN ('interior', 'exterior', 'interior_exterior')",
            name="ck_script_scene_interior",
        ),
        CheckConstraint(
            "time_of_day IN ('day', 'night', 'dawn', 'dusk')",
            name="ck_script_scene_time_of_day",
        ),
        UniqueConstraint(
            "episode_id",
            "position",
            name="uq_script_scene_episode_position",
        ),
        UniqueConstraint(
            "episode_id",
            "scene_number",
            name="uq_script_scene_episode_scene_number",
        ),
    )

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="场景ID",
    )
    episode_id = Column(
        String(64),
        ForeignKey("episode_script.episode_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属Episode剧本ID",
    )
    position = Column(Integer, nullable=False, comment="场景在剧本中的顺序")
    scene_number = Column(String(32), nullable=True, comment="制作场景号，如12A")
    interior = Column(
        String(32),
        nullable=False,
        default="interior",
        comment="内景、外景或内外景",
    )
    location = Column(Text, nullable=False, default="", comment="场景地点")
    time_of_day = Column(
        String(64),
        nullable=False,
        default="day",
        comment="白天、夜晚、黎明或黄昏",
    )
    synopsis = Column(Text, nullable=False, default="", comment="场景摘要")
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

    script = relationship("EpisodeScript", back_populates="scenes")
    lines = relationship(
        "ScriptLine",
        back_populates="scene",
        cascade="all, delete-orphan",
        foreign_keys="ScriptLine.scene_id",
        order_by="ScriptLine.position",
    )


class ScriptLine(Base):
    __tablename__ = "script_line"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_script_line_position"),
        CheckConstraint(
            "kind IN ("
            "'action', 'character', 'parenthetical', 'dialogue', "
            "'beat', 'transition'"
            ")",
            name="ck_script_line_kind",
        ),
        UniqueConstraint(
            "scene_id",
            "position",
            name="uq_script_line_scene_position",
        ),
    )

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="剧本语义行ID",
    )
    scene_id = Column(
        String(64),
        ForeignKey("script_scene.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属场景ID",
    )
    position = Column(
        Integer,
        nullable=False,
        comment="语义行在场景内的顺序，不是排版后的物理行号",
    )
    kind = Column(
        String(32),
        nullable=False,
        comment="动作、角色提示、括注、对白、节拍或转场",
    )
    content = Column(Text, nullable=False, default="", comment="语义行文本内容")
    character_id = Column(
        String(64),
        ForeignKey("character.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="角色提示或对白关联的项目角色",
    )
    cue_line_id = Column(
        String(64),
        ForeignKey("script_line.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="对白或括注所关联的角色提示行",
    )
    dialogue_group_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="关联连续对白或双栏对白的稳定分组ID",
    )
    origin = Column(
        String(32),
        nullable=True,
        comment="内容来源，如generated、manual或ai",
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

    scene = relationship(
        "ScriptScene",
        back_populates="lines",
        foreign_keys=[scene_id],
    )
    character = relationship("Character", back_populates="lines")
    cue_line = relationship(
        "ScriptLine",
        remote_side=[id],
        back_populates="dialogue_lines",
        foreign_keys=[cue_line_id],
    )
    dialogue_lines = relationship(
        "ScriptLine",
        back_populates="cue_line",
        foreign_keys=[cue_line_id],
    )


class StoryboardFrame(Base):
    __tablename__ = "storyboard_frame"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_storyboard_frame_position"),
        UniqueConstraint(
            "episode_id",
            "position",
            name="uq_storyboard_frame_episode_position",
        ),
    )

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="分镜帧ID",
    )
    episode_id = Column(
        String(64),
        ForeignKey("episode.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属Episode ID",
    )
    position = Column(Integer, nullable=False, comment="分镜顺序")
    title = Column(String(255), nullable=False, default="", comment="分镜标题")
    description = Column(Text, nullable=False, default="", comment="分镜描述")
    image_url = Column(Text, nullable=True, comment="分镜图片地址")
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

    episode = relationship("Episode", back_populates="storyboard_frames")


class StylePortfolio(Base):
    __tablename__ = "style_portfolio"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="风格资产包ID")
    skill_id = Column(Integer, ForeignKey("skill.id", ondelete="CASCADE"), unique=True, nullable=False, comment="所属技能ID")
    style_text = Column(Text, nullable=False, default="", comment="风格说明")
    reference_cases = Column(JSON, nullable=False, default=list, comment="参考案例")
    visual_language = Column(JSON, nullable=False, default=dict, comment="色彩、镜头、构图、元素等视觉语言")
    narrative_patterns = Column(JSON, nullable=False, default=dict, comment="叙事结构与场景推进模式")
    style_assets = Column(JSON, nullable=False, default=dict, comment="示例、规则、禁忌等风格资产")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    created_by = Column(String(64), nullable=True, comment="资源包创建记录")
    updated_by = Column(String(64), nullable=True, comment="资源包修改记录")
    skill = relationship("Skill", back_populates="style_portfolio")


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
    style_portfolio = relationship("StylePortfolio", back_populates="skill", uselist=False, cascade="all, delete-orphan")


class Attachment(Base):
    __tablename__ = "attachment"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="附件ID")
    uid = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    conversation_id = Column(Integer, ForeignKey("conversation.id", ondelete="SET NULL"), nullable=True, comment="来源会话ID")
    status = Column(String(16), nullable=False, default="pending", comment="附件状态")
    attachment_name = Column(String(255), nullable=False, comment="文件名")
    attachment_type = Column(String(128), nullable=False, comment="文件类型")
    attachment_size = Column(Integer, nullable=False, comment="文件大小")
    attachment_path = Column(String(1024), nullable=False, comment="MinIO对象路径")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")


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
