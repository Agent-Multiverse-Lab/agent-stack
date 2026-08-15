# Subagent Delegation Spec

## 1. Context

子代理只作为 Parent agent 的编排能力，不应绕过主 run 流程直接持久化关键状态。

## 2. Requirements

### AG-SUB-001
调用子代理必须通过 `SubAgentMiddleware`。父代理只通过约定的工具调用方式发起。

### AG-SUB-002
子任务 run 使用 `run_type="subagent"`，并保留 `parent_run_id` 形成执行树。

### AG-SUB-003
子代理取消遵循父 run cancel 触发路径：`request_cancel_agent_run` 递归标记子 run。

### AG-SUB-004
子代理状态读取只允许返回运行输出，不参与父级输出消息拼接的持久化决策。

## 3. Example

```python
# 中间件触发子 run 的逻辑位置（概念）
sub_run_id = await create_agent_run_service(..., run_type="subagent", parent_run_id=run_id)
await enqueue_agent_run(sub_run_id)
```

## 4. Acceptance

- 所有子代理都可追溯到 parent run
- 主 run 与子 run 的生命周期一致性可读
