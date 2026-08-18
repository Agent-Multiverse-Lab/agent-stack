019fe66a-7a7f-7433-b837-cb141a8cf369# Knowledge 三栏组件架构设计

## 背景与目标

Knowledge 页面由三个一级区域组成：Files、Chat、Tools。三个区域各自只有一个根组件，
其余 Knowledge 页面组件都必须属于其中一个区域；`KnowledgeView.vue` 只负责页面布局和
跨区域状态，不是第四个业务区域。

本轮目标不是简单把现有 8 个组件搬进三个目录，而是让组件边界与页面真实职责一致：

- Files 负责添加文档、搜索文件以及显示文件处理状态；
- Chat 是纯粹的 Knowledge 对话区域，显示对话和当前对话中的知识库工具状态；
- Tools 上半区提供可执行工具，下半区显示当前工具的运行状态。

本设计只确定前端组件边界、状态所有权和交互方向，不定义新的后端 API、SSE 事件或
持久化状态合同。文档中的工具状态均为前端展示职责，不能直接等同于 `AgentRun`、
`ToolMessage` 或其他后端状态。

## 目标组件树

```text
web/src/views/KnowledgeView.vue
├── files/KnowledgeFilesComponent.vue
│   ├── Add Sources 上传按钮                         # 内联，不单独建组件
│   ├── Search files 输入区                          # 内联，不单独建组件
│   └── KnowledgeFileStatusComponent.vue             # 文件列表、空状态、文件处理状态
│       ├── v-for 直接渲染文件行                     # 不建立 Item 组件
│       └── KnowledgeFileActionsMenuComponent.vue    # 每行的文件操作菜单
├── chat/KnowledgeChatComponent.vue
│   ├── KnowledgeConversationComponent.vue           # 对话内容与滚动边界
│   │   └── KnowledgeChatToolStatusComponent.vue     # 对话轮次中的知识库工具状态
│   └── KnowledgeComposerComponent.vue               # 纯文本输入
└── tools/KnowledgeToolsComponent.vue
    ├── KnowledgeToolListComponent.vue                # 上半区，可用工具入口
    │   └── v-for 直接渲染工具按钮                   # 不建立单个 Tool 组件
    └── KnowledgeToolRunStatusComponent.vue           # 下半区，当前工具运行状态
```

三个根组件仅由 `KnowledgeView.vue` 编排。目录内的组件只能服务于所属区域，不跨目录
引用其他区域的内部组件。

## 目录结构

```text
web/src/components/knowledge/
├── files/
│   ├── KnowledgeFilesComponent.vue
│   ├── KnowledgeFileStatusComponent.vue
│   └── KnowledgeFileActionsMenuComponent.vue
├── chat/
│   ├── KnowledgeChatComponent.vue
│   ├── KnowledgeConversationComponent.vue
│   ├── KnowledgeChatToolStatusComponent.vue
│   └── KnowledgeComposerComponent.vue
└── tools/
    ├── KnowledgeToolsComponent.vue
    ├── KnowledgeToolListComponent.vue
    └── KnowledgeToolRunStatusComponent.vue
```

不增加每个区域内部的 `components/` 子目录，不建立 `index.ts` 聚合导出。

## Files：文档来源、搜索与文件状态

`KnowledgeFilesComponent.vue` 是左栏根组件，依次编排以下三个内容区域：

1. `Add Sources`：只是上传文档的按钮和文件选择入口；它不代表独立的 Source 模型、
   Source Provider 或来源选择器，因此直接内联在根组件中，不建立
   `KnowledgeSourcePickerComponent`。
2. `Search files`：文件名搜索输入区直接内联在根组件中，由根组件持有输入值和已提交
   查询，不为一个输入框建立独立组件。
3. 文件状态：`KnowledgeFileStatusComponent.vue` 显示空状态、文件列表、选中态以及
   `KnowledgeFileItem.status` 对应的处理状态。

### 文件行

`KnowledgeFileStatusComponent.vue` 使用原生列表语义和 `v-for` 直接渲染文件行。文件行只
包含文件图标、名称、处理状态、选中态和操作菜单，不建立
`KnowledgeFileListItemComponent.vue`。

