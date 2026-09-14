# Tasks: Chat Thinking Group

## Ordered work

1. 提取并验证 3×3 像素流动 icon。
2. 组合 Thinking Group 的标题、计时和可选内容区。
3. 删除 Loading 中转组件，在 ChatView 中直接复用 Thinking Group，并把当前 Run 的有效 Tool 状态作为独立同级组件保留。
4. 执行 TypeScript、ESLint 和 diff 检查。

## Done Conditions

- icon 外形、错峰延迟和流动动画保持不变；
- Thinking Group 不依赖模拟阶段或虚构消息；
- Conversation 加载和 Agent Thinking 不通过额外的 Loading 中转组件；
- 当前 Run 尚无 Assistant 文本时，Thinking 与有效活动状态依次同级显示；
- 当前 Run 出现 Assistant 文本或等待用户交互后不再显示 Thinking Group；
- Thinking 卸载和 Run 终态收口不删除当前页面已有的 Tool 组件；
- 减少动态效果时动画停止，状态文本仍可读取；
- 定向检查通过并如实报告。
