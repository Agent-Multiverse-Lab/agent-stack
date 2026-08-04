# 用户附件生命周期与消息引用 API 设计

状态：本轮 UUID4 文件标识、消息 metadata 与 Worker 透传、已有消息引用读取已实现。
Agent Run 不新增 MessageAttachment。临时文件转正、Markdown 解析与过期清理仍是后续
独立附件处理链路，不纳入本轮实现。

相关代码：

- `server/router/thread_router.py`
- `server/router/agent_router.py`
- `server/router/library_router.py`
- `server/entities/agent.py`
- `server/entities/thread.py`
- `server/entities/library.py`
- `server/service/library_service.py`
- `server/service/thread_service.py`
- `server/service/input_message_service.py`
- `server/worker.py`
- `src/database/models.py`
- `src/database/repositories/attachment_repository.py`
- `src/database/repositories/conversation_repository.py`
- `src/database/repositories/message_attachment_repository.py`
- `migrate/versions/0003_attachment_library.py`
- `src/storage/minio.py`

## 1. 目标与核心结论

附件是用户拥有、可被消息重复引用的独立文件资源。Conversation 不拥有附件，
Message 通过关联表记录本次使用了哪些附件。

目标关系：

```text
User 1 ───── N Conversation
Conversation 1 ───── N Message

User 1 ───── N Attachment
Message 1 ───── N MessageAttachment N ───── 1 Attachment
```

核心结论：

- `Attachment` 的所有者是 User，不保存 `conversation_id` 或 `message_id`。
- `MessageAttachment` 表结构保留用于表达 Message 对 Attachment 的显式引用，但当前
  Agent Run 创建链路不新增引用行。
- 上传但未发送消息的文件保存在 MinIO 临时目录，并以 `pending` 状态落库。
- 临时上传时生成 UUID4 `file_id`；它是客户端和 `msg_metadata` 使用的文件标识，
  不是 Attachment 的数据库主键。
- 附件上传与 Conversation 创建、Agent Run 创建是独立请求；上传接口不接收
  `thread_id`，也不提前创建任何会话或消息关系。
- 前端暂存上传接口返回的 `file_id`，在真实触发 Run 时通过消息 `msg_metadata` 回传；
  后端只把 metadata 保存到 Message，不查询 Attachment 或创建 MessageAttachment。
- Worker 默认收到的 `AgentInputMsg.msg_metadata` 已包含文件 ID，不查询、转移、解析
  或清理附件。
- PostgreSQL 是附件元数据、状态和引用关系的唯一来源；不能扫描 MinIO 重建列表。

## 2. 改造前实现与真实缺口

本轮改造前，上传接口执行：

```text
POST /api/chat/attachment/tmp/upload
  -> 上传原文件到旧临时对象路径
  -> 创建 Attachment(status="pending")
  -> 返回 Attachment 数据库整数主键
```

改造前存在以下问题：

1. `Attachment.conversation_id` 把附件直接指向 Conversation。
2. `pending -> attached` 表达的是对话绑定，而不是文件处理状态。
3. `prepare_attachments_for_conversation(...)` 会把文件复制到包含 Conversation ID
   的对象路径，但该函数当前没有调用方。
4. `Message` 与 Attachment 之间没有持久关联。
5. 临时上传响应仍返回 Attachment 数据库整数主键，没有独立的 UUID4 文件标识。
6. `AgentInputMsg.msg_metadata` 尚未统一使用 `file_ids` 传递临时文件标识。
7. Thread 详情响应没有每条消息的附件列表。
8. 当前 Library 响应通过 Conversation relationship 返回 `thread_id`，与用户级附件
   所有权冲突。
9. 临时对象路径中的随机 UUID 没有作为可查询的文件标识持久化。
10. AttachmentMiddleware 继续保留为 Agent 层的显式扩展点，但当前只尝试注入路径，
    且未接入任何 Agent。

因此，现有 Library CRUD 可以保留其基本 API 形状，但临时文件标识和消息输入 metadata
必须按本设计调整。

