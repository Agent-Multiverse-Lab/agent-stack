# Thread（对话）管理 API 设计

状态：已实现。已完成目标单元测试、Ruff、Repository PostgreSQL SQL 编译及
Alembic upgrade/downgrade 离线 SQL 验证；真实 PostgreSQL 环境仍需在部署时执行迁移。

相关代码：

- `server/router/thread_router.py`
- `server/router/agent_router.py`
- `server/service/thread_service.py`
- `server/service/subagent_service.py`
- `server/worker.py`
- `src/database/models.py`
- `src/database/repositories/conversation_repository.py`
- `src/database/repositories/agent_run_repository.py`
- `src/database/repositories/attachment_repository.py`
- `src/database/manger.py`

## 1. 目标与结论

本项目中的 Thread 就是业务 `Conversation`，对外稳定标识为
`Conversation.thread_id`。`Conversation.id` 只用于数据库关联，不进入公开 URL。

`thread_router.py` 需要承担完整的对话资源 API，而不只是返回对话列表：

1. 创建对话。
2. 分页列出当前用户的顶层对话。
3. 按标题或摘要查找对话。
4. 加载指定对话、对话元数据、消息及每条消息对应的 Run 元数据。
5. 更新对话标题、摘要和用户元数据。
6. 删除对话。

核心结论：

- UI 展示的对话和历史消息以 PostgreSQL 中的 `Conversation`、`Message`、
  `AgentRun` 为唯一来源，不能从 Redis Stream 或 LangGraph Checkpoint 重建。
- 公开接口只暴露 `parent_conversation_id IS NULL` 的顶层对话；子智能体创建的内部
  Conversation 不进入用户对话列表，也不能通过公开详情接口直接读取。
- Router 只做请求校验、响应组装和异常到 HTTP 状态码的转换；查询、更新、删除的
  用例协调放在 `server/service/thread_service.py`，SQL 只放在 Repository。
- 首期删除采用软删除。HTTP 请求只让对话立即不可见，不在一个请求中同时硬删除
  PostgreSQL、MinIO、Redis、Sandbox 和 LangGraph Checkpoint。
- “附带的元数据”必须区分对话元数据和单次 Run 元数据，不能继续用一个
  `thread_metadata` 名称混合两种含义。

## 2. 实现基础与结果

### 2.1 已有能力

当前已经存在：

- `POST /api/chat/thread` 创建顶层 Conversation。
- `Conversation.conversation_metadata` 保存对话级元数据。
- `POST /api/agent/runs` 保存用户 `Message` 和对应 `AgentRun`。
- Worker 在 Run 完成后保存 assistant `Message`。
- `Message.agent_run_id` 可以把输入、输出消息关联到一次 Run。
- `Message` 已保存角色、正文、图像内容、消息类型、状态、`request_id` 和时间。
- `AgentRun` 已保存运行类型、运行状态、父 Run、错误和执行时间。
- `AsyncPostgresSaver` 当前安装版本提供
  `await checkpointer.adelete_thread(thread_id)`，可供后续物理清理使用。

### 2.2 本次实现结果

本次已经完成：

- 对话列表、搜索、详情、消息历史、更新和软删除接口。
- 对话列表复合游标与消息 ID 游标分页。
- 当前用户、顶层对话和未删除状态的统一查询约束。
- 消息对应 AgentRun 的批量装配，以及请求 Run metadata 的持久化。
- `Conversation.deleted_at`、`AgentRun.run_metadata` 和查询索引迁移。
- 根对话及内部子对话树软删除，并在存在活动 Run 时拒绝删除。
- `AttachmentRepository` 与真实 `Attachment.uid` 字段对齐。

以下边界仍然保留：

- `Attachment` 只能关联到 Conversation，不能准确指出属于哪一条 Message。
- `prepare_attachments_for_conversation(...)` 返回的 `parser`、`parse_status`、
  `parse_error`、`parse_metadata` 和 `parsed_text` 当前没有持久化。
