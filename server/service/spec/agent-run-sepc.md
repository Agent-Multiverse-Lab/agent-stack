# Agent Run Service 设计说明

状态：草稿

归属：backend

相关代码：

- `server/service/agent_run_service.py`
- `server/service/arq_queue_servcie.py`
- `server/worker.py`
- `src/storage/redis/redis_manger.py`

## 1. 定位

`Agent Run Service` 负责所有顶层和子级 `AgentRun` 共用的运行编排能力：

1. ARQ 入队：把 `run_id` 投递给后台 worker。
2. Run event：构建、解析并向 SSE 投影 Agent Run 事件。
3. 取消请求：按当前用户更新 PostgreSQL `cancel_requested`，提交后发布取消信号。

`arq_queue_servcie.py` 负责 ARQ pool 使用以及所有直接 Redis I/O：Stream 的
`XADD`、`XREAD`、`XREVRANGE`，取消 key 的 `SET`、`EXISTS`、`DELETE`。
Redis client 和 ARQ pool 的底层创建仍然属于
`src/storage/redis/redis_manger.py`。

## 2. 第一版范围

第一版只打通这条链路：

```text
create run -> enqueue run -> worker execute -> publish events -> frontend read events
```

需要实现的接口：

```python
async def enqueue_agent_run(run_id: str) -> None: ...
async def publish_agent_run_event(run_id: str, event: dict[str, Any]) -> str: ...
async def read_agent_run_events(...) -> list[tuple[str, dict[str, Any]]]: ...
async def stream_agent_run_event(...) -> AsyncIterator[str]: ...
async def cancel_run_service(*, run_id: str, current_user_id: str, db: AsyncSession) -> dict[str, str]: ...
async def request_cancel_agent_run(*, run_id: str, current_uid: str, db: AsyncSession) -> AgentRun: ...
```

队列服务提供直接 Redis 操作：

```python
async def publish_agent_run_cancel_signal(run_id: str, *, reason: str | None = None) -> None: ...
async def has_agent_run_cancel_signal(run_id: str) -> bool: ...
async def clear_agent_run_cancel_signal(run_id: str) -> None: ...
```

不做的事：

- 不做 Redis pub/sub。
- 不做 `run:result:{run_id}`。
- 不做后台等待结果接口。
- 不做最近事件查询接口。
- 不做长期事件归档。

这些等 worker、SSE 和取消链路真的跑通后再加。

## 3. Redis Key

| 用途 | Key | 说明 |
| --- | --- | --- |
| ARQ job id | `run:{run_id}` | 入队去重 |
| run event stream | `run:events:{run_id}` | SSE 游标续读 |
| cancel flag | `run:cancel:{run_id}` | worker 轮询取消 |

Redis Stream event id 和 ARQ job id 是两个概念。

`run:events:{run_id}` 里的 Redis Stream event id 只作为 SSE 游标，不是持久业务状态。

## 4. Event Payload

Service 写事件时统一补齐基础字段：

```json
{
  "scope": "agent_run",
  "run_id": "run_123",
  "type": "status",
  "created_at": "2026-07-06T22:50:00+00:00"
}
```

事件字段只放小 payload。完整消息、附件、生成资产放 PostgreSQL 或 storage。

终态统一为 `type: "end"`，最终状态放在 `status`：`completed`、`failed` 或
`cancelled`。`stream_agent_run_events(...)` 只在读到 `end` 后结束。

## 5. TTL

第一版用一个模块常量：

```python
RUN_REDIS_TTL_SECONDS = 24 * 60 * 60
```

每次写 `run:events:{run_id}` 或 `run:cancel:{run_id}` 时刷新 TTL。

先不加配置项。等 TTL 真的需要按环境调整时再提到 `config.py`。

## 6. PostgreSQL 和 Redis 边界

PostgreSQL 保存事实状态：

- run 基本记录
- run 当前状态，包括请求取消时的 `cancel_requested`
- final message / error

Redis 只保存临时运行能力：

- ARQ 队列状态
- run event stream
- cancel flag

如果 Redis Stream 过期，前端只能回退到 PostgreSQL 最终状态和持久消息。

## 7. Worker 使用方式

worker 只接收 `run_id`：

```python
async def process_agent_run(ctx, run_id: str) -> None:
    ...
```

worker 执行时：

1. 从 PostgreSQL 读取 run。
2. 写入并发布 `running`。
3. 等待 Agent 下一条输出的同时监听 `run:cancel:{run_id}`。
4. 输出 token/status/tool 时调用 `publish_agent_run_event(...)`。
5. 成功或失败时写入数据库终态，再发布 `end`。
6. 收到取消信号时停止消费，写入数据库 `cancelled`，发布 `end`，再清理取消信号。

worker 不直接拼 Redis key。

## 8. 取消顺序

`POST /api/agent/runs/{run_id}/cancel` 通过 `cancel_run_service(...)` 调用统一的
`request_cancel_agent_run(...)`。取消入口必须先把 PostgreSQL 状态写成
`cancel_requested`，提交成功后才能发布 Redis 取消信号。请求取消时不写终态
Stream 事件；只有 Worker 确认 Agent
消费已经停止后，才能把状态写成 `cancelled` 并发布最终 `end`。

取消入口通过 `AgentRunRepository.list_active_child_runs(...)` 查询目标 Run
下当前用户的活跃直接子 Agent Run；同一事务内先把子 Run、再把目标 Run 标记为
`cancel_requested`，提交后分别发布取消信号。取消范围不按 `run_type` 分支。

`parent_run_id` 只表示 Run 之间的关联：连续的主对话 Run 也可能记录上一条 Run，
因此取消、Worker Agent 解析和子 Agent 查询都不能用它推断 Run 类型。
