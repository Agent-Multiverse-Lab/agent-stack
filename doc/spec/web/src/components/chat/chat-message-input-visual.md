# Chat Message Input 视觉与过渡规格

## 1. 设计方向

Chat 输入区服务于技术学习与 Agent 协作场景，唯一任务是让用户清楚地组织正文、附件和发送动作。
视觉方向是紧凑的“工作台”，不是功能展示台。

- 色彩沿用现有 `paper`（`#ffffff`）、`mist`（`#f7f7f7`）、`graphite`（`#0d0d0d`）、`slate`（`#6b6b6b`）和 `danger`（`#d00e17`）。
- 正文继续使用现有 sans 字体；不为输入区增加展示字体。
- 识别特征是一个安静、连续的大圆角容器：附件是上下文，正文是主体，附件入口与发送动作分居两端。
- 不复制参考稿的彩虹 Shader、自动演示、模型选择、听写、`@` 数据源、`/` 命令或品牌菜单。

## 2. 整体布局

保留当前 `ChatView.vue` 的页面布局：空会话时输入区位于页面中部，产生消息后停靠底部；消息宽度和输入区宽度保持现状。

输入组件仍只有三种布局：

```text
单行
[附件入口] [正文                              ] [发送/取消]

真实换行
[正文                                              ]
[附件入口]                                  [发送/取消]

存在附件
[附件胶囊，可自动换行                              ]
[正文或当前单行/多行控件布局                       ]
```

附件区与正文之间不用分割线，不增加模型选择器或其他中间控件。`ResizeObserver` 继续根据真实高度决定单行或多行，不按字符数量猜测。

## 3. 内部样式

- 输入容器恢复原有 `rounded-[1.7rem]` 大圆角，单行、多行和附件状态共用这一圆角。
- 容器使用现有 `paper` 背景、轻边框和低对比阴影；聚焦时只略微提高边框与阴影强度。
- 内边距收紧，附件入口与发送按钮保持圆形，正文编辑区不增加独立背景或边框。
- 附件入口使用浅 `graphite` 背景；发送按钮使用实心 `graphite`，禁用时降为低对比背景。
- 附件胶囊继续放在同一个输入容器内部，允许换行，并保持可移除操作。
- `ChatActionMenuComponent.vue` 保持全宽面板与现有内容；展开方向遵循
  [Chat Action Menu 规格](chat-action-menu.md)：居中输入框向下展开，底部输入框向上展开。
- 输入区所有仅以图标表达含义的可见操作使用 Ant Design Vue `ATooltip`：
  Action Menu 显示 `Action menu`，发送按钮根据状态显示 `Send` 或 `Cancel`，
  附件删除按钮显示 `Remove <文件名>`；Tooltip 文案与按钮 `aria-label` 对齐。

## 4. 过渡动画

全部使用 Vue Transition 与 Tailwind/CSS，不引入 `glimm`，也不使用 GSAP。

- 输入容器的边框与阴影在 `150ms` 内过渡。
- 加号菜单沿用现有旋转和面板淡入、轻微位移与缩放；纵向位移方向与面板展开方向一致。
- 附件列表改用 `TransitionGroup`；附件添加和移除使用约 `160ms` 的透明度、轻微缩放与纵向位移。
- 发送与取消图标使用约 `120ms` 的淡入和轻微缩放切换，按钮本身位置不变。
- hover、active 和 disabled 只改变颜色或轻微缩放，不添加循环动画。
- 所有新增动画继续尊重 `prefers-reduced-motion`；关闭动画后，状态与操作仍完整可见。

## 5. 边界与公共契约

- 不修改 `v-model`、props、emits、上传、提交、取消、拖拽、粘贴、键盘或输入法组合态行为。
- 除 Action Menu 方向合同外，不修改 `ChatView.vue` 和 `ChatActionMenuComponent.vue` 的其他行为；不修改 Attachment DTO、Chat API、Store、Worker 或后端协议。
- 不增加组件、Composable、样式文件、依赖或主题 Token。

## 6. 文件级修改计划

1. 修改 `web/src/components/chat/ChatMessageInputComponent.vue`：
   - 收紧容器、编辑区和控件的 Tailwind 样式；
   - 把输入容器圆角恢复为 `rounded-[1.7rem]`；
   - 为附件列表增加 `TransitionGroup`；
   - 为发送与取消图标增加 Vue Transition；
   - 使用现有 `ATooltip` 包装发送/取消按钮，并按运行状态切换文案。
2. 修改 `web/src/components/chat/ChatActionMenuComponent.vue`：
   - 使用现有 `ATooltip` 包装 Action Menu 图标按钮。
3. 修改 `web/src/components/AttachmentComponent.vue`：
   - 使用现有 `ATooltip` 包装可移除附件的删除图标按钮，并在文案中包含文件名。

## 7. 验证

```bash
cd web
npm run typecheck
npm run lint
npm run build
cd ..
git diff --check -- web doc/spec/web/src/components/chat/chat-action-menu.md doc/spec/web/src/components/chat/chat-message-input-visual.md
```

浏览器人工确认：

- 空会话居中和会话后底部停靠位置不变；
- 单行、多行与附件布局不回退，正文最大高度仍为 `180px`；
- 附件添加与移除、发送与取消切换连续且没有布局跳动；
- 加号菜单的内容、功能和全宽尺寸不变；
- Action Menu、发送/取消和附件删除按钮在悬停或键盘聚焦时显示对应 Tooltip；
- 空会话时 Action Menu 在输入框下方，输入框停靠底部后 Action Menu 在输入框上方；
- Enter、Shift+Enter、中文输入法、选择/拖入/粘贴附件保持可用；
- reduced motion 下没有残留缩放或位移动画；
- 桌面端与窄屏下控件不溢出输入容器。