- `ToolCall` 虽有表定义，但当前主 Run 链路没有稳定的写入闭环，不能承诺历史详情中
  一定存在完整工具调用记录。
- MinIO、Redis、Checkpoint 和 Sandbox 等跨存储资源的物理清理仍未实现。

设计和实现都必须明确这些缺口，不能从 Checkpoint、Redis 事件或请求日志中拼出一份
看似完整但不可重复恢复的历史数据。

## 3. 元数据边界

### 3.1 对话元数据

对话级元数据来自创建对话时的 `ThreadRequest.metadata`，持久化到
`Conversation.conversation_metadata`，例如工作区配置和 `backend_id`。

接口统一返回为：

```json
{
  "metadata": {
    "backend_id": "leaderagent",
    "workspace": "default"
  }
}
```

`backend_id` 是系统维护字段。更新对话元数据时，客户端可以替换用户字段，但不能删除
或覆盖 `backend_id`。

### 3.2 Run 元数据

`AgentRunCreateRequest.thread_metadata` 实际描述一次调用，不是 Conversation 本身。
实施时新增 `AgentRun.run_metadata` JSON 字段，并把该请求值持久化到 Run：

```text
AgentRunCreateRequest.thread_metadata
  -> AgentRun.run_metadata
  -> ThreadRunMetadataResponse.metadata
```

后续可以在一次统一的 API 变更中把请求字段重命名为 `run_metadata`。首期若保留旧字段
名，只做输入别名兼容，数据库和响应中都使用准确的 `run_metadata` / `metadata` 语义。

服务端运行时追加的 `agent_instance` 等 Python 对象不得落库。只持久化请求中的 JSON
值和服务端生成的稳定标识。

### 3.3 消息元数据

首期不增加泛化的 `Message.metadata` JSON。每条消息可恢复的元数据由现有列和对应
AgentRun 组成：

- `message_type`
- `status`
- `request_id`
- `agent_run_id`
- `created_at` / `updated_at`
- Run 的 `run_type`、`agent_status`、`parent_run_id`、时间和 `run_metadata`

如果以后出现不属于 Run、但必须附着到单条 Message 的业务字段，再单独设计
`Message.message_metadata`；本次不为假设需求增加空 JSON 字段。

### 3.4 附件元数据

当前 Attachment 只能作为对话级附件返回，不能挂到具体消息下面。首期详情接口可以
返回数据库已持久化的文件名、MIME、大小、状态和临时访问地址，但不返回未持久化的
解析元数据。

如果产品要求恢复“某条消息的附件及解析状态”，必须先增加：

- `Attachment.message_id -> Message.id`
- 持久化的附件解析元数据字段或独立解析结果表

完成该迁移前，响应不得根据文件时间或数组位置猜测消息与附件关系。

## 4. API 总览

沿用当前 Router 的 `/chat` 前缀和现有 `/thread` 资源路径，避免为了复数形式破坏已
存在的创建接口。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/api/chat/thread` | 创建对话，保留现有路径 |
| `GET` | `/api/chat/thread` | 分页列出或搜索当前用户的顶层对话 |
| `GET` | `/api/chat/thread/{thread_id}` | 加载指定对话、消息和已持久化元数据 |
| `PATCH` | `/api/chat/thread/{thread_id}` | 更新标题、摘要和用户元数据 |
| `DELETE` | `/api/chat/thread/{thread_id}` | 软删除对话 |

不额外增加 `/search`。搜索是列表查询的筛选条件，统一使用 `q` 参数。

## 5. 响应实体

Thread 请求与响应实体统一放在 `server/schemas/thread.py`，Router 只导入并使用
这些 Pydantic 模型。公开 Agent 摘要放在 `server/schemas/agent.py`。
`server/schemas/` 只承载 Router 的 HTTP 契约，不接收 SQLAlchemy 模型或 Service
内部 dataclass、TypedDict。

```python
class ThreadSummaryResponse(BaseModel):
    """对话列表与详情共用的基础信息。"""

    thread_id: str
    title: str
    summary: str | None
    agent_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None


