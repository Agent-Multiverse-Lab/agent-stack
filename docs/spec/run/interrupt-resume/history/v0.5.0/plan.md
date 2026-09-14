# Interrupt 输入区挂载

计划版本：v0.5.0

用户已确认，只调整挂载位置。关联 RUN-HIL-010。

状态：实施与验证完成。

- ChatView.vue：把现有卡片移到 footer 中的 ChatMessageInputComponent 前，保持 props/emits。
  composerDocked 纳入 pendingInteraction；待回答时限制 footer 最大高度并允许自身滚动。
  此时回到最新消息按钮置于输入区正常布局内，避免被滚动边界裁掉。
- ponytail：复用现有 footer 和卡片，无新组件、状态层或依赖，不修改分页与后端协议。
- 在已有浏览器回归脚本增加真实 ChatView 模板位置断言，并使用输入区挂载布局测试消息滚动
  不改变卡片位置；执行组件回归、lint 和构建。隔离布局不等同于真实后端端到端测试。

## 验证结果

- 真实 ChatView 模板 AST 断言通过：卡片仅一个，在 footer 内且位于文字输入组件之前，
  messageScroller 内没有卡片；底部停靠条件包含 pendingInteraction。
- 浏览器隔离布局使用真实卡片与文字输入组件；1280×800、375×800、800×375（减少动态效果）
  回归通过，覆盖消息滚动不带动卡片、上下顺序及既有鼠标/键盘分页、回答提交与重置；查看窄屏截图。
- 修改文件 ESLint、类型检查、构建与 git diff --check 通过。
- 全仓 lint 仍有 LibraryView.vue 既有未使用变量错误和其他文件的 3 个既有警告；
  构建仅有既有大 chunk 警告。未进行真实后端或完整 ChatView 业务联调。
