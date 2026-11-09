# Implementation Plan: Subagent Delegation

计划版本：v0.1.0

## Steps

1. 确保父子 run 创建时显式写入 `run_type` 与 `created_by_run_id`。
2. 所有子代理调用路径集中在 `SubAgentMiddleware` 入口。
3. 取消路径复用 `request_cancel_agent_run` 的 active child run 标记。
4. 将父子会话关系迁移到 `subagent_conversation_relation`，并由关系表承载会话树查询与软删除。

## Mapping

- `src/agents/middlewares/subagent_middlware.py`: 子代理调用与取消传播
- `server/service/agent_run_service.py`: 运行类型与 `created_by_run_id` 传入
- `src/database/repositories/agent_run_repository.py`: `list_active_child_runs`
- `src/database/repositories/conversation_repository.py`: 父子会话关系创建、树查询和软删除
