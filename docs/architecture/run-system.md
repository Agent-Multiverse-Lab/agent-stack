# Run System Architecture

## 1. Responsibility

`Run System` 管理一次对话/子任务的执行生命周期：入队、执行、事件、终态、取消。

相关存储细节见 [Run 执行记录与租约](run-execution-schema.md)（execution 持有执行权、心跳、租约与结束事实）。

## 2. Core Components

- `server/router/agent_router.py`：对外入口（创建 run、取消、SSE 读取）。
- `server/service/agent_run_service.py`：Run 及事件流的服务层入口。
- `server/service/arq_queue_servcie.py`：ARQ/Redis 运行时协作层。
- `server/worker.py`：实际执行 worker，消费 `process_agent_run`。
- `src/database/repositories/agent_run_repository.py`：状态原子更新。
- `src/database/repositories/agent_run_request_repository.py`：请求关联持久化和 ORM 记录查询。

## 3. State Model

`pending -> running -> (completed | failed | cancelled | interrupted)`
`cancel_requested` 作为中间态，专门承接中断意图。

## 4. Lifecycle Flow

```text
POST /api/agent/runs
  -> lock conversation, check request_id / pending interaction / active Run
  -> reject busy input, or persist queued Request + Message
  -> when idle: persist Request + Message + pending Run in the same transaction
  -> commit, then enqueue run_id to ARQ
ARQ: process_agent_run(run_id)
  -> set running
  -> stream agent output
  -> end -> set terminal status + write end event
```

待回答问题阻止接收新输入；活动 Run 按 `enqueue | reject | steer`（默认 `enqueue`）决定拒收或即时落库 `AgentRunRequest(status="queued")` 与 `Message(status="queued")`，删除走逻辑软取消（`cancelled` 墓碑），`POST .../steer` 支持忙碌原地升级或空闲就地晋升。同一 `request_id` 重试复用已接收输入。Request 持有输入关联、策略、等待区状态和顺序；正文、图片和消息元数据由 Message 持有，执行状态由 AgentRun 持有。ARQ Worker 保持终止与派发解耦（`set_run_terminal`、`_finalize_run` 与租约回收器均不触发队列派发），仅由 `process_agent_run` 在 `completed`（自然结束）或 `steered`（Turn 边界停机及 120s 宽限硬取消）且 `changed=True` 时按 `steer` 优先与 `queue_seq ASC` 晋升下一条排队请求，创建 Run 时读取会话当前配置。

**关键运行不变量：**
- **Interrupt & Resume**：`ask_user` 中断产生 `interrupted` 终态并将问题载荷保存在 `AgentRun.run_metadata["interrupt"]`；恢复时创建新 `AgentRun(run_type="resume", created_by_run_id=parent_run_id)` 复用同一 `thread_id` 与 LangGraph checkpoint，父 Run 不回到 `running`。尚无 `resume` 子 Run 的 `interrupted` Run 阻止新输入、`steer`、队列派发和会话删除，且可通过取消接口直接收敛为 `cancelled` 解锁会话。
- **Cancellation**：`cancel_requested` 仅是中间态；Worker 仅在进入流消费循环后写入 Redis `end` 事件（流前停止只写 PostgreSQL 终态，由 SSE 按 DB 终态兜底）；终态单向，晚到取消不得覆盖已有终态。
- **Stream Decoupling**：Worker 执行不依赖任何单条 SSE 连接，客户端断开不停止 Run，重连继续读取同一 `run_id`。

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
| Run 服务编排 | `server/service/agent_run_service.py` | 会话锁内的策略路由、请求接收与 Run 创建事务、授权校验、提交后入队和事件读取编排 |
| 请求持久化 | `src/database/repositories/agent_run_request_repository.py` | 保存请求及输入关联，查询并返回请求 ORM 记录 |
| ARQ/Redis 适配 | `server/service/arq_queue_servcie.py` | 队列、Stream、取消 key/Pub/Sub 和事件信封，不决定业务终态 |
| Run 执行 | `server/worker.py` | 重载输入、执行 Agent、发布事件和收口终态 |
| Run 持久化 | `src/database/repositories/agent_run_repository.py` | 在事务和行锁内决定状态转换 |
| SSE framing | `server/utils/agent_run_utils.py` | 将 Redis 信封转成公开 SSE，不访问 Redis 或数据库 |

队列只传 `run_id`，使用 `run:{run_id}` 作为 Job ID；SSE 消费者独立读取
`run:events:{run_id}`。`AgentRun.run_type` 表示执行类型；`created_by_run_id` 表示来源 Run，
子任务指向发起委派的 Run，resume 指向被恢复的 Run，普通顶层 Run 为空。两者不能互相替代。

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