## 3. 目标数据模型

### 3.1 Conversation

Conversation 只保存对话本身：

```text
id
uid
thread_id
parent_conversation_id
agent_id
title
summary
conversation_metadata
deleted_at
created_at
updated_at
```

Conversation 不增加 Attachment relationship，也不保存附件 ID 列表。

### 3.2 Message

Message 继续通过 `conversation_id` 属于一个 Conversation，并增加非空 JSON
`msg_metadata` 保存单次输入消息元数据。`file_ids` 随该字段持久化，供 Worker 重建
`AgentInputMsg` 时原样透传。当前 Agent Run 链路不把这些 ID 转换为数据库关联。

新增 ORM relationship `attachment_links`，用于按 `position` 读取 MessageAttachment；
不在 Message 表增加单值 `attachment_id` 或专用附件 ID 列表字段。

### 3.3 MessageAttachment

新增关联模型：

```python
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
```

约束语义：

- 联合主键禁止同一 Message 重复引用同一个 Attachment。
- `position` 保留用户提交附件时的顺序。
- 一条 Message 可以引用多个 Attachment。
- 同一 Attachment 可以被多个 Message、多个 Thread 引用。
- 删除 Message 时只级联删除引用行，不删除 Attachment。
- Attachment 默认通过 `deleted_at` 删除，因此历史引用继续存在。

### 3.4 Attachment

目标 Attachment 字段：

```text
id                      Integer 数据库内部主键，用于外键和 Library 游标
file_id                 String(36)，保存 UUID4 对外文件标识，唯一且不可为空
user_id                 用户数据库主键，FK -> user.id
status                  pending/uploaded/parsing/parsed/failed
attachment_name         用户看到的文件名
attachment_type         原文件 MIME 类型
attachment_size         原文件字节数
original_object_name    当前原文件 MinIO object name
markdown_object_name    解析后 Markdown 对象名，可为空
error_message           最近一次附件处理错误，可为空
deleted_at              用户删除时间，可为空
created_at
updated_at
```

从 Attachment 删除：

```text
conversation_id
conversation relationship
```

现有字段直接重命名：

```text
uid             -> user_id
attachment_path -> original_object_name
```

`user_id` 明确表示它引用 `User.id`，避免与字符串业务标识 `User.uid` 混淆。
`original_object_name` 明确表示它不是文件系统路径或可访问 URL。
`file_id` 在临时上传开始前通过 `str(uuid4())` 生成，并在 Attachment 生命周期内保持
不变。UUID4 是字符串值的生成和校验规则，不是 PostgreSQL UUID 字段类型，也不替代
`user_id` 所有权校验。

不向 Attachment 增加：

```text
message_id
origin
parsed_text
access_url
suffix
category
```

原因：

- Message 使用关系由 MessageAttachment 表表达。
- Markdown 正文保存在 MinIO，数据库只保存对象名。
- Access URL 是短时签名结果，按请求生成。
- suffix 和 category 分别从文件名、MIME 派生。
- 本期只处理用户上传附件，不引入 generated 来源字段。

索引：

```text
attachment(user_id, deleted_at, id)
attachment(status, created_at)
attachment(file_id) UNIQUE
message_attachment(message_id, position)
message_attachment(attachment_id)
```

第一组服务 Library 游标列表，第二组为后续独立 pending 清理预留；关联表索引分别服务
Thread 消息批量加载和反向引用检查。本轮不新增 Worker 清理任务。

## 4. 附件状态与对象路径

### 4.1 状态定义

| 状态 | 原文件位置 | Markdown | 含义 |
| --- | --- | --- | --- |
| `pending` | 临时目录 | 无 | 已上传，尚未进入后续转正和解析流程 |
| `uploaded` | 用户持久目录 | 无 | 原文件已转正，等待 Parser |
| `parsing` | 用户持久目录 | 生成中 | 独立附件处理流程正在调用 Parser |
| `parsed` | 用户持久目录 | 已保存 | 可直接供 Agent 使用 |
| `failed` | 用户持久目录 | 无或不可用 | Parser 失败，保留原文件和错误信息 |

