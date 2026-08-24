# Implementation Plan: Agent Run Message Persistence
计划版本：v0.1.0

## 1. Smallest implementation scope

1. 修改 `src/database/models.py`：为 `AgentRun` 增加 `output_message_id`；
   删除 `ToolCall.tool_sequence`，增加可空的 `status`；明确
   `AgentRun.messages` 和 `Message.agent_run` 使用 `Message.agent_run_id`。
2. 新增 `migrate/versions/0007_agent_run_message_persistence.py`，只执行上述
   schema 变更，不增加兼容字段或数据回填逻辑。
3. 修改 `ConversationRepository`：保留 `create_agent_output_message`，增加
   `create_tool_call` 和 `update_tool_call`，并让 `get_run_result_message`
   通过 `AgentRun.output_message_id` 查询。
4. 修改 `AgentRunRepository`：增加 `set_output_message`。
5. 修改 `server/service/thread_service.py`：增加三个 snake_case 异步函数，从
   checkpoint 读取 Message，并把 `ai/tool` 分别交给两个 save 函数。
6. 在 `stream_agent_response` 正常结束后、`finished` 之前调用父保存函数。父函数统一
   提交事务；取消或异常路径不会进入该调用。
7. 增加一个定向 unittest，使用已经确认的 Human -> AI tool call -> Tool -> final AI
   state，验证 Message 遍历和工具保存闭环。

## 2. Ownership

- `save_message_from_langgraph_state`：构建相同 Graph config、读取 checkpoint、按
  Message `type` 分发并提交事务。
- `save_ai_message`：提取一个 AI Message 的文本；存在 `tool_calls` 时读取当前工具
  调用，并调用两个 Repository。
- `save_tool_message`：提取 Tool Message 的 `tool_call_id/text/status`，调用
  Conversation Repository 更新。
- `ConversationRepository`：按 Conversation -> Message -> ToolCall 聚合创建
  Assistant Message，创建/更新 ToolCall，并读取 Run 的输出 Message。
- `AgentRunRepository`：将当前 Assistant Message ID 写入
  `AgentRun.output_message_id`。
- Worker：只在收到 `finished` 后收口 Run 终态；不读取 LangGraph checkpoint。

## 3. Schema changes

目标：`src/database/models.py` 和
`migrate/versions/0007_agent_run_message_persistence.py`。

```python
class Message(Base):
    agent_run_id = Column(
        String(64),
        ForeignKey("agent_run.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_run = relationship(
        "AgentRun",
        back_populates="messages",
        foreign_keys=[agent_run_id],
    )


class ToolCall(Base):
    __tablename__ = "tool_call"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(
        Integer,
        ForeignKey("message.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_call_id = Column(String(255), nullable=True)
    tool_name = Column(String(255), nullable=False)
    tool_arguments = Column(JSON, nullable=False, default=dict)
    tool_input = Column(JSON, nullable=True)
    tool_result = Column(Text, nullable=True)
    status = Column(String(16), nullable=True)


class AgentRun(Base):
    output_message_id = Column(
        Integer,
        ForeignKey("message.id", ondelete="SET NULL"),
        nullable=True,
        comment="Output message ID",
    )
    messages = relationship(
        "Message",
        back_populates="agent_run",
        foreign_keys="Message.agent_run_id",
    )
```

`Message.tool_calls` 删除对 `ToolCall.tool_sequence` 的 `order_by`。

Migration upgrade 新增 Run 输出指针，并调整 ToolCall：

```python
op.add_column(
    "agent_run",
    sa.Column("output_message_id", sa.Integer(), nullable=True),
)
op.create_foreign_key(
    "fk_agent_run_output_message_id_message",
    "agent_run",
    "message",
    ["output_message_id"],
    ["id"],
    ondelete="SET NULL",
)
op.drop_column("tool_call", "tool_sequence")
op.add_column(
    "tool_call",
    sa.Column("status", sa.String(length=16), nullable=True),
)
```

## 4. Repository contracts

### 4.1 Create ToolCall

目标：
`src/database/repositories/conversation_repository.py:ConversationRepository.create_tool_call`

```python
async def create_tool_call(
    self,
    *,
    message_id: int,
    tool_call_id: str,
    tool_name: str,
    tool_arguments: dict,
) -> ToolCall:
    tool_call = ToolCall(
        message_id=message_id,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_arguments=dict(tool_arguments),
    )
    self.session.add(tool_call)
    await self.session.flush()
    return tool_call
```

该方法不接收或生成 `sequence/index`，也不复制 `args` 到 `tool_input`。

### 4.2 Update ToolCall

目标：
`src/database/repositories/conversation_repository.py:ConversationRepository.update_tool_call`

```python
async def update_tool_call(
    self,
    *,
    tool_call_id: str,
    tool_result: str,
    status: str,
) -> ToolCall:
    result = await self.session.execute(
        select(ToolCall)
        .where(ToolCall.tool_call_id == tool_call_id)
    )
    tool_call = result.scalar_one()
    tool_call.tool_result = tool_result
    tool_call.status = status
    await self.session.flush()
    return tool_call
```

Repository 使用 state 中的原始 `tool_call_id`，不校验非空，也不按名称或位置回退。

