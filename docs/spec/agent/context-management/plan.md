# Implementation Plan: Context Management

## 1. Steps

1. 明确 `worker` 与 `agent` 服务中 context 组装点。
2. 禁止在 agent 执行中直接读取未注入的全局上下文。
3. 在 `stream_thread_response` / `SubAgentMiddleware` 的入口添加注释与参数边界说明。

## 2. Mapping

- `server/worker.py`: `process_agent_run` 构造 `metadata` 与 message
- `server/service/thread_service.py`: `stream_thread_response` 上下文透传
- `src/agents/leaderagent/*`, `src/agents/subagents/*`: 上下文消费端
