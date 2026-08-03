# Knowledge 页面设计

## 页面定位

Knowledge 是独立的知识库工作台，不是 Library 的一个右侧子页面。它进入后占据完整应用
视口，离开时返回普通应用页面。

路由规划：

```text
/knowledge -> KnowledgeView.vue
```

`/knowledge` 不放在 `NavigationView` 的 children 下，不使用当前 Library 的
`featureId` 分支。`KnowledgeView.vue` 自己负责页面级布局和区域编排，具体功能下沉到
有明确职责的 Component 和 Composable。

## 页面结构

下面按横向四列 `1:2:5:2` 设计：

```text
┌────── 1 ──────┬──────────── 2 ────────────┬──────────────────── 5 ────────────────────┬──────────── 2 ────────────┐
│ Icons         │ Files                      │ Knowledge Chat                             │ Tools                       │
│ hover expand  │ 添加、检索、文件列表          │ 根据知识库内容进行对话                        │ Road Map / PPT / Slides    │
│               │                             │                                            │                            │
│ 常用按钮       │ 圆角容器                    │ 圆角容器                                   │ 圆角容器                   │
└───────────────┴─────────────────────────────┴────────────────────────────────────────────┴────────────────────────────┘
```

第一列是固定窄度的图标栏，不单独做圆角卡片；悬停或键盘聚焦时向右覆盖展开，不改变后三列
尺寸。后三列都是独立圆角容器，并共享同一条顶部基线。

四个比例区域本身都必须以组件实现。比例只决定页面编排，不允许把某个区域和其它区域的
交互逻辑写进 `KnowledgeView.vue`。

## 四个区域

### 1. Knowledge utility rail

默认只纵向显示返回、文件、对话和工具图标，不放纵向文字。悬停或键盘聚焦时，工具栏向右
展开并横向显示图标名称；展开层覆盖在页面上，不推动 Files、Chat 和 Tools 容器重新排版。

### 2. Files：上传与解析

左侧圆角容器是知识文件入口：

- Header 只显示 `Files`；文件添加由 `KnowledgeFileAddComponent` 提供；
- 文件检索先作为 `KnowledgeFilesComponent` 内部的一个功能区域；只有出现独立的查询状态、
  防抖、远程检索或复用需求时，才抽出 `KnowledgeFileSearchComponent`；
- `KnowledgeFileListComponent` 负责列表滚动、空状态和选中项；
- 每一行由 `KnowledgeFileListItemComponent` 承载，只显示文件图标、名称、选中状态和三点菜单；
- 每一行的删除操作通过 `KnowledgeFileActionsMenuComponent` 的“三点”菜单触发，并在菜单组件内完成确认；
- 解析动作可以作用于当前文件，也可以由独立的解析操作组件提供批量入口。

文件列表是这个区域的主内容，上传区域保持紧凑，不能挤压列表的可滚动空间。

### 3. Chat：根据知识库对话

中间圆角容器是页面的主工作区，比例最大：

- Header 保留在 `KnowledgeChatComponent` 内，只显示 `Knowledge Chat`；
- 当前消息区域只有空状态，因此保留在 `KnowledgeChatComponent` 内；接入真实消息、引用和独立滚动状态后再拆出消息组件；
- Composer 由 `KnowledgeComposerComponent` 提供并固定在容器底部，消息区域独立滚动；
- 引用显示文件名和定位信息，避免把检索证据和普通消息混在一起。

没有文件时，空状态应该引导用户先上传文件；没有选中文件时，不阻断知识库级对话。

### 4. Tools：内容生成工具

右侧圆角容器承载知识内容的生成入口：

- Header 只显示 `Tools`；
- Body 先提供 `Road Map`、`PPT` 和 `Slides` 三个样例功能；
- 每个功能只显示图标和名称，不附加说明性小字；
- 这些功能由 `KnowledgeFileActionsComponent` 统一承载，不为每个按钮建立单独组件。

右侧不承担文件列表、知识库切换或全局设置。

## Header 对齐规则

后三个容器必须使用一致的结构：

```text
knowledge-workbench-grid
  ├── knowledge-files-panel
  │     ├── panel-header
  │     └── panel-body
  ├── knowledge-chat-panel
  │     ├── panel-header
  │     └── panel-body
  └── knowledge-file-actions-panel
        ├── panel-header
        └── panel-body
```

- 三个容器使用同一个 `grid-template-rows: auto minmax(0, 1fr)`；
- Header 高度、上下内边距和底部边界一致；
- 不在单个容器上额外增加顶部 margin，保证标题、分割线处于同一水平线；
- Body 各自滚动，页面本身不因单个文件列表或消息增长而整体滚动；
- 圆角、边框和背景使用现有 `tokens.css` 的语义变量，不新增页面专属颜色体系。

## 组件和文件角色

```text
src/views/KnowledgeView.vue
  ├── KnowledgeNavigationComponent.vue                 # 比例 1
  ├── KnowledgeFilesComponent.vue                      # 比例 2
  │     ├── KnowledgeFileAddComponent.vue
  │     ├── KnowledgeFileListComponent.vue
  │     │     └── KnowledgeFileListItemComponent.vue
  │     │           └── KnowledgeFileActionsMenuComponent.vue
  ├── KnowledgeChatComponent.vue                       # 比例 5
  │     └── KnowledgeComposerComponent.vue
  └── KnowledgeFileActionsComponent.vue                 # 比例 2
```