### 4.3 Bind the Run output Message

目标：
`src/database/repositories/agent_run_repository.py:AgentRunRepository.set_output_message`

```python
async def set_output_message(
    self,
    *,
    run_id: str,
    output_message_id: int,
) -> AgentRun:
    run = await self.get_by_id(run_id)
    run.output_message_id = output_message_id
    await self.session.flush()
    return run
```

### 4.4 Read the Run result Message

目标：
`src/database/repositories/conversation_repository.py:ConversationRepository.get_run_result_message`

```python
async def get_run_result_message(self, run_id: str) -> Message | None:
    result = await self.session.execute(
        select(Message)
        .join(AgentRun, AgentRun.output_message_id == Message.id)
        .where(AgentRun.id == run_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()
```

## 5. Thread Service contracts

### 5.1 Save AI Message

目标：`server/service/thread_service.py:save_ai_message`

```python
async def save_ai_message(
    *,
    db: AsyncSession,
    conversation_id: int,
    agent_run_id: str,
    message: AIMessage,
) -> None:
    conversations = ConversationRepository(db)
    output_message = await conversations.create_agent_output_message(
        conversation_id=conversation_id,
        agent_run_id=agent_run_id,
        content=message.text,
    )
    await AgentRunRepository(db).set_output_message(
        run_id=agent_run_id,
        output_message_id=int(output_message.id),
    )

    if message.tool_calls:
        tool_call = message.tool_calls[0]
        await conversations.create_tool_call(
            message_id=int(output_message.id),
            tool_call_id=tool_call["id"],
            tool_name=tool_call["name"],
            tool_arguments=tool_call["args"],
        )
```

### 5.2 Save Tool Message

目标：`server/service/thread_service.py:save_tool_message`

```python
async def save_tool_message(
    *,
    db: AsyncSession,
    message: ToolMessage,
) -> None:
    await ConversationRepository(db).update_tool_call(
        tool_call_id=message.tool_call_id,
        tool_result=message.text,
        status=message.status,
    )
```

### 5.3 Read and dispatch checkpoint Messages

目标：`server/service/thread_service.py:save_message_from_langgraph_state`

```python
async def save_message_from_langgraph_state(
    *,
    agent_instance: BaseAgent,
    runtime_context: dict[str, Any],
    db: AsyncSession,
) -> None:
    context = agent_instance.agent_context()
    context.update_context(runtime_context)
    graph = await agent_instance.get_agent(context)
    checkpoint = await graph.aget_state(
        {
            "configurable": {
                "thread_id": context.thread_id,
                "uid": context.uid,
            }
        }
    )

    conversation = await ConversationRepository(
        db
    ).get_conversation_by_thread_id_for_user(
        thread_id=context.thread_id,
        user_id=context.uid,
    )

    for message in checkpoint.values.get("messages", []):
        if message.type == "ai":
            await save_ai_message(
                db=db,
                conversation_id=int(conversation.id),
                agent_run_id=context.run_id,
                message=message,
            )
        elif message.type == "tool":
            await save_tool_message(
                db=db,
                message=message,
            )

    await db.commit()
```

父方法不解析 `content` 中的工具 block，不执行 ToolCall SQL，也不增加 Message 类型
兼容层。

### 5.4 Normal completion call site

目标：`server/service/thread_service.py:stream_agent_response`

```python
await save_message_from_langgraph_state(
    agent_instance=agent_instacne,
    runtime_context=agent_runtime_context,
    db=db,
)

yield make_agent_stream_event(
    status="finished",
    runtime_metadata=runtime_metadata,
)
```

调用只位于 Agent Stream 的正常完成路径。保存或提交失败会沿现有异常路径传播，不发出
`finished`。

## 6. Validation

新增一个 `test/test_thread_message_persistence.py` 用例，输入固定为：

```text
HumanMessage
AIMessage(tool_calls=[{id="", name="add_numbers", args={a: 17, b: 25}}])
ToolMessage(tool_call_id="", content="42", status="success")
AIMessage(content="42", tool_calls=[])
```

一次测试验证：

- Human Message 未重复创建；
- 第一条 AI Message 创建 Assistant Message 和一个 ToolCall；
- ToolCall 只保存 `tool_call_id/tool_name/tool_arguments`，没有排序值；
- Tool Message 更新同一 ToolCall 的 `tool_result="42"` 和 `status="success"`；
- 最后一条 AI Message 创建最终 Assistant Message；
- `AgentRun.output_message_id` 指向最终 Assistant Message；
- `get_run_result_message(run_id)` 通过该指针返回最终文本 `42`；
- 物理删除 Conversation 时，Message 和 ToolCall 由外键递进级联删除。

实施后的定向验证命令：

```bash
.venv/bin/python -m unittest test.test_thread_message_persistence
.venv/bin/python -m compileall -q server/service src/database/repositories
uv run --no-sync alembic upgrade head
git diff --check -- \
  server/service/thread_service.py \
  src/database/models.py \
  src/database/repositories \
  migrate/versions \
  test/test_thread_message_persistence.py \
  docs/spec/run/message-persistence
```

不启动 API、Worker 或前端进程。
