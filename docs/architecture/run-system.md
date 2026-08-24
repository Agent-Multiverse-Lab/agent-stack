# Run System Architecture

## 1. Responsibility

`Run System` 管理一次对话/子任务的执行生命周期：入队、执行、事件、终态、取消。

行为规格入口：

- [Run Lifecycle Spec](../spec/run/lifecycle/spec.md)
- [Run Cancellation Spec](../spec/run/cancellation/spec.md)
- [Agent Run Event Streaming Spec](../spec/run/event-streaming/spec.md)

## 2. Core Components

- `server/router/agent_router.py`：对外入口（创建 run、取消、SSE 读取）。
- `server/service/agent_run_service.py`：run 及事件流的服务层入口。
- `server/service/arq_queue_servcie.py`：ARQ/Redis 运行时协作层。
- `server/worker.py`：实际执行 worker，消费 `process_agent_run`。
- `src/database/repositories/agent_run_repository.py`：状态原子更新。

## 3. State Model

`pending -> queued -> running -> (completed | failed | cancelled)`  
`cancel_requested` 作为中间态，专门承接中断意图。

## 4. Lifecycle Flow

```text
POST /api/agent/runs
  -> create run + persist message
  -> enqueue run_id to ARQ
ARQ: process_agent_run(run_id)
  -> set running
  -> stream agent output
  -> end -> set terminal status + write end event
```

## 5. Event Flow

- Stream key: `run:events:{run_id}`
- Event types: `status`, `messages`, `agent_execute_event`, `end`
- Terminal event must always be `{"type":"end","status":...}`

## 6. Persistence Policy

- 业务状态：`PostgreSQL AgentRun.agent_status`
- 运行信号：`Redis run:cancel:{run_id}`
- 运行可见性：`Redis Stream run:events:{run_id}`

## 7. Concurrency

- 同一 run 的状态更新使用数据库行锁（在仓储层）保护。
- Worker 并发执行多个 run，但同一 run 只能有单一执行链。

## 8. Capability Ownership

| 能力 | 承载位置 | 责任边界 |
| --- | --- | --- |
| HTTP 创建、取消和 SSE 入口 | `server/router/agent_router.py` | 鉴权、参数校验和响应整形，不执行 Agent |
| Run 服务编排 | `server/service/agent_run_service.py` | 创建 Run、持久化输入、授权校验和事件读取编排 |
| ARQ/Redis 适配 | `server/service/arq_queue_servcie.py` | 队列、Stream、取消 key/Pub/Sub 和事件信封，不决定业务终态 |
| Run 执行 | `server/worker.py` | 重载输入、执行 Agent、发布事件和收口终态 |
| Run 持久化 | `src/database/repositories/agent_run_repository.py` | 在事务和行锁内决定状态转换 |
| SSE framing | `server/utils/agent_run_utils.py` | 将 Redis 信封转成公开 SSE，不访问 Redis 或数据库 |

队列只传 `run_id`，使用 `run:{run_id}` 作为 Job ID；SSE 消费者独立读取
`run:events:{run_id}`。`AgentRun.run_type` 表示执行类型，`parent_run_id` 只表示父子
关系，不能互相替代。

## 9. Process Boundaries

- FastAPI 的构造、API lifespan 和独立 ARQ Worker lifespan 分别由
  `server/main.py`、`server/lifespan.py` 和 `server/worker.py` 承载。
- Thread 和 attachment 编排归 `server/service/thread_service.py`；不创建平行的
  `conversation_service.py`。
- `server/service/arq_queue_servcie.py` 保留现有文件名，负责 ARQ/Redis 客户端协作、
  Stream 信封、取消 key 和 Pub/Sub；`src/storage/redis/redis_manger.py` 只负责客户端
  构造、共享生命周期和关闭。
- `server/utils/agent_run_utils.py` 是纯 Redis 信封到 SSE framing 的适配器，不访问
  Redis、PostgreSQL 或 Run 生命周期。
- Worker 可以创建缺失表和 Agent 注册记录，但不得 drop 表、seed 用户/会话或覆盖已有
  Agent；后端源码变更后需要重建 Compose Worker 镜像。
