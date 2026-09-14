# Agent Runtime Slice

关联需求：DP-MAO-003、DP-MAO-006、DP-MAO-007、DP-MAO-008  
关联任务：MAO-003

## 1. Files

- `src/third_party/data_platform_client.py`
- `src/agents/subagents/dataplatformagent/__init__.py`
- `src/agents/subagents/dataplatformagent/agent.py`
- `src/agents/subagents/dataplatformagent/context.py`
- `src/agents/subagents/dataplatformagent/prompt.py`
- `src/agents/subagents/dataplatformagent/tools.py`
- `src/agents/leaderagent/agent.py`
- `src/agents/subagents/__init__.py`

客户端集中处理 HTTP、超时和响应校验；SubAgent tools 不复制 HTTP 调用。第一版不增加新的 Agent
middleware、Graph state 或嵌套 SubAgent。

## 2. Context

`DataPlatformAgentContext` 只增加本次 Run 所需的平台 base URL、可信身份 token 和查询/轮询预算。
这些值由外层运行入口注入，不由模型参数、用户消息或模块全局变量覆盖。

## 3. Tools

`tools.py` 提供三个面向任务的工具：

- `find_assets`：有界检索并返回候选摘要。
- `inspect_assets`：批量读取少量候选详情，限制最大 ID 数。
- `process_assets`：提交允许的 operation，等待终态并返回成果与血缘摘要。

不把六个 HTTP 端点一对一暴露成六个低层工具；取消和轮询是 `process_assets` 内部生命周期行为。
工具输出保留资产 ID、job ID、artifact ID、来源、版本、警告和错误 code，不把完整对象内容送入模型。

## 4. Agent behavior

`DataPlatformAgent.get_agent()` 复用现有模型加载、checkpointer 和 store。Prompt 要求先收敛范围，再发现
资产，提交前检查版本与质量，完成后核验成果；信息不足时返回缺失条件，不自行扩大搜索范围。

目标文件：`src/agents/leaderagent/agent.py`，负责方法：`LeaderAgent._create_middlewares`。

```python
create_subagent_middleware(
    subagents=[
        SearchAgent(),
        CitationAgent(),
        DataPlatformAgent(),
    ],
    parent_context=context,
)
```

`DataPlatformAgent` 只增加到内部列表，不进入公共 Agent 列表。

## 5. Cancellation and failures

`process_assets` 捕获 Python task cancellation；若已经取得活动 `job_id`，在重新抛出取消前请求一次
平台取消。平台超时、非法响应和业务错误转换为有稳定 code 的工具结果，不交给模型猜测成功状态。

## 6. Tests

- 客户端超时、错误 envelope 和响应校验
- 工具的查询边界、最大候选数和输出裁剪
- 平台 job 成功、失败、超时和 Python cancellation
- Agent 自动发现与 `LeaderAgent` 内部注册
- 子 Run 的 `run_type`、`parent_run_id` 与结果返回保持现有契约
