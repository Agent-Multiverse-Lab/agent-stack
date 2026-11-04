# Chat 消息组件统一接入计划

## 当前任务

重构 `web/src/pages/chat/` 消息展示组件，使所有会话消息通过单一入口组件 `ChatMessage` 接入，组件内部通过分支子组件渲染具体区域。

## 任务目标

消除 UI 组件层的 `unknown` 类型强转与 `RunMessages`/`ChatMessage` 嵌套乱象，建立“数据归约层 → 单一入口组件 → 区域分支子组件”的清晰架构。落地过程区去容器化、单线时间线串联、正文/状态物理隔离，并支持正文后出现工具调用时的动态回退与计时/动画恢复。

## 如何修改

- 在 `web/src/pages/chat/types.ts` 定义 `ChatRenderItem` 与 `AgentContentBlock` 等强类型视图契约，消灭 `ToolCall` 等处的 `unknown` 事件并强制携带 `messageId`。
- 在 `ConversationMessages.tsx` 将消息聚合与过程拆分提炼为纯函数 `buildChatRenderItems`，列表只遍历渲染 `ChatMessage`。
- 将 `ChatMessage.tsx` 改造为单入口组件，将人类气泡、Markdown、Reasoning、AgentTasks 与 Run 聚合区分离为独立子组件。
- 在接入组件 `AgentRunSection` 保留活跃 Run 的流式 `answerReceivedAt` 引用，支持正文后新工具到达时重置并恢复计时与展开动画；历史静态消息直接由纯函数依据持久化字段计算耗时。
- 过程区内状态组件彻底去容器化，移除多余卡片边框与胶囊背景，全程由一条连续垂直时间线导轨连接，以 `[状态Icon + 名称 + 状态文字]` 紧凑呈现；等宽字体严格限定于参数与日志，思考全文保留自然文本排版。

## 实施步骤（计划）

1. 定义视图模型接口与转换纯函数，负责消息按 Run 归组、动态末尾判定、清洗强类型 ToolCall 与稳定提取真实 `messageId`。
2. 拆分人类气泡、Markdown、思考链、任务清单及 Run 过程子组件，落实去容器化、单线时间线样式与双态时间戳计算。
3. 改造 `ChatMessage` 为统一接入入口，收敛 `ConversationMessages` 为纯容器。
4. 执行 TypeScript 类型检查、ESLint、组件单元测试与构建验证。
5. 执行真实浏览器验证，核验流式输出、动态回退恢复、代码块滚动、浅深色对比度与审批交互。

## 验收标准

- **架构与类型**：所有会话消息项统一经由 `ChatMessage` 挂载，各子组件直接接收强类型 Props，不再包含 `unknown` 类型解析；所有节点基于真实 `messageId` 索引。
- **动态回退与时间冻结**：
  - 正文后再次触发工具调用时，正文自动回退为时间线上的过程节点，`Thinking` 自动恢复展开、恢复流水动画与实时计时；
  - 历史已终态 Run 依据持久化时间戳幂等呈现耗时，活跃 Run 在真正回答到达时精准冻结耗时。
- **视觉与交互规范**：
  - 过程区各状态组件之间仅有一条垂直连续时间线导轨相连，无多余卡片边框或药丸嵌套；
  - 状态区整体呈微弱次级灰（`muted-foreground/90`、`muted-foreground/60`），最终回答呈现高对比正文主色（`text-foreground`）；
  - 外层过程折叠/展开不影响内层工具与思考链的局部展开选择；等宽字体仅作用于参数与日志，思考全文保留常规排版。
- **真实验收通过**：
  - `npm run typecheck`、`npm run lint`、`npm test`、`npm run build` 全部无错误通过；
  - 浏览器真实交互验证通过：流式思考输出、正文后新工具调用的回退恢复、工具展开滚动、等待审批（`AskUser`）承接、浅色与深色主题下的视觉对比度无喧宾夺主。
