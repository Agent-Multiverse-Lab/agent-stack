# Implementation Plan: Subagent Delegation

计划版本：v0.1.0

## Steps

1. 确保父子 run 创建时显式写入 `run_type` 与 `parent_run_id`。
2. 所有子代理调用路径集中在 `SubAgentMiddleware` 入口。
3. 取消路径复用 `request_cancel_agent_run` 的 active child run 标记。

## Mapping

- `src/agents/middlewares/subagent_middlware.py`: 子代理调用与取消传播
- `server/service/agent_run_service.py`: 运行类型与 `parent_run_id` 传入
- `src/database/repositories/agent_run_repository.py`: `list_active_child_runs`
