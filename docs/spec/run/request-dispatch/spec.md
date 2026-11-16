# Agent Run 分发策略与等待区调度规格

## 1. 能力与职责

`POST /api/agent/runs` 先按 `dispatch_policy` 接收并持久化 `AgentRunRequest`，再根据会话中的 Run 状态决定立即创建 `AgentRun`、进入等待区排队、转向当前活跃 Run 或拒绝请求。

- **PostgreSQL**：持有 `AgentRunRequest`（等待区与派发状态）、输入 `Message` 与 `AgentRun`；`uq_agent_run_one_executing_per_thread` 继续保证同一 `thread_id` 至多存在一个执行中 `AgentRun`。
- **ARQ**：只派发已晋升为 `AgentRun(agent_status="pending")` 的任务，`enqueue_agent_run(run_id)` 契约保持不变。
- **Worker / Runtime**：执行 Run、响应软停止（Turn 边界 `jump_to="end"`）与硬取消，收敛输出消息与 Run 终态后，触发下一条等待区请求晋升。

HTTP 请求模型为 `server/entities/agent.py:AgentRunCreateRequest`，数据库模型为 `src/database/models.py:AgentRunRequest`。请求保存、策略分发与等待区移除由 `server/service/agent_run_service.py` 编排；Turn 边界停机与消息收敛由 `src/agents/middlewares/`、`server/service/thread_service.py` 与 `server/worker.py` 协作完成。

## 2. 数据契约

### 2.1 HTTP 请求模型：`AgentRunCreateRequest`

```python
class AgentRunCreateRequest(BaseModel):
    query: str | None = Field(default=None, description="问题")
    agent_id: str = Field(default=..., description="Agent 标识")
    thread_id: str = Field(default=..., description="对话 thread_id")
    dispatch_policy: Literal["reject", "queue", "steer"] = Field(
        default="reject",
        description="会话忙碌时的分发策略：reject 拒绝、queue 等待当前 Run 结束、steer 转向当前 Run",
    )
    request_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="请求元数据：type（chat/resume）、model、request_id、attachment_file_ids、resume.answers",
    )
    image_content: str | None = Field(default=None, description="图像文件")
```

### 2.2 数据库模型：`AgentRunRequest` 与 `Message`

```python
class AgentRunRequest(Base):
    __tablename__ = "agent_run_request"
    __table_args__ = (
        Index(
            "ix_agent_run_request_thread_queued",
            "thread_id",
            "queue_seq",
            postgresql_where=text("status = 'queued'"),
        ),
    )

    request_id = Column(String(128), primary_key=True)
    uid = Column(String(64), nullable=False)
    thread_id = Column(String(64), nullable=False, index=True)
    agent_id = Column(String(128), nullable=False)
    trigger_message_id = Column(
        Integer,
        ForeignKey("message.id", ondelete="CASCADE"),
        nullable=False,
    )
    dispatch_policy = Column(String(16), nullable=False, server_default="reject")
    status = Column(String(16), nullable=False, server_default="dispatched")
    queue_seq = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

字段语义：

- `thread_id`：逻辑对应 `Conversation.thread_id`（不建跨表外键，由 Service 层持会话锁校验归属与 `deleted_at IS NULL`）；会话物理删除时通过 `trigger_message_id -> message.id (ON DELETE CASCADE)` 自动级联清除。
- `dispatch_policy`：取自请求的 `reject | queue | steer`。
- `status`：请求在等待区中的状态，仅允许 `queued | dispatched | cancelled`：
  - `queued`：已持久化在等待区，尚未生成 `AgentRun`。
  - `dispatched`：已绑定 1:1 `AgentRun`（`AgentRun.request_id == AgentRunRequest.request_id`）。
  - `cancelled`：在未晋升前被用户从等待区删除。
- `queue_seq`：仅当请求进入等待区时按同一 `thread_id` 单调递增分配，决定晋升顺序（`queue_seq ASC`）。
- `trigger_message_id` 对应的用户输入 `Message`：
  - 立即执行（`dispatched`）时，`Message.status = "completed"` 并绑定 `agent_run_id = run.id`。
  - 进入等待区（`queued`）时，`Message.status = "queued"`、`Message.agent_run_id = None`；主消息历史查询过滤 `status = "queued"` 的记录，由 `ThreadDetailResponse.queued_requests` 单独返回。晋升为 `AgentRun` 时再将 `Message.status` 置为 `"completed"`、重新分配当前最大 `sequence` 并绑定 `agent_run_id`。
  - 从等待区删除（`cancelled`）时，同步软删除或物理删除该未绑定的 `Message`。

### 2.3 Repository 接口

`src/database/repositories/agent_run_request_repository.py:AgentRunRequestRepository` 提供：

```python
class AgentRunRequestRepository:
    def __init__(self, session: AsyncSession): ...

    async def get_by_request_id(self, request_id: str) -> AgentRunRequest | None: ...

    async def create_request(
        self,
        *,
        request_id: str,
        uid: str,
        thread_id: str,
        agent_id: str,
        trigger_message_id: int,
        dispatch_policy: str,
        status: str,
        queue_seq: int | None = None,
    ) -> AgentRunRequest: ...

    async def list_queued_for_thread(
        self, thread_id: str, *, uid: str
    ) -> list[AgentRunRequest]: ...

    async def has_queued_steer_for_thread(self, thread_id: str) -> bool: ...

    async def pop_next_queued_for_thread(
        self, thread_id: str
    ) -> AgentRunRequest | None: ...

    async def mark_dispatched(self, request_id: str) -> None: ...

    async def cancel_queued_request(
        self, request_id: str, *, uid: str
    ) -> AgentRunRequest | None: ...
