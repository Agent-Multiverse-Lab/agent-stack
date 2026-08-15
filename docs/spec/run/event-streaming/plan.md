# Implementation Plan: Run Event Streaming

## 1. Event Pipeline

1. worker 将 `running/messages/values/agent_execute_event` 写入 stream；
2. 终态路径写 `type=end`；
3. SSE endpoint `stream_agent_run_events` 逐条消费，遇到 `type=end` 退出。

## 2. Mapping

- `server/service/arq_queue_servcie.py`: `write_agent_run_stream_event`, `read_agent_run_events`
- `server/service/agent_run_service.py`: `publish_agent_run_event`, `stream_agent_run_events`
- `server/worker.py`: 运行时写事件点
- `server/router/agent_router.py`: `/events/{run_id}` SSE 响应

## 3. Fallback

- 如果数据库已终态且 stream 未及时结束，`stream_agent_run_events` 必须补齐最终 `messages` + `end`，防止前端长期空转。