class ThreadRunMetadataResponse(BaseModel):
    """一条消息对应的 Agent Run 元数据。"""

    run_id: str
    run_type: str
    status: str
    parent_run_id: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None
    finished_at: datetime | None


class ThreadMessageResponse(BaseModel):
    """指定对话中的持久化消息。"""

    message_id: int
    role: str
    content: str
    image_content: str | None
    message_type: str
    status: str
    request_id: str | None
    run: ThreadRunMetadataResponse | None
    created_at: datetime
    updated_at: datetime


class ThreadListResponse(BaseModel):
    """对话列表游标页。"""

    items: list[ThreadSummaryResponse]
    next_cursor: str | None


class ThreadDetailResponse(BaseModel):
    """对话及其一页消息历史。"""

    thread: ThreadSummaryResponse
    messages: list[ThreadMessageResponse]
    next_before_message_id: int | None
```

时间字段直接使用 Pydantic `datetime`，由框架输出 ISO 8601，不在 Router 中手写
`isoformat()` 字符串。

## 6. 对话列表与搜索

### 6.1 请求

```http
GET /api/chat/thread?limit=20&cursor=<opaque>&q=需求分析
```

参数：

- `limit`：默认 20，范围 1 到 100。
- `cursor`：可选，不透明游标，客户端不能解析或修改。
- `q`：可选，去除首尾空白后搜索标题和摘要；提供空字符串时返回 422。

首期 `q` 不搜索 Message 正文。消息全文搜索需要 PostgreSQL FTS 或专用搜索索引，
不应先用跨表 `%keyword%` 扫描冒充可扩展实现。

### 6.2 查询范围

Repository 查询必须同时满足：

```text
Conversation.uid == current_user.uid
Conversation.parent_conversation_id IS NULL
Conversation.deleted_at IS NULL
```

子智能体 Conversation 是内部执行记录，不得出现在公开列表。

### 6.3 排序和游标

列表按最近活动时间倒序，稳定次序为：

```text
last_activity_at DESC, Conversation.id DESC
```

其中：

```text
last_message_at = MAX(Message.created_at)
last_activity_at = COALESCE(last_message_at, Conversation.updated_at)
```

不能直接按 `Conversation.updated_at` 判断最近聊天，因为当前插入 Message 不会更新该
行。游标编码最后一项的 `last_activity_at + Conversation.id`，查询时使用严格的小于
条件，避免翻页期间新增消息导致 Offset 页重复或遗漏。

### 6.4 响应示例

```json
{
  "items": [
    {
      "thread_id": "c4f9...",
      "title": "知识库检索设计",
      "summary": "讨论检索和重排链路",
      "agent_id": "leaderagent",
      "metadata": {"backend_id": "leaderagent"},
      "created_at": "2026-08-03T10:00:00+08:00",
      "updated_at": "2026-08-03T10:10:00+08:00",
      "last_message_at": "2026-08-03T10:12:00+08:00"
    }
  ],
  "next_cursor": null
}
```

## 7. 指定对话及消息加载

### 7.1 请求

```http
GET /api/chat/thread/{thread_id}?message_limit=100&before_message_id=812
```

- `message_limit`：默认 100，范围 1 到 200。
- `before_message_id`：可选；只读取当前对话中 `Message.id < cursor` 的更早消息。

首次请求读取最新一页。数据库按 `Message.id DESC` 查询 `limit + 1` 条，判断是否还有
更早数据后，在响应前反转为 `Message.id ASC`，让前端可以直接按时间正序渲染。

`before_message_id` 必须仅作为当前 Conversation 内的游标，不能先按 ID 查询 Message
再绕过对话归属校验。

### 7.2 数据加载

服务层按以下顺序加载：

```text
AuthenticatedUser.uid + thread_id
  -> 查询当前用户未删除的顶层 Conversation
  -> 查询一页 Message
  -> 按 Message.agent_run_id 批量查询 AgentRun
  -> 组装 ThreadDetailResponse
