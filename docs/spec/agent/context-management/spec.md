# Context Management Spec

## 1. Invariant

Agent 的 `context` 由以下来源合并，且每次执行只读一次：

1. 运行时配置（`AgentRun` 触发数据）
2. 数据库持久化参数（如 agent 配置）
3. 用户输入消息与 metadata

## 2. Requirements

### AG-CONT-001
禁止从全局环境直接注入运行参数；所有上下文都应明确从入口参数传入。

### AG-CONT-002
同一 run 运行期间上下文不可热更新；若需更新，需发起新 run。

### AG-CONT-003
`LeaderAgent` 与 `SubAgent` 的上下文构造入口必须可追踪到具体调用点。

## 3. Example

```python
# worker / service 组装上下文示例（概念化）
runtime_context = {
    "uid": agent_run.uid,
    "thread_id": agent_run.thread_id,
    "agent_id": agent_run_event.agent_id,
    "metadata": agent_run_metadata,
    "message": build_agent_input_msg(...),
}
```

## 4. Acceptance

- 运行上下文的输入点可以审计
- context 与 DB 主状态无耦合（不会直接修改 run 状态）