`KnowledgeFileStatusComponent.vue` 接收文件集合和当前选中文件 ID，并向
`KnowledgeFilesComponent.vue` 发出 `select` 与 `remove` 事件。它不直接修改页面级文件
集合。

### 文件操作菜单

`KnowledgeFileActionsMenuComponent.vue` 保留为独立组件，因为它拥有完整且可扩展的交互
职责：

- 渲染当前文件可用的操作；
- 隔离菜单点击与文件行选择；
- 处理打开、下载等浏览器侧行为；
- 在删除前显示确认，并向上发出 `remove` 事件；
- 后续真实新增的文件 Action 继续集中在此组件中。

菜单只显示已经具备真实行为的操作，不为 Rename、Parse、Index 等未来能力保留 Disabled
占位项。菜单不直接修改文件集合，也不调用尚未确定的后端服务。

## Chat：Knowledge 对话

`KnowledgeChatComponent.vue` 是中栏根组件。它是 Knowledge 页面自己的 Chat，不复用普通
Chat 的附件交互，也不把右侧内容生成工具的运行状态混入对话区域。

### 对话显示

`KnowledgeConversationComponent.vue` 负责消息显示、空状态和滚动边界。初始实现直接循环
渲染简单消息，不为纯展示消息预先建立 Message Item 组件；只有消息结构出现真实分支时
再提取对应组件。

与某一轮对话相关的知识库工具状态由
`KnowledgeChatToolStatusComponent.vue` 渲染，并按发生顺序出现在该轮对话中。例如知识库
检索、来源读取等过程状态属于这里。它不是一个固定悬浮的全局状态栏。

### 输入区与来源边界

`KnowledgeComposerComponent.vue` 只提供文本输入和提交，不显示通用附件按钮。

- 用户在当前对话临时上传的文件才属于对话附件；当前设计不加入该能力。
- 引用其他知识库时，该对象属于 Knowledge Source 或 Context Reference，不是附件；当前
  设计不提前建立来源选择组件或数据合同。
- 当前知识库是对话的默认上下文，不要求用户在每次发送消息时重复添加。

## Tools：工具入口与运行状态

`KnowledgeToolsComponent.vue` 是右栏根组件。Header 下方固定分为上下两个等高区域，中间
保留一条横向分割线。

### 上半区：可用工具

`KnowledgeToolListComponent.vue` 显示当前可用的 Road Map、PPT、Slides 等工具，并使用
`v-for` 直接渲染同构按钮。单个按钮只负责展示和发出 `activate(toolId)`，当前没有足够的
独立职责建立 `KnowledgeToolComponent.vue`。

工具列表只负责说明“可以使用哪些工具”，不显示运行进度，也不直接维护任务结果。

### 下半区：工具运行状态

`KnowledgeToolRunStatusComponent.vue` 显示当前选中工具的执行过程。用户点击 PPT 后，
`KnowledgeToolsComponent.vue` 立即把下半区切换到 PPT 的运行视图；真实进度和终态由后续
确认的执行数据源更新，不在组件内伪造后端运行结果。

下半区至少区分：

- 当前没有工具任务；
- 当前工具正在处理；
- 当前工具已经完成；
- 当前工具处理失败。

这些名称是前端展示状态，不构成后端状态枚举。右栏工具运行状态与中栏对话工具状态是
两个独立合同，不能复用同一份状态对象。

## 状态所有权

- `KnowledgeView.vue` 持有文件集合、当前选中文件、两侧收纳状态以及三栏 Grid；只把被
  多个区域使用的数据或影响页面布局的状态放在这里。
- `KnowledgeFilesComponent.vue` 持有文件搜索输入和过滤状态，并协调上传入口与文件状态
  列表。
- `KnowledgeChatComponent.vue` 持有 Knowledge 对话投影；Composer 的草稿仍由
  `KnowledgeComposerComponent.vue` 自己持有。