```

## 3. 分发策略与状态规则

### RUN-RD-001 请求接收与策略路由

Service 在持有用户所属 `Conversation` 行锁（`for_update=True`）后执行 `request_id` 幂等检查（RUN-RD-004）。新请求按以下规则处理：

1. 查询 `get_pending_interaction_run(thread_id)`：若存在未回答的 `ask_user` 中断 Run，所有策略均返回 HTTP 409（`detail: 当前会话有待回答的问题`），**不**提交孤立的 user `Message`。
2. 查询 `get_latest_active_for_thread(thread_id)`：
   - **会话空闲（无活动 Run）**：保存 `Message(status="completed")`、`MessageAttachment`、`AgentRunRequest(status="dispatched")`，提交接收事务后进入 RUN-RD-002 创建 `AgentRun` 并调用 `enqueue_agent_run(run.id)`。
   - **会话忙碌且 `dispatch_policy == "reject"`**：不写入 `Message` 与 `AgentRunRequest`，直接返回 HTTP 409（`detail: 当前会话有正在执行的任务`）。
   - **会话忙碌且 `dispatch_policy == "queue"`**：保存 `Message(status="queued")` 与 `AgentRunRequest(status="queued", dispatch_policy="queue", queue_seq=next_seq)`，提交后返回 HTTP 202（`status="queued"`），不创建 `AgentRun` 也不调用 `enqueue_agent_run`。
   - **会话忙碌且 `dispatch_policy == "steer"`**：保存 `Message(status="queued")` 与 `AgentRunRequest(status="queued", dispatch_policy="steer", queue_seq=next_seq)`，提交后返回 HTTP 202（`status="queued"`、`steering_run_id=active_run.id`），不写额外的队列信号。

### RUN-RD-002 Run 创建与终态晋升

1. **直接创建**：会话空闲时创建 `AgentRun(agent_status="pending")`、回绑 `Message.agent_run_id`，提交后调用 `enqueue_agent_run(run.id)`。
2. **终态晋升（`dispatch_next_queued_request(thread_id)`）**：
   - 在 `server/worker.py` 将活跃 `AgentRun` 收敛为 `completed | failed | cancelled` 终态（含租约过期回收器收敛 `LeaseExpired`）**之后**调用。
   - 持有 `Conversation(thread_id)` `FOR UPDATE` 行锁，确认 `get_pending_interaction_run` 与 `get_latest_active_for_thread` 均为 `None`。
   - 取出 `queue_seq` 最小的一条 `AgentRunRequest(status="queued")`（若同队列内有多个请求，优先晋升 `steer` 或严格按 `queue_seq ASC` 顺序出队）。
   - 将关联 `Message` 置为 `status="completed"`、更新为新 `sequence`，创建 `AgentRun(agent_status="pending")` 并绑定 `agent_run_id`，将 `AgentRunRequest.status` 更新为 `"dispatched"`，提交事务后调用 `enqueue_agent_run(run.id)`。

### RUN-RD-003 Steer 优雅停机（Turn 边界 `jump_to="end"`）

1. **核心边界**：活跃 Run 正在执行 `model` 流式输出或 `tools` 调用时，不强行向进行中节点注入 `HumanMessage`，也不直接硬杀正常工具调用；等当前轮的 `model -> tools` Superstep 闭环并提交 checkpoint 后，在下一轮 `before_model` 节点完成退出。
2. **单一事实来源（无需额外信号）**：直接复用 PostgreSQL `AgentRunRequest` 表作为唯一状态来源，不向 Redis 写入 `run:steer:{run_id}` 额外信号。若用户通过 `DELETE /api/agent/runs/requests/{request_id}` 撤销该 `steer` 请求，转向条件自动消失，无需双端同步。
3. **Graph 退出路径**：`LeaderAgent` 装配 `SteerStopMiddleware`（`before_model(can_jump_to=["end"])`）。进入下一轮 `before_model` 前查询当前会话是否存在 `status == "queued"` 且 `dispatch_policy == "steer"` 的 `AgentRunRequest`；命中时返回 `{"jump_to": "end"}`，图路由至 `after_agent -> END`，完整保留上一个 `AIMessage(tool_calls)` 与 `ToolMessage` 配对。
4. **终态收敛与硬取消兜底**：
   - 图跳至 `END` 正常结束 `astream_events` 后，先执行消息保存收敛，再由 Worker 结合 `has_queued_steer_for_thread(thread_id)` 将当前 Run 收敛为 `cancelled`（标记被转向的终止原因），随后调用 `dispatch_next_queued_request(thread_id)` 晋升新请求。
   - 若工具执行耗时超过宽限阈值或用户点击显式强停，仍由 `_cancellable_stream` 触发 `asyncio.CancelledError` 硬取消兜底。

### RUN-RD-004 非正常 / Steer 消息保存收敛

取消或转向退出时，`server/service/thread_service.py` 的消息持久化遵循单一收敛顺序：

1. 先执行 `save_message_from_langgraph_state`，将当前 Run 内**已提交进 LangGraph checkpoint** 的全部 `AIMessage`（通过 `ModelMessageAuditRepository.reconcile_to_history` 转正流式审计行）与 `ToolMessage`（更新 `ToolCall` 结果）落库。
2. 仅当硬取消或异常中断发生在流式半途中、存在尚未进入 checkpoint 的 `accumulated_msg` 时（`stream_agent_response` 与 `resume_agent_response` 均须传入 `full_msg`），优先按当前 `operation_id` 对 `model_audit` 行执行 reconcile 并附加中断元数据；不存在对应审计行时才写入截断消息。
3. 若因 `before_model` 跳 `END` 退出且最后一条 `AIMessage` 仅为工具调用前置消息，在 Run/Message 元数据保留 `stop_reason="steered"`，不重复插入多余文本消息。

### RUN-RD-005 等待区请求删除

`DELETE /api/agent/runs/requests/{request_id}` 仅操作尚未晋升为 `AgentRun` 的等待区请求：

1. 校验用户身份并持有所属 `Conversation` `FOR UPDATE` 行锁（与 Worker 晋升互斥）。
2. 查询 `AgentRunRequest`：
   - `status == "queued"`：置为 `status = "cancelled"`，清理未绑定的触发 `Message`，提交后返回 HTTP 200。
   - `status == "dispatched"`（已与晋升并发生成 `AgentRun`）：返回 HTTP 409 并附带 `run_id`，前端改走 `POST /api/agent/runs/{run_id}/cancel`。
   - `status == "cancelled"`：幂等返回 HTTP 200。

### RUN-RD-006 重复请求幂等

按 `request_id` 查询 `AgentRunRequest` 与 `AgentRun`，核对 `uid`、`thread_id`、`agent_id`：

- 已绑定 `AgentRun`：返回该 Run（HTTP 200）。
- 状态为 `queued`：返回当前排队态（HTTP 202、`queue_position`）。
- 状态为 `cancelled`：返回 HTTP 409（`detail: 请求已从等待区取消`）。
- 归属校验失败：返回 HTTP 409（`detail: request_id 已被其他请求使用`）。

## 4. HTTP 接口

### 4.1 提交请求：`POST /api/agent/runs`

- **立即创建或已关联 Run（HTTP 200）**：

```json
{
  "run_id": "<run.id>",
  "thread_id": "<run.thread_id>",
  "status": "<run.agent_status>",
  "request_id": "<run.request_id>",
  "stream_url": "/api/agent/runs/<run.id>/events?thread_id=<run.thread_id>"
}
```

- **进入等待区排队或转向（HTTP 202）**：

```json
{
  "run_id": null,
  "thread_id": "<request.thread_id>",
  "status": "queued",
  "dispatch_policy": "queue",
  "request_id": "<request.request_id>",
  "queue_position": 1,
  "steering_run_id": null,
  "stream_url": null
}
```

### 4.2 删除等待区请求：`DELETE /api/agent/runs/requests/{request_id}`

- 成功移除返回 HTTP 200：`{"request_id": "<id>", "status": "cancelled"}`。
- 已晋升为 Run 返回 HTTP 409：`{"detail": "请求已开始执行", "run_id": "<run.id>"}`。

### 4.3 会话详情扩展：`GET /api/chat/thread/{thread_id}`

`ThreadDetailResponse` 增加 `queued_requests: list[QueuedRunRequestItem]`，按 `queue_seq ASC` 返回当前会话 `status == "queued"` 的请求摘要（`request_id`、`dispatch_policy`、`queue_seq`、`content`、`created_at`）。

## 5. 流程图

### 改动前

```mermaid
flowchart TD
    A[POST /api/agent/runs] --> B[TX1: 保存 Request 与 Input Message 并提交]
    B --> C[TX2: 锁定会话检查活跃 Run]
    C -->|有活跃 Run / 待回答问题| D[保留 Request/Message, 返回 409]
    C -->|空闲| E[创建 AgentRun pending 并入队]
    E --> F[Worker 执行 Run]
    F -->|硬取消 CancelledError| G[save_partial_message 直接另插 assistant 消息]
