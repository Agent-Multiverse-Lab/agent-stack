# Interrupt 选项数量上限

计划版本：v0.6.0

状态：实施与定向验证完成。范围仅限新提问的每题选项数量，不限制一轮问题数。

- `src/agents/leaderagent/tools.py`：给 HumanQuestion.options 添加 min_length=1、max_length=3，
  字段和工具说明明确优先 3 个、最多 3 个，不凑数。
- `test/test_ask_user_tool.py`：验证公开 Schema 的 minItems/maxItems，以及 3 个允许、4 个和空列表拒绝。
- ponytail：复用 Pydantic 输入校验，无截断逻辑、前端兼容层或新增依赖；已有待回答问题保持原样。
- 执行工具定向测试和 diff 检查；部署后端变更需要重新构建 Worker 镜像，不自动操作运行中服务。

## 验证结果（2026-09-14）

- `LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false .venv/bin/python -m unittest -v
  test.test_ask_user_tool test.test_agent_run_interrupt_resume`：20 个测试通过，正常退出。
  覆盖 0/1/2/3/4 个选项输入、公开 Schema 上限、3 选项真实内存 checkpoint 恢复及既有 Run 流程。
- 沙箱内测试断言通过但在 asyncio shutdown_default_executor 阶段挂起；中止后在沙箱外复测通过。
- 修改文件 compileall 和 git diff --check 通过。未重建或重启 Worker，未调用真实模型或数据库服务。