```

必须使用批量查询或显式 eager load，不能逐条消息查询 AgentRun 形成 N+1。

同一个 Run 通常对应一条 user Message 和一条 assistant Message，两条消息都可以返回
同一个 Run 元数据。旧数据没有 `agent_run_id` 时，`run` 返回 `null`，不能因此丢弃
消息。

详情响应中的消息只来自 PostgreSQL。LangGraph Checkpoint 保存 Graph 状态，不是
业务消息表；Redis Stream 只承载在线事件，也不是历史回放源。

### 7.3 响应示例

```json
{
  "thread": {
    "thread_id": "c4f9...",
    "title": "知识库检索设计",
    "summary": null,
    "agent_id": "leaderagent",
    "metadata": {"backend_id": "leaderagent"},
    "created_at": "2026-08-03T10:00:00+08:00",
    "updated_at": "2026-08-03T10:10:00+08:00",
    "last_message_at": "2026-08-03T10:12:00+08:00"
  },
  "messages": [
    {
      "message_id": 811,
      "role": "user",
      "content": "设计对话查询接口",
      "image_content": null,
      "message_type": "text",
      "status": "completed",
      "request_id": "req-1",
      "run": {
        "run_id": "run-1",
        "run_type": "chat",
        "status": "completed",
        "parent_run_id": null,
        "metadata": {"source": "web"},
        "started_at": "2026-08-03T10:11:00+08:00",
        "finished_at": "2026-08-03T10:12:00+08:00"
      },
      "created_at": "2026-08-03T10:11:00+08:00",
      "updated_at": "2026-08-03T10:11:00+08:00"
    }
  ],
  "next_before_message_id": null
}
```

## 8. 更新对话

### 8.1 请求

```http
PATCH /api/chat/thread/{thread_id}
Content-Type: application/json
```

```json
{
  "title": "新的对话标题",
  "summary": "新的摘要",
  "metadata": {"workspace": "research"}
}
```

请求实体：

```python
class ThreadUpdateRequest(BaseModel):
    """更新当前用户拥有的对话。"""

    title: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    metadata: dict[str, Any] | None = None
