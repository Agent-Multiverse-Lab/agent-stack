# Resume 输入与事件接线实施

计划版本：v0.3.0

状态：本轮接线实施与定向验证完成；完整能力的真实服务联调未执行。
保留现有工具、解析、handler、消息保存和终态函数，只补齐恢复入口及前后端调用处的参数、事件接线。

## 1. 现有依赖与边界

直接使用 `ask_user`、`AskHumanPayload`、`parse_interrupt_questions`、中断格式化与构建函数、
`_reslove_agent_interrupt`、异步生成器 `check_agent_interrupt_handler`、运行上下文构建、
`_stream_agent_event_chunks`、消息保存函数、`BaseAgent.stream_message_by_resume` 和
`_finalize_run -> set_run_terminal -> set_agent_terminal`。这些函数的签名和实现保持现状。

父子 Run、鉴权与锁、队列、SSE、新 Run 切换沿用原流程。按 ponytail-review 收敛：
不增加包装器、公共执行器、新表、兼容路径或替代实现。
现有解析函数的单字典行为和空问题默认题属于范围外差异，本次只接入工具原生 questions 列表。

## 2. 实施顺序与落点

1. RUN-HIL-002 至 004、007：`server/entities/agent.py:AgentRunResumeRequest` 与
   `server/service/agent_run_service.py:create_resume_agent_run_service` 将调用输入接为
   `thread_metadata.resume.answers`。Service 按父 Run questions 校验完整键集合及合法 value，
   同请求同回答复用子 Run、同键不同回答拒绝；沿用父 Run 身份并复制 model 配置。
2. RUN-HIL-005、007、008：`server/service/thread_service.py:resume_agent_response` 接收显式
   `resume_input`，获取 LeaderAgent，调用现有上下文构建和会话校验函数，检查待恢复 checkpoint，
   将 `Command(resume=resume_input)` 原样交给现有 BaseAgent 方法。补传 accumulated_msg；
   保存后按现有 handler 签名消费异步生成器；异常调用既有保存函数并输出 error。
3. RUN-HIL-005、006、009：普通入口保留 interrupted、interrupt_type、interrupt_message
   和中断状态解析，暂存 handler 生成的中断 chunk；删除前面的重复保存调用，checkpoint 保存
   成功后才发出暂存的中断 chunk 并返回，只有正常结束才发送 finished。恢复入口同样在保存后
   消费 handler，中断后返回。
   `server/worker.py:process_agent_run` 调用恢复入口时传 answers；
   按 handler 现有 ask_human/pending_interrupt 字段调用既有 `_finalize_run(status="interrupted")`。
   保留三个停止分支的终态调用与发布规则；无停止信号时调用既有失败收口，取消检查使用 await。
4. RUN-HIL-009 至 011：`server/entities/thread.py:InteractionRequired`、`web/src/types/chat.ts`、`useAgentRun` 的交互事件读取、
   `ChatAskUserComponent.vue` 与 `ChatView.vue:submitResume` 接入 questions/answers。
   每题独立单选，全部回答后一次提交 label 对应的 value；父 Run 变化清空选择。
   页面继续使用现有恢复 API、Run 切换与线程详情读取。

### 核心调用示例

`server/service/thread_service.py:resume_agent_response`：

```python
stream_events = agent_instance.stream_message_by_resume(
    Command(resume=resume_input), runtime_context=agent_runtime_context,
)
# 消费现有事件转换器并保存后：
async for interrupt_chunk in check_agent_interrupt_handler(
    agent_instance=agent_instance,
    runtime_metadata=runtime_metadata,
    chunk_iterator=make_agent_resume_event,
    context=agent_context,
):
    yield interrupt_chunk
    return
```

`server/worker.py:process_agent_run` 的中断分支读取 `pending_interrupt`，向现有终态函数传
`status="interrupted"` 和问题 payload。不改变 handler、chunk builder 和终态函数实现。

`web/src/views/ChatView.vue:submitResume` 提交示例：

```json
{"thread_id":"thread-1","thread_metadata":{"request_id":"resume-request-1","resume":{"answers":{"database":"postgresql","environment":"local"}}}}
```

## 3. 失败与验证

- 请求/Service：漏答、多答、非法 value、无效问题结构、越权、错线程、重复恢复和幂等冲突。
- 恢复入口：原字典进入 Command，同 thread/uid checkpoint；初始化、缺失 checkpoint、执行和保存失败输出 error。
- 真实内存 checkpoint：正式 ask_user 两题暂停、恢复为关联原 tool_call_id 的 ToolMessage，再次中断。
- Worker：恢复分支不读取 HumanMessage；handler 事件能进入既有中断终态调用；无停止信号失败。
- 前端：两题独立选择、全答后提交、label/value、切换 Run 和线程详情恢复；执行构建与可用的浏览器验证。
- 源码检查：受保护函数体不变；git diff --check；按 docs/development.md 执行定向检查。

本轮不部署、不迁移。真实数据库/队列/模型未验证时明确记录，不以构建或内存测试替代线上证据。

## 4. 验证记录（2026-09-14）

- `.venv/Scripts/python.exe -m unittest test.test_agent_run_interrupt_resume test.test_ask_user_tool`：
  19 个测试通过。覆盖 Service 输入、身份、模型继承与幂等；真实内存 checkpoint 多题恢复和再次中断；
  普通入口保留状态解析、保存一次、保存后才发中断及失败后不发 finished；Worker 参数与中断/取消/协议错误接线。
  数据库、队列和模型被隔离，checkpoint 为真实 InMemorySaver。
- `npm.cmd run build`：类型检查与 Vite 构建通过；存在现有大体积 chunk 提示。
- 本地无界面 Edge 加载真实问题组件与 useAgentRun，模拟 Thread/Resume/SSE API：
  两题独立选中、全答后提交 value、新 Run SSE 再次提问、父 Run 切换清空、刷新恢复通过；
  390px 和 1280px 视口无横向溢出。临时测试页及脚本在验证后清理。
- 变更文件 compileall、git diff --check 通过；AST 比对确认现有 handler、解析、上下文、
  流转换、保存与终态辅助函数保持不变；工具、解析文件、BaseAgent 和 Run Repository 无差异。

限制：未连接真实 PostgreSQL/Redis/ARQ 或模型服务，未验证真实消息落库去重与线上恢复。
现有解析函数的单字典行为、空列表默认题保留原样，不属于本轮实施范围；不据此宣称整个 spec 已验收。