状态转换：

```text
pending -> uploaded -> parsing -> parsed
                       \-> failed -> parsing
```

`deleted_at` 与处理状态正交，不增加 `deleted` 状态。删除后禁止新 Message 引用，
Library 不再展示，但已有 MessageAttachment 仍可返回不可用占位信息。

禁止恢复 `attached` 状态，因为是否被 Message 引用应由 MessageAttachment 表查询，
不属于文件处理生命周期。

上述转正和解析状态是完整生命周期的目标定义，不代表由 Agent Run Worker 执行。本轮
UUID4 改造只创建 `pending` 记录并建立消息引用；后续处理入口需单独设计和确认。

### 4.2 MinIO 对象路径

附件使用专用私有 Bucket：

```text
attachments
```

以下均为 `attachments` Bucket 内的 object name，不是 URL。

继续使用现有临时上传入口。上传阶段 object name：

```text
tmp/chat/attachment/{user_id}/{file_id}/{safe_file_name}
```

首次被 Message 使用后转入用户级持久目录：

```text
{user_id}/{file_id}/original/{safe_file_name}
{user_id}/{file_id}/parsed/document.md
```

因此完整 MinIO 位置分别是
`attachments/{user_id}/{file_id}/original/{safe_file_name}` 和
`attachments/{user_id}/{file_id}/parsed/document.md`。临时路径和持久路径始终复用同一个
UUID4 `file_id`；Integer `Attachment.id` 不进入 MinIO 对象名。持久位置不包含
`thread_id` 或 Conversation 数据库主键。启动消息只是文件转正的触发条件，不改变
User 对 Attachment 的所有权。

### 4.3 转移语义

MinIO 没有跨对象名的事务性 rename。“转移”定义为：

1. 从临时对象服务端复制到确定性的持久对象名。
2. 确认目标对象复制成功。
3. 更新 Attachment 的 `original_object_name` 和 `status="uploaded"` 并提交。
4. 数据库提交成功后删除临时对象。

不得先删除临时对象再提交数据库。若最后一步删除失败，持久对象和数据库仍然正确，
残留临时对象由过期清理任务回收。

`src/storage/minio.py` 应提供薄的异步 copy 操作，Service 不应通过
download + upload 把整个文件加载进应用进程内存。

## 5. 完整执行流程

### 5.1 临时上传

保留接口：

```http
POST /api/chat/attachment/tmp/upload
Content-Type: multipart/form-data
```

流程：

1. Router 校验文件数量、扩展名、MIME 和大小。
2. 在应用层生成一个 UUID4 `file_id`。
3. 使用该 `file_id` 构造 MinIO 临时对象名并上传原文件。
4. 创建 `Attachment(status="pending")`，保存 `file_id`、当前用户、原文件元数据和
   临时对象名。
5. 提交数据库并返回 `file_id`。
6. 数据库写入失败时删除本次已经上传的临时对象。

上传阶段不执行 Parser、不创建 MessageAttachment、不要求 Thread ID，也不把 pending
文件展示在正式 Library 列表中。

上传响应只返回客户端需要的字段：

```python
class UploadedAttachmentResponse(BaseModel):
    """临时上传成功的用户附件。"""

    id: str  # Attachment.file_id 的 UUID4 字符串
    file_name: str
    content_type: str
    file_size: int
    category: str
    status: str
    access_url: str
```

不返回 MinIO `file_key`、Parser 名称、客户端伪造的 parse_status 或 parsed_text。

### 5.2 真实触发 Run 时保存消息 metadata

附件上传完成后，前端只暂存返回的 UUID4 文件 ID。创建 Conversation 本身不消费这些
ID，也不建立 Conversation 与 Attachment 的直接关系。用户正式发送消息时，前端通过：

```http
POST /api/agent/runs
```

把 `thread_id`、消息内容以及文件 ID 一起提交。文件 ID 放入输入消息的
`AgentInputMsg.msg_metadata`：

