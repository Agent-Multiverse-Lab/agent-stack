# Run System Architecture

## 1. Responsibility

`Run System` 管理一次对话/子任务的执行生命周期：入队、执行、事件、终态、取消。

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
