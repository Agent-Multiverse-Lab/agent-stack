# 实施任务

- [x] 定义 `ChatRenderItem` 与 `AgentContentBlock` 判别联合类型及归约纯函数（强类型 ToolCall，全链路携带 messageId）。
- [x] 拆分人类气泡、Markdown、Reasoning、AgentTasks 与 AgentRun 分支子组件，落实去容器化、单线时间线串联与参数等宽/思考自然字体区隔。
- [x] 实现动态末尾判定与时间戳双态处理：活跃 Run 流式 answerReceivedAt 记忆与正文后新工具调用的回退/计时动画恢复。
- [x] 重构 `ChatMessage` 为统一接入组件并收敛 `ConversationMessages` 为纯容器。
- [x] 运行静态代码检查与单测：TypeScript 类型检查、ESLint、Vitest 组件单元测试（82 passed）与 Vite 构建打包。
- [ ] 运行浏览器真实交互验收：
  - [ ] 验证流式思考与正文动态流出；
  - [ ] 验证正文后再次调用工具时的动态回退与计时/动画恢复；
  - [ ] 验证外层折叠/展开不影响内层展开状态，工具参数与长日志正常滚动；
  - [ ] 验证浅色与深色主题下的视觉对比度（确保状态区低调不喧宾夺主，正文清晰醒目）；
  - [ ] 验证等待审批（`AskUser`）在时间线后的正常呈现与承接。