```

### 改动后

```mermaid
flowchart TD
    A[POST /api/agent/runs] --> B[锁定会话校验幂等与待回答问题]
    B -->|有待回答问题| C[不落盘脏消息, 返回 409]
    B -->|空闲| D[保存 Request dispatched + 创建 AgentRun pending]
    D --> E[enqueue_agent_run]
    B -->|忙碌且 policy=reject| F[不落盘脏消息, 返回 409]
    B -->|忙碌且 policy=queue| G[保存 Request queued, 返回 202]
    B -->|忙碌且 policy=steer| H[保存 Request queued steer, 返回 202]

    H --> I[Worker 当前轮 model/tools 跑完]
    I --> J[before_model 查到 queued steer Request -> jump_to=end]
    J --> K[先 save_message_from_langgraph_state 同步 checkpoint]
    K --> L[Worker 收敛 Run 终态]
    E --> M[Worker 正常/取消执行完成并收敛 Run 终态]
    L --> N[dispatch_next_queued_request 锁会话晋升队首]
    M --> N
    N --> O[创建新 AgentRun pending 并调用 enqueue_agent_run]

    P[DELETE /api/agent/runs/requests/request_id] --> Q[锁会话检查状态]
    Q -->|queued| R[置为 cancelled 并清理未绑定 Message]
    Q -->|dispatched| S[返回 409 + run_id]
```

## 6. 验收标准

- `dispatch_policy="reject"` 在会话忙碌时返回 409 且不产生孤立 `Message` 与 `AgentRunRequest`。
- `dispatch_policy="queue"` 在会话忙碌时返回 202，主消息历史不提前出现排队消息；当前 Run 收敛终态后自动晋升队首请求并入队执行。
- `dispatch_policy="steer"` 在当前轮 `tools` 执行完进入下一轮 `before_model` 时通过 `jump_to="end"` 优雅停机，checkpoint 内 `AIMessage` 与 `ToolMessage` 完整配对，随后自动晋升执行新请求。
- 非正常退出（Turn 边界停机或硬取消）均先同步已提交 checkpoint 的消息与 `ToolCall` 结果，半截流式输出优先 reconcile 已有 `model_audit` 行，且 `resume_agent_response` 保留部分输出。
- `DELETE /api/agent/runs/requests/{request_id}` 在会话锁下移除 `queued` 请求及触发消息；并发已被晋升时返回 409 并附带 `run_id`。
- `enqueue_agent_run(run_id)` 契约保持不变，仅在 `AgentRun` 创建提交后被调用。
