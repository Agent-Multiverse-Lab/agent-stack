# Implementation Plan: Context Management
计划版本：v0.1.0

状态：代码与定向验证已完成。关联 AG-CONT-001 至 AG-CONT-003。

## 1. 实施落点

- `server/worker.py:process_agent_run()`：记录运行参数来源；从持久化 Run 读取身份并覆盖 metadata 同名值。
- `server/service/thread_service.py:_build_agent_runtime_context()`：深拷贝 SQL 预设，注入受信任身份，
  在入口确定模型值。普通执行和 Resume 共用此入口，运行期间不重新读取角色配置。
- `src/agents/base_context.py:BaseContext.model`：声明直接构造 Context 时使用的应用默认模型。
- `src/agents/buildin/leader/agent.py`、`src/agents/buildin/subagents/subagent_graph.py`、
  `src/agents/middlewares/summary_middleware.py`：构图和摘要只读取 Context 中已确定的模型。
- `src/agents/middlewares/subagent_middlware.py:SubAgentMiddleware`：说明父 Context 与子 Run 配置边界。

## 2. 核心示例

目标文件：`server/service/thread_service.py`，负责函数：`_build_agent_runtime_context()`。

```python
agent_runtime_context = deepcopy(defaults or {})
agent_runtime_context.update({
    "uid": uid,
    "run_id": run_id,
    "thread_id": thread_id,
    "request_id": request_id,
})
agent_runtime_context["model"] = model or agent_runtime_context.get("model") or config.default_model
if parent_run_id:
    agent_runtime_context["parent_run_id"] = parent_run_id
```

目标文件：两个执行类及摘要中间件，负责方法：`LeaderAgent._build_agent()`、
`SubAgentGraph.get_agent()`、`create_summary_middleware_from_context()`。
这些调用统一从 Context 获取模型，运行中不再读取全局默认模型进行兜底。

## 3. 验证结果

与 Agent 构造、流式响应、委派、Resume、摘要和 PostgreSQL 接线的定向用例一起运行：
52 项测试及 30 个子用例通过。新增用例检查模型默认值快照与受信任身份覆盖；
既有用例覆盖模型选择、嵌套配置隔离和 Resume 参数。

```bash
.venv/bin/python -m pytest -q test/test_agent_construction.py test/test_thread_stream_events.py test/test_subagent_middleware_prompt.py test/test_agent_run_interrupt_resume.py test/test_image_processing_agent.py test/test_ask_user_tool.py test/test_summary_middleware.py test/test_langgraph_postgres_persistence.py
```

定向用例使用模拟模型；真实外部模型调用不属于这些测试已经证明的范围。
