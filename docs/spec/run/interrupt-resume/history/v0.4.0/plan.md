# Interrupt 单容器分页

计划版本：v0.4.0

状态：实施与隔离组件验证完成。关联 RUN-HIL-010；后端协议、Resume 调用和其他页面保持不变。

## 实施

- `web/src/components/chat/hil/ChatAskUserComponent.vue` 保留答案字典，增加当前题索引与
  切换方向；只呈现当前题。选择后前进，末题停留，上一题/下一题不提交且保留答案。
- 同组件使用 Vue Transition 和 Tailwind 位移/透明度过渡，不引入轮播依赖或公共抽象
  （ponytail）。保留原有视觉 token、radio 定位修复及完整答案提交门禁。
- 页码、左右按钮与 Continue 位于固定外壳；内容区限高滚动。新 Run 重置，禁用期间
  不接受操作；切换焦点使用 preventScroll，减少动态效果时禁用动画。

## 验证

- 留下一个可运行的浏览器组件回归脚本，覆盖真实鼠标选择、前后切换与答案回显、末题不自动
  提交、完整 value 字典、禁用/重试、新 Run 重置、键盘焦点、长选项与窄屏及减少动态效果。
- 运行类型检查、组件 lint、全仓 lint 与构建；区分既有错误和新增问题。
- 不启动或修改真实后端运行，不将隔离组件验证描述为真实模型端到端验证。

## 验证结果（2026-09-14）

- `web/test/hil-pagination.mjs` 通过：1280×800、375×800、800×375（减少动态效果）。
  使用真实 Vue 组件与 Chrome 鼠标/键盘输入；覆盖同项重选、前后翻页、焦点、单题、完整答案、
  提交禁用与重试、新 Run 重置；断言外层 scrollTop 为 0、无横向溢出。桌面和窄屏截图已查看。
- 运行方式：独立 Chrome 使用 `--remote-debugging-port=9237`；在 web 下执行
  `CDP_URL=http://127.0.0.1:9237 node test/hil-pagination.mjs`。脚本启动临时 Vite，
  使用测试数据，不访问后端；结束后关闭测试标签页和 Vite。
- 类型检查、组件和脚本 ESLint、构建通过；构建保留既有大 chunk 警告。
- 全仓 lint 未通过：既有 LibraryView.vue 未使用变量错误，以及其他组件的 3 个既有警告。
- 未连接真实 PostgreSQL/Redis/模型服务；验证范围为隔离组件，不是后端端到端联调。