```

使用 `payload.model_fields_set` 区分“字段未提供”和“显式提供 null”：

- `title` 未提供：保持不变。
- `title` 为 null 或去除空白后为空：返回 422。
- `summary` 未提供：保持不变；显式为 null：清空摘要。
- `metadata` 未提供：保持不变；提供对象：替换用户维护字段，但保留系统字段
  `backend_id`。
- 空 Patch：返回 422，不执行无意义更新。

`thread_id`、`uid`、`agent_id`、`parent_conversation_id` 都不可通过该接口修改。
切换 Agent 会改变 Checkpoint、Sandbox 和运行上下文语义，必须创建新对话。

成功返回更新后的 `ThreadSummaryResponse`。

## 9. 删除对话

### 9.1 首期语义

```http
DELETE /api/chat/thread/{thread_id}
```

成功返回 `204 No Content`。首期删除是软删除：

```text
Conversation.deleted_at = now()
Conversation.updated_at = now()
```

顶层 Conversation 的内部子 Conversation 同时标记删除。此后列表、详情、更新和
Agent Run 创建都必须按未删除条件查询，对外统一表现为 404。

删除前检查根对话及所有子对话的 AgentRun。如果存在 `pending`、`running` 或
`cancel_requested`，返回 409，要求先走现有取消链路并等待终态，不能删除仍由 Worker
执行的上下文。

### 9.2 为什么不在 HTTP 请求中硬删除

一个 Thread 可能同时拥有：

- PostgreSQL Conversation、Message、AgentRun 和 ToolCall。
- Conversation 级 Attachment 及 MinIO 对象。
- LangGraph Checkpoint。
- Redis Run 事件和取消键。
- 会话 Sandbox 或本地 Workspace。

这些资源不共享一个事务。先删外部资源可能留下仍可见但内容残缺的 Conversation；
先提交数据库硬删除又可能留下无法重试定位的外部孤儿。首期通过软删除先保证用户侧
一致性，物理清理单独设计为可重试任务。

后续物理清理任务至少需要：

1. 读取根 Conversation 及所有子 Conversation 的 `thread_id`。
2. 删除附件对象和 Attachment 行。
3. 对每个 thread 调用 `AsyncPostgresSaver.adelete_thread(thread_id)`。
4. 清理对应 Run 的 Redis Stream 和取消键。
5. 通过 Sandbox Provider 的公开接口销毁会话沙箱和 Workspace。
6. 最后硬删除 Conversation；数据库外键级联删除 Message、ToolCall、AgentRun 和子对话。

`AsyncPostgresStore` 可能保存跨 Thread 的用户记忆，不能因为删除一个对话就按 UID
整体删除 Store namespace。

本设计不增加恢复已删除对话的公开接口。若产品需要回收站，应在物理清理策略确定后
单独设计恢复期限和接口。

## 10. Repository 与 Service 边界

### 10.1 ConversationRepository

新增或扩展以下数据库操作：

- `list_top_level_for_user(...)`
- `get_top_level_for_user(...)`
- `list_messages(...)`
- `update_conversation(...)`
- `soft_delete_tree(...)`
- `list_tree_for_user(...)`

所有公开读取查询都在 SQL 中包含 UID、顶层和未删除约束。不要先按 `thread_id`
读取，再在 Router 中判断用户。

### 10.2 AgentRunRepository

需要：

- `create_run(...)` 接收并保存 `run_metadata`。
- 批量读取一页 Message 对应的 Run。
- 检查一个 Conversation 树中的活动 Run。

### 10.3 ThreadService

`server/service/thread_service.py` 统一承载 Thread/Conversation 服务边界，负责：

- 列表游标解析和结果组装。
- 详情消息页与 Run 元数据批量装配。
- 更新字段语义及系统 metadata 保护。
- 删除前活动 Run 检查和 Conversation 树软删除。

它不直接拼 SQL，不读取 Redis Stream，也不把 Checkpoint 当作消息来源。

### 10.4 Thread Router

`thread_router.py` 只负责：

- 引用 `server/schemas/` 中的请求与响应实体。
- 查询参数和 Path 参数接收。
- 调用 ThreadService。
- 把未找到转换为 404、活动 Run 冲突转换为 409、输入错误转换为 422。

当前创建接口中的 User、Agent 和 Conversation 查询也应在实施时移到 Service，避免
继续扩大 Router 内的业务编排。

## 11. 数据库迁移与索引

本次新增 Alembic revision，不依赖 Worker 的 `create_all(checkfirst=True)` 修改已有
表：

```text
conversation.deleted_at          TIMESTAMPTZ NULL
agent_run.run_metadata           JSON NOT NULL DEFAULT '{}'
```

建议索引：

```text
conversation(uid, parent_conversation_id, deleted_at, updated_at, id)
message(conversation_id, id)
agent_run(conversation_id, agent_status)
attachment(conversation_id)
```

`Message.conversation_id` 和 `Attachment.conversation_id` 当前只是外键；PostgreSQL 不会
因为外键自动创建查询索引。

首期搜索使用标题和摘要的普通 `ILIKE`。只有真实数据量证明需要时，再单独评估
`pg_trgm` 或全文检索索引，不在本次 revision 中提前启用扩展。

## 12. 权限、错误和并发

- 所有接口依赖 `AuthenticatedUser`。
- 非当前用户、内部子对话、已删除对话和不存在的对话统一返回 404，避免泄露资源存在。
- 无效游标、空搜索词、空 Patch 和非法标题返回 422。
- 删除存在活动 Run 的对话返回 409。
- 更新采用最后写入覆盖；首期不增加 ETag 或版本号。
- 详情分页使用 Message ID 游标，新增消息不会改变已读取旧消息页的边界。
- 删除和更新前重新按 UID 查询，不复用客户端传入的 Conversation 数据。
- 响应不包含数据库内部 `Conversation.id`、MinIO 凭证、Authorization Header 或原始
  Provider 错误详情。

## 13. 文件级实现清单

1. `migrate/versions/0002_thread_query_metadata.py`
   - 增加 `conversation.deleted_at`、`agent_run.run_metadata` 和必要索引。
2. `src/database/models.py`
   - 对齐迁移后的两个字段。
3. `src/database/repositories/conversation_repository.py`
   - 增加列表、详情消息、更新和软删除查询。
4. `src/database/repositories/agent_run_repository.py`
   - 持久化 Run metadata，增加详情批量查询和活动 Run 检查。
5. `server/service/thread_service.py`
   - 实现对话读写用例、附件处理、Agent 执行辅助和响应所需数据装配。
6. `server/schemas/thread.py`
   - 保存 Thread Router 使用的请求与响应实体。
7. `server/router/thread_router.py`
   - 增加 GET/PATCH/DELETE 路由，并收薄现有创建入口。
8. `server/router/agent_router.py`
   - 把现有 `thread_metadata` 持久化为 `AgentRun.run_metadata`。
9. `server/service/subagent_service.py`
   - 子 Run 明确写入自己的 Run metadata，并拒绝已删除的父 Conversation。
10. `src/database/repositories/attachment_repository.py`
   - 统一 `Attachment.uid` 字段后再接入对话级附件加载。
11. `test/test_thread_conversation_service.py`
    - 增加不依赖网络和真实基础设施的确定性测试。

## 14. 验证要求

实现阶段至少覆盖：

- 用户只能列出自己的未删除顶层对话。
- 子智能体 Conversation 不进入列表和公开详情。
- 无搜索词时分页稳定；标题和摘要搜索只命中当前用户数据。
- 列表最近活动时间来自最新 Message，而不是错误依赖 Conversation.updated_at。
- 详情首屏返回最新消息且响应按正序排列。
- `before_message_id` 只能在当前对话范围内使用。
- 一页消息的 Run 元数据使用批量查询，不产生 N+1。
- 旧 Message 没有 AgentRun 时仍正常返回。
- 请求中的 Run metadata 落库后可通过详情接口恢复。
- 更新可以清空摘要、替换用户 metadata，并保留 `backend_id`。
- 空标题、空 Patch 和越权更新被拒绝。
- 有活动主 Run 或子 Run 时删除返回 409。
- 软删除后列表、详情、更新和新 Run 创建均视为不存在。
- Alembic upgrade/downgrade、目标单元测试、Ruff 和 `git diff --check` 通过。

涉及真实 PostgreSQL、MinIO、Redis、Checkpointer 和 Sandbox 的物理清理只能由集成测试
证明，不能用 mock 单元测试宣称跨存储删除已经完成。

## 15. 首期不做

- 不把 LangGraph Checkpoint 或 Redis Stream 作为历史消息来源。
- 不公开内部子智能体 Conversation。
- 不实现消息正文全文搜索。
- 不实现对话恢复或回收站。
- 不在 DELETE HTTP 请求中同步硬删所有外部资源。
- 不为 Message 增加尚无真实写入者的通用 metadata JSON。
- 不承诺恢复当前没有持久化的附件解析信息或工具调用事件。
- 不允许更新对话的 `thread_id`、`uid`、`agent_id` 或父子关系。
