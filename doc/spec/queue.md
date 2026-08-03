# Queue

当前代码中的队列是 **ARQ + Redis** 的组合，不是一个包含全部逻辑的单独队列类。它把
Agent Run 的提交、执行、事件传递和取消拆成不同角色，让 API、Worker 和事件消费者可以
独立运行。

## 队列组成

| 角色 | 文件 / 类 | 关键参数或职责 |
| --- | --- | --- |
| 入队 | `server/service/queue_service.py::enqueue_agent_run(run_id: str)` | 只把 `run_id` 放入 ARQ，Job ID 为 `run:{run_id}`，队列名来自 `config.arq_queue_name` |
| Worker | `server/worker.py::WorkerSettings` | `functions`、`queue_name`、`redis_settings`、`max_jobs`、`on_startup`、`on_shutdown` |
| 执行 | `server/worker.py::process_agent_run(ctx, run_id)` | 根据 `run_id` 恢复输入，调用 `stream_agent_response`，发布运行事件 |
| 事件生产 | `server/service/arq_queue_servcie.py::write_agent_run_stream_event` | `run_id`、`event`、`ttl_seconds`；写入 `run:events:{run_id}` |
| 事件消费 | `server/service/queue_service.py::stream_agent_run_events` | `run_id`、`current_uid`、`thread_id`；把 Redis Stream 转成 SSE |
| 取消 | `server/service/agent_run_service.py::request_cancel_agent_run` + Redis Pub/Sub | 持久化取消请求后写 `run:cancel:{run_id}`，并向 `run:cancel` 发布运行标识 |

## 主链路

```text
提交 Run
  -> enqueue_agent_run(run_id)
  -> ARQ 调度 process_agent_run(ctx, run_id)
  -> Worker 调用 Agent Runtime
  -> write_agent_run_stream_event(run_id, event)
  -> stream_agent_run_events(run_id, ...)
  -> SSE 客户端消费
```

取消链路是另一条并行通道：

```text
取消请求
  -> run:cancel:{run_id}
  -> run:cancel Pub/Sub
  -> Worker 的取消监听
  -> 停止当前 Agent 流
  -> 发布 cancelled 终止事件
```

## 解耦方式和设计原则

1. **任务与请求解耦**：提交侧只传 `run_id`，不把 Agent 实例、数据库会话或完整消息对象
   放入队列；Worker 根据运行标识恢复所需输入。
2. **执行与消费解耦**：Worker 负责执行和写事件，SSE 只读取事件；打开 SSE 不会触发
   Worker，断开 SSE 也不等于取消运行。
3. **通道职责分离**：ARQ 负责任务投递，Redis Stream 负责有序事件，Pub/Sub 负责唤醒取消
   监听，取消 Key 负责在监听前后保留信号，四者不互相替代。
4. **跨进程只传可序列化标识**：API 与 Worker 不共享 Python 对象，`run_id` 是任务、事件、
   取消和子 Agent 关联的共同句柄。
5. **父子 Run 复用同一条链路**：Sub-agent 创建自己的 `run_id` 后仍然进入
   `enqueue_agent_run`，不在父 Agent 进程内另起一套执行机制。

## 事件示例

`server/worker.py::StreamEventSmoother` 的参数是 `thread_id`、`run_id`、
`character_limit`。它把连续的模型消息合并后再写入 Stream，减少过细的事件；工具事件、
状态事件和终止事件则按独立事件类型发布。