```python
msg_metadata = {
    "file_ids": [
        "759b114e-90d6-42d2-a052-bdccaa40c7b6",
        "0a77af9d-e5cf-46f0-b519-bf9eb96df0ca",
    ]
}
```

本设计中的“会话正式开始”定义为后端接受 Run 请求并成功持久化 AgentRun，而不是仅创建
Conversation，也不是等待 Worker 把 Run 状态改成 `running`。后端处理顺序为：

```text
校验 thread_id 与当前用户
  -> 将 msg_metadata 作为普通消息输入
  -> 创建触发 Message 并原样保存 msg_metadata
  -> 创建 AgentRun
  -> 同一事务提交
  -> 提交成功后入队
```

`create_agent_run_service(...)` 不解释 `file_ids` 的业务含义，不校验 Attachment 是否
存在或属于当前用户，也不创建 `MessageAttachment`。因此当前新消息的文件归属只体现在
`Message.msg_metadata` 中；Thread 响应中的 `attachments` 只会返回数据库中已经存在的
MessageAttachment 行。

### 5.3 Worker 边界

Worker 默认收到的 `AgentInputMsg.msg_metadata` 已经包含 `file_ids`。Worker 将 metadata
作为普通消息输入的一部分透传，不识别这些 ID 的业务含义，也不执行附件查询、权限
校验、MinIO 操作、转移、Parser、清理或 Attachment Service 调用。

### 5.4 Agent 输入

`file_ids` 是本次消息输入数据，不属于 Agent runtime configuration。附件 ID 只放在
`AgentInputMsg.msg_metadata`，不复制到 Run metadata，也不展开成文件路径或正文。

没有文本但 `file_ids` 非空时，输入仍然有效。既没有文本、图像也没有文件 ID 时继续
返回输入错误。

## 6. Thread 消息查询

Thread 详情按以下链路加载：

该链路只读取数据库中已经存在的 MessageAttachment；当前 Agent Run 创建流程不会产生
新的关联行。

```text
Conversation(thread_id + uid)
  -> 一页 Message
  -> 按 message_ids 批量查询 MessageAttachment
  -> 批量加载 Attachment
  -> 按 position 组装到各 Message
```

禁止在响应循环中逐条查询附件。Repository 应使用一条批量查询返回关联行和
Attachment，Service 负责按 `message_id` 分组。

`ThreadMessageResponse` 增加：

```python
class ThreadMessageAttachmentResponse(BaseModel):
    """历史消息引用的附件。"""

    id: str  # Attachment.file_id
    file_name: str
    content_type: str
    file_size: int
    status: str
    available: bool
    access_url: str | None


class ThreadMessageResponse(BaseModel):
    # 现有字段保持不变
    attachments: list[ThreadMessageAttachmentResponse]
```

当 Attachment 已删除时，MessageAttachment 仍然存在：

- `available=false`
- `access_url=null`
- 保留文件名、类型、大小和最后处理状态供历史展示
- Library 不再为该附件生成访问 URL

Conversation 软删除不删除 Message、MessageAttachment 或 Attachment。未来若物理删除
Message，只级联删除 MessageAttachment；Attachment 继续由用户 Library 管理。

## 7. Library API 调整

保留以下用户附件管理接口：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/libraries/attachments` | 列出或搜索正式用户附件 |
| `GET` | `/api/libraries/attachments/{attachment_id}` | 读取附件详情 |
| `PATCH` | `/api/libraries/attachments/{attachment_id}` | 修改展示文件名 |
| `DELETE` | `/api/libraries/attachments/{attachment_id}` | 删除附件 |

路径参数名暂保留 `attachment_id`，其值是 UUID4 `Attachment.file_id`，不是数据库整数
`Attachment.id`。所有 Library 响应中的附件 `id` 同样使用 `file_id`。

Library 列表只返回：

```text
Attachment.user_id == current_user.id
Attachment.deleted_at IS NULL
Attachment.status IN (uploaded, parsing, parsed, failed)
```

`pending` 是尚未正式使用的临时文件，不进入 Library。排序和 `before_id` 游标继续使用
`Attachment.id DESC`。

调整后的响应实体：

```python
class LibraryAttachmentItem(BaseModel):
    """用户附件 Library 中的一个文件。"""

    id: str  # Attachment.file_id
    file_name: str
    suffix: str
    content_type: str
    file_size: int
    category: str
    status: str
    parse_error: str | None
    access_url: str
    created_at: datetime
    updated_at: datetime