- `KnowledgeView.vue`：持有本地文件集合、`selectedFileId` 和页面级布局状态，并负责四列区域的组合；不直接绑定 Ant Design 交互控件。
- `KnowledgeNavigationComponent.vue`：负责默认图标栏以及悬停、聚焦时的覆盖展开。
- `KnowledgeFilesComponent.vue`：负责比例 2 的容器编排、文件检索区域和文件列表状态；上传流程由 `KnowledgeFileAddComponent` 负责。
- `KnowledgeChatComponent.vue`：负责比例 5 的容器编排和当前空状态；具有独立输入状态的 Composer 单独实现。
- `KnowledgeFileActionsComponent.vue`：统一承载右侧 Road Map、PPT 和 Slides 等生成工具；不继续拆分单个工具按钮。
- `KnowledgeFileActionsMenuComponent.vue`：负责文件行的三点菜单和菜单事件；菜单中的删除、解析、索引等选项不逐个拆成组件。
- `src/types/knowledge.ts`：定义文件状态和页面组件共享的 TypeScript 合同。当前页面状态只由
  `KnowledgeView.vue` 使用，因此不提前建立一次性的 Composable；组件之间通过 props/emits
  交换数据，不使用事件总线。

这些组件按功能命名，不抽象出通用的 `Panel`、`Container` 或 `Layout` 组件。

## Component First 原则

Knowledge 页面采用有规律的 Component First：

1. 每个比例容器是组件；容器内部具有独立职责的区域也是组件。
2. 只有具有独立状态、交互、生命周期或复用价值的功能才拆成组件。
3. 静态标题、简单布局包装和单个菜单项不因为视觉上独立就拆组件。
4. 所有交互触发都从所属功能组件发出，由该组件负责自己的 props、emits、加载状态、错误状态和确认流程；父组件只负责组合和传递上下文。
5. `KnowledgeView.vue` 不直接写文件删除、上传、查询、对话发送或右侧操作的按钮逻辑，也不直接绑定 Ant Design 交互控件。
6. Ant Design Vue 组件只能在对应的功能组件内部使用。例如 `Dropdown` 放在
   `KnowledgeFileActionsMenuComponent`，`Upload.Dragger` 放在 `KnowledgeFileAddComponent`，
   `Drawer` 放在需要响应式收起的区域组件中。
7. 三点菜单是一个完整的文件操作组件；删除、解析、索引等菜单项通过事件或动作标识交给
   文件状态协调层，不单独建立一组同构的小组件。

新增功能时，先判断它属于哪个功能组件，再判断是否满足独立状态、交互、生命周期或复用
条件；不得为了省文件把多个功能塞进错误的父组件，也不得为了形式把没有独立职责的静态
包装层拆成组件。

## Ant Design Vue 使用边界

Knowledge 页面允许使用 `ant-design-vue`。当前依赖已经加入
`web/package.json`，版本为 `^4.2.6`。

Ant Design Vue 负责成熟的交互控件，不负责这张页面的主布局：

- 上传使用 `Upload` / `Upload.Dragger`；
- 操作按钮、Tooltip、Dropdown 和确认操作使用 `Button`、`Tooltip`、`Dropdown`、`Modal`；
- 文件列表和空状态使用 `List`、`Empty`；
- 中小屏的 Files、Tools 抽屉使用 `Drawer`；
- 页面根部和三列圆角容器继续使用自定义 CSS Grid，不使用 Ant Design `Layout` 或 `Card`
  替代 1:2:5:2 结构，避免 Header 高度和内边距不一致；
- 组件颜色和交互状态通过现有语义 Token 或 `ConfigProvider` 统一配置，不在单个组件中
  写新的颜色体系。

组件库只提供控件行为，Knowledge 页面的工作台比例、Header 基线、滚动边界和视觉层级仍由
`KnowledgeView.vue` 及其功能组件负责。

## 响应式规则

- 宽屏使用窄图标栏和 `2fr 5fr 2fr` 三个内容区，中间对话区是最稳定的主列；
- 中等宽度保留工具栏和对话区，Files、Tools 变为可展开的侧边抽屉；
- 小屏将第一列变成顶部工具栏，文件列表和文件操作改为底部抽屉，对话区保持主视图；
- 抽屉打开时保留当前选中文件和滚动位置，关闭后不丢失上下文；
- 所有按钮、文件行和抽屉入口都需要可见的键盘焦点状态，并尊重减少动画设置。

## 视觉方向

页面整体采用“知识工作台”而不是普通后台 Dashboard 的语言：白色纸面、浅灰工作区、
细边界和稳定的圆角容器，使用现有黑白灰 tokens 保持与对话页一致。页面的识别性来自三
个容器共享的 Header 基线，以及第一列连续的知识库工具栏；不额外添加装饰性渐变、数字
徽章、说明性小字或无功能的统计卡片。