- `KnowledgeToolsComponent.vue` 协调当前激活工具与下半区运行视图；子组件不直接调用
  执行服务。
- 子组件只接收所属区域所需的 Props，并通过语义明确的事件向所属根组件报告交互。

## 保持与删除的边界

保持不变：

- 三栏 Grid 比例 `1 : 1.92 : 1`；
- Files 与 Tools 的独立收纳行为和 GSAP 动效；
- `720px` 以下的 `Chat → Files → Tools` 纵向布局；
- `KnowledgeFileItem` 及其既有文件状态含义；
- Knowledge 页面与 Library 页面继续保持独立。

删除或替换：

- 删除 `KnowledgeFileListItemComponent.vue`；
- 用 `KnowledgeFileStatusComponent.vue` 替换只负责列表转发的
  `KnowledgeFileListComponent.vue`；
- 删除单张卡片包装 `KnowledgeToolComponent.vue`；
- 将右栏根组件从 `KnowledgeFileActionsComponent.vue` 改为
  `KnowledgeToolsComponent.vue`；
- 删除 Files 与 Tools 已不再使用的 Drawer 分支、`presentation` / `open` / `close` 合同、
  `KnowledgePanelPresentation` 类型和对应 Drawer 样式；
- 不增加通用 `Panel`、`Container`、`Layout`、Composable、Action Registry 或状态适配层。

## 文件级修改计划

1. 创建 `files/`、`chat/`、`tools/` 三个目录并移动各自根组件与保留的子组件。
2. Files：
   - 保留 `KnowledgeFilesComponent.vue` 中内联的 Add Sources 和 Search；
   - 新建 `KnowledgeFileStatusComponent.vue`，合并现有 List 与 Item 的有效模板和事件；
   - 保留并移动 `KnowledgeFileActionsMenuComponent.vue`，删除未实现的菜单占位项；
   - 删除原 `KnowledgeFileListComponent.vue` 和
     `KnowledgeFileListItemComponent.vue`。
3. Chat：
   - 移动 `KnowledgeChatComponent.vue` 与 `KnowledgeComposerComponent.vue`；
   - 新建 `KnowledgeConversationComponent.vue` 与
     `KnowledgeChatToolStatusComponent.vue`；
   - Composer 保持纯文本输入，不接入通用 Attachment 组件。
4. Tools：
   - 将 `KnowledgeFileActionsComponent.vue` 重命名为
     `KnowledgeToolsComponent.vue`；
   - 新建 `KnowledgeToolListComponent.vue` 与
     `KnowledgeToolRunStatusComponent.vue`；
   - 删除 `KnowledgeToolComponent.vue`，由 Tool List 直接循环渲染工具按钮；
   - 将原本空白的下半区改为当前工具运行状态区域。
5. 更新 `KnowledgeView.vue`，使其只引入三个根组件，并移除固定传入的 Drawer Props。
6. 删除 `web/src/types/knowledge.ts` 中不再使用的
   `KnowledgePanelPresentation`；若实现阶段需要共享的前端状态 View Model，只添加当前
   三栏实际消费的最小字段，不把它描述成后端合同。
7. 删除 `web/src/styles/index.css` 中只服务于 Knowledge Drawer 的样式。
8. 同步更新 `doc/spec/web/src/views/KnowledgeView.md` 和其他仍引用旧组件路径或旧组件名的
   当前设计文档，避免保留两套组件架构说明。

## 验证

- 运行 `npm run typecheck`、`npm run lint`、`npm run build` 和 `git diff --check`。
- 检查 Files 的上传文档、扩展名校验、搜索、空状态、文件状态、选择、打开、下载和删除
  确认。
- 检查 Chat 的消息滚动、知识库工具状态顺序、纯文本提交，以及没有通用附件入口。
- 检查 Tools 上下区域、工具激活后下半区切换到对应工具状态、完成与失败展示。
- 检查两侧收纳、快速反向切换、Reduced Motion 和 `720px` 以下纵向布局。
- 本轮未确认后端执行合同，因此不以模拟状态证明 API、SSE 或真实工具执行已经打通。