```

删除当前 `thread_id` 字段。Library 不暴露 `original_object_name`、
`markdown_object_name` 或 Markdown 签名 URL；Markdown 是 Agent 输入工件，不是公开
文件管理 API。

改名仍只修改 `attachment_name`，且不得修改后缀或移动 MinIO 对象。删除仍写
`deleted_at`，不在 HTTP 请求内同步删除原文件和 Markdown。

## 8. Repository 与 Service 边界

### 8.1 AttachmentRepository

AttachmentRepository 只负责 Attachment SQL：

- `create_pending_attachment(...)`：使用调用方生成的 `file_id` 创建临时上传记录。
- `list_library_attachments_for_user(...)`：读取正式 Library 列表。
- `get_library_attachment_by_file_id_for_user(...)`：按外部文件 ID 读取正式附件详情。
- `update_attachment_name(...)`：修改用户可见文件名。
- `soft_delete_attachment(...)`：写入 `deleted_at`。

所有按外部 ID 的读取和写入都必须同时带 `user_id`。删除
`mark_attachment_attached(...)`；Repository 不调用 MinIO 或 Parser。本轮不增加转正、
解析或定时清理 Repository 方法。

### 8.2 MessageAttachmentRepository

Repository 当前只负责
`list_attachments_by_message_ids(...)`，批量读取已有 MessageAttachment 的有序附件；
不提供 Agent Run 创建引用的方法。

Repository 不组装 HTTP 实体、不生成签名 URL、不加载 Markdown 正文。

### 8.3 Attachment Service

新增 `server/service/attachment_service.py`，使用模块函数，不创建无状态 Service 类：

- `upload_pending_attachments(...)`

该模块只协调临时上传所需的 Repository 和 MinioStorage：生成一次 UUID4 `file_id`，
使用它构造对象名、创建 `pending` 记录并返回同一个 ID。数据库写入失败时，只清理本次
上传产生的确定对象。该模块本轮不调用 Pipeline，也不承担 Library CRUD。

`server/service/agent_run_service.py` 中的 `create_agent_run_service(...)` 只创建 Message
和 AgentRun。它把 `msg_metadata` 原样保存到 Message，不导入 Attachment Repository，
也不校验、绑定或更新附件。

`server/service/library_service.py` 继续只承载列表、详情、改名和删除等 Library 用例，
对外返回 `Attachment.file_id`，不承担对话输入或 Worker 执行编排。

### 8.4 Router

- Thread Router 保留临时上传入口，只做 multipart 参数和 HTTP 错误映射。
- Agent Router 不增加顶层 `attachment_ids` 参数；`msg_metadata` 作为普通消息元数据
  进入 `create_agent_run_service(...)`。
- Library Router 继续调用函数式 Library Service。
- Router 不直接构造 MinIO 客户端、不执行 Parser、不写关联表 SQL。

### 8.5 Worker

Worker 只按现有流程恢复触发 Message，并把其中的 `msg_metadata` 作为普通输入数据传给
`AgentInputMsg`。即使 metadata 中存在 `file_ids`，Worker 也不查询 Attachment、不校验
附件权限、不读写 MinIO、不转正、不解析、不清理，也不调用 Attachment Service。

## 9. 并发、幂等与一致性

### 9.1 数据库事务

Message 和 AgentRun 必须同事务提交。任何一个失败都回滚，提交前不允许入队。

### 9.2 重复执行

- 每个上传文件在写入 MinIO 前只生成一次 UUID4 `file_id`。
- 临时对象名、Attachment 记录和上传响应必须使用同一个 `file_id`。
- `attachment.file_id` 唯一约束负责拒绝意外碰撞，创建后不得修改。
- 一次上传请求的网络级重试视为一次新上传，生成新的 `file_id`；本轮不按文件内容去重。
- Agent Run 不校验、去重或绑定 `msg_metadata` 中的文件 ID。

### 9.3 MinIO 与 PostgreSQL

两者不共享事务，操作顺序必须保证数据库不会指向已主动删除的唯一对象：

- 上传失败：不创建 Attachment。
- 上传成功、数据库失败：删除临时对象。
- 数据库提交成功：响应中的 `id` 必须等于记录中的 `file_id`，对象名也必须包含该值。

不得通过扫描整个 Bucket 作为正常恢复流程。后续转正、解析和孤儿清理需使用数据库
记录及确定对象名另行设计，不放入 Agent Run Worker。

## 10. Pending 保留与后续清理边界

上传后未发送消息的附件会保持 `pending`。本轮 UUID4 改造不新增 ARQ 定时任务、FastAPI
lifespan 定时器或 Agent Run Worker 清理逻辑。

后续若增加独立维护任务，只能按数据库记录有界选择候选项，基本条件为：

```text
status == pending
deleted_at IS NULL
created_at < now - ATTACHMENT_PENDING_TTL
NOT EXISTS MessageAttachment
```

TTL、调度器、删除顺序和重试语义必须在独立需求中确认后实现。正式 Attachment 的用户
删除仍使用 `deleted_at`，不复用 pending 物理清理语义。

## 11. 权限与删除语义

- 上传、引用、Library 管理和 Thread 查询都以认证用户为边界。
- Library 查询、改名和删除使用 `file_id + user_id`；UUID4 字符串不是授权凭证。
- 不存在、已删除和不属于当前用户的附件对外统一按不可用处理，避免泄露 ID。
- MessageAttachment 不能改变 Attachment 所有者。
- Agent Run 不根据 `msg_metadata` 判断 Attachment 的删除状态。
- Attachment 删除后不再生成原文件访问 URL。
- Conversation 软删除不触发附件删除。
- MinIO Bucket 保持私有，只返回短时签名原文件 URL。

## 12. 数据迁移设计

本设计替换当前尚未完成的 `0003_attachment_library.py` 附件方案。Upgrade：

1. 删除 `ix_attachment_conversation_id`。
2. 删除 Attachment 到 Conversation 的外键和 `conversation_id` 列。
3. 将 `uid` 重命名为 `user_id`，并明确其外键为 `user.id`。
4. 将 `attachment_path` 重命名为 `original_object_name`。
5. 增加 `file_id VARCHAR(36) NOT NULL` 及唯一约束；该值由应用通过
   `str(uuid4())` 在插入前生成，不设置数据库 server default。
6. 增加 `markdown_object_name VARCHAR(1024) NULL`。
7. 增加 `error_message TEXT NULL`。
8. 增加 `deleted_at TIMESTAMPTZ NULL`。
9. 保留并重新定义 status 为
   `pending/uploaded/parsing/parsed/failed`。
10. 创建 `message_attachment` 表及唯一约束和索引。
11. 为 Message 增加非空 JSON `msg_metadata`，默认值为 `{}`。
12. 创建 Library 和 pending 清理索引。

Downgrade 按相反顺序删除新增表、字段和索引，并恢复 Conversation 外键及索引。

本次不增加兼容字段、双写路径或旧 `attached` 状态映射。迁移执行前必须确认目标数据库
当前 revision；已经应用旧版 0003 的环境需要独立新 revision，不能修改已发布历史。
`Attachment.id`、`MessageAttachment.attachment_id` 和 `before_id` 游标继续使用 Integer，
不迁移为 UUID。

## 13. 本轮文件级实施计划

1. `src/database/models.py`
   - 为 Attachment 增加不可为空、唯一的 `String(36)` 类型 `file_id`；为 Message 增加
     `msg_metadata`；保留 Integer `id` 和现有外键。
2. `migrate/versions/0003_attachment_library.py`
   - 增加 `file_id`、`msg_metadata` 及相关约束，不改变 MessageAttachment 外键类型。
3. `src/database/repositories/attachment_repository.py`
   - 创建 pending 记录时接收 `file_id`，并让 Library 详情、改名和删除使用外部文件 ID。
4. `server/service/attachment_service.py`
   - 每个文件只生成一次 UUID4，复用于临时对象名、Attachment 记录和上传响应；本轮只
     保留临时上传编排。
5. `server/service/agent_run_service.py`
   - 保留 `create_agent_run_service(...)`，把 `msg_metadata` 原样持久化到 Message；
     不查询 Attachment，不创建 MessageAttachment。
6. `src/database/repositories/conversation_repository.py`
   - 创建触发 Message 时保存 `msg_metadata`。
7. `server/entities/agent.py`、`server/router/agent_router.py`
   - 删除顶层附件 ID 参数，使用输入消息的 `msg_metadata`。
8. `server/service/input_message_service.py`
   - 把 `file_ids` 视为有效输入并原样保留在 `msg_metadata`，不查询或展开附件内容。
9. `server/worker.py`
   - 只把持久化的 Message `msg_metadata` 传给 `AgentInputMsg`，不执行附件业务。
10. `server/entities/thread.py`、`server/entities/library.py`
   - 上传、Thread 消息和 Library 响应的附件 `id` 统一表示 UUID4 `file_id`；不新增
     `attachments` 顶层请求字段或 `AgentInputAttachment` 实体。
11. `server/service/thread_service.py`、`server/service/library_service.py`
   - 对外装配 `file_id`，内部关系和 Library 游标继续使用 Integer `id`。
12. `test/`
   - 覆盖 UUID4 字符串生成与复用、唯一约束、metadata 透传、外部响应 ID 和 Worker
     零附件操作边界。

`src/storage/minio.py` 不增加 copy，Parser、转正和定时清理也不在本轮实施计划内。

## 14. 验收标准

- 上传附件即产生 MinIO 临时对象和 pending Attachment，但不要求 Thread。
- 创建 Conversation 不建立任何附件关系。
- 上传响应 `id` 是合法 UUID4 字符串，并等于 `Attachment.file_id`。
- MinIO 临时对象名、数据库记录和响应复用同一个 `file_id`。
- `Attachment.id`、MessageAttachment 外键和 Library `before_id` 游标仍为 Integer。
- 未发送消息的 pending Attachment 不进入正式 Library。
- Agent Run 将 `msg_metadata` 原样保存，不增加顶层 `attachment_ids` 或 `attachments` 字段。
- Agent Run 不查询 Attachment，也不创建 MessageAttachment。
- Message 和 AgentRun 原子落库后才入队。
- Worker 只透传 `msg_metadata`，没有 Attachment Repository、Attachment Service、MinIO、
  Parser 或附件清理调用。
- Thread 详情按 Message 返回有序 attachments，不出现 N+1 查询。
- 删除 Conversation 不删除 Attachment。
- 删除 Attachment 后历史消息返回 `available=false`。
- Router 不定义 Pydantic 实体，不直接执行 SQL、Parser 或 MinIO 编排。
- Ruff、OpenAPI、Alembic upgrade/downgrade SQL、目标单元测试和
  `git diff --check` 通过。

## 15. 本期不做

- 不处理系统生成附件。
- 不增加文件夹、收藏、批量改名或内容编辑。
- 不在 Library API 暴露 Markdown 正文或对象名。
- 不扫描 MinIO 构造 Attachment、MessageAttachment 或清理列表。
- 不把附件正文放入 Agent runtime context 或 Run metadata。
- 不把 `Attachment.id`、MessageAttachment 外键或 Library 游标迁移为 UUID。
- 不在 Agent Run Worker 中增加任何附件操作。
- 不在本轮接入临时文件转正、Parser-to-Markdown 或 pending 定时清理。
