# Web 前端设计与开发规范

本文档是 `web/` 的前端规范入口，适用于页面、布局、组件、Hooks、样式和交互变更。产品能力的
具体行为仍由 [`docs/spec/product/`](../spec/product/README.md) 下对应的 capability 规定；本文件
只定义跨页面通用的工程与设计规则。

## 1. 技术与权威来源

- 应用使用 React、TypeScript、Vite、React Router 和 React Context。
- 界面使用 Tailwind CSS v4、shadcn/ui（Base UI）和 Lucide 图标。
- 依赖和脚本以 [`web/package.json`](../../web/package.json) 与锁文件为准。
- shadcn/ui 的生成方式和路径别名以 [`web/components.json`](../../web/components.json) 为准。
- 主题变量和全局样式以 [`web/src/styles/index.css`](../../web/src/styles/index.css) 为准。
- 共享组件的变体和状态以 `web/src/components/ui/` 内对应组件实现为准。
- 视觉基准由本文档定义，通过现有 React/shadcn 组件承载。

文档与实现不一致时，先确认当前产品要求，再同步修正文档和实际拥有该规则的源码，不在页面中
增加临时覆盖来绕过共享规则。

## 2. 目录与职责

```text
web/
├── public/                  直接提供的静态文件
├── src/
│   ├── api/                 后端请求、响应类型与协议处理
│   ├── app/                 应用根组件、路由和登录校验
│   ├── assets/              图片、标志和字体
│   ├── components/
│   │   ├── ui/              shadcn/ui 基础组件与共享变体
│   │   └── common/          跨页面复用的产品组件
│   ├── context/             跨页面共享状态
│   ├── layouts/             布局及其专用组件
│   ├── lib/                 无页面归属的通用工具
│   ├── pages/<feature>/     路由页面及其专用组件、Hooks 和类型
│   ├── styles/index.css     主题变量和全局样式
│   ├── types/               跨模块共享类型
│   └── main.tsx             应用入口
├── components.json          shadcn/ui 配置
└── package.json             依赖和脚本
```

代码按所有权放置：

- 页面专用组件、Hooks 和类型放在 `pages/<feature>/` 下。
- 布局专用组件放在对应的 `layouts/<Layout>/` 下。
- 只有被多个页面使用的产品组件才放入 `components/common/`。
- shadcn/ui 基础组件和共享视觉变体放入 `components/ui/`，业务逻辑不得放在这里。
- 跨页面状态放入 `context/`；请求、响应类型和网络调用放入 `api/`。
- 从用户目标定位真实页面后，按需追踪 `app/App.tsx → app/routes.tsx → pages/layouts → 组件与
  Hooks → api`；涉及接口时同时核对后端协议。

## 3. 命名

以下规则用于新增文件以及任务范围内发生的重命名，不要求为统一命名而批量改动无关旧文件。

| 对象 | 规则 | 示例 |
| --- | --- | --- |
| React 页面 | PascalCase，使用 `Page` 后缀 | `SandboxPage.tsx` |
| React 业务组件 | PascalCase，文件名与导出组件同名 | `WorkspaceFileList.tsx` |
| 布局 | PascalCase，使用 `Layout` 后缀 | `MainLayout/MainLayout.tsx` |
| Hook | `use` 开头的 camelCase | `useAgentRun.ts` |
| 页面目录 | 小写功能名；多个单词使用 kebab-case | `pages/model-settings/` |
| 普通模块 | 小写；多个单词使用 kebab-case | `file-format.ts` |
| shadcn/ui 文件 | 保留生成器的小写 kebab-case 命名 | `dropdown-menu.tsx` |
| 测试 | 与被测文件同目录，使用 `.test.ts` 或 `.test.tsx` | `SandboxPage.test.tsx` |
| 类型 | PascalCase，不添加 `I` 前缀 | `WorkspaceEntry` |
| 事件属性 | 对外回调用 `onXxx`，组件内部处理函数用 `handleXxx` | `onDelete`、`handleDelete` |
| 布尔值 | 使用 `is`、`has`、`can`、`should` 等可判断前缀 | `isOpen`、`canEdit` |

内部导入优先使用 `@/` 别名。相邻、紧密绑定的文件可以使用相对路径。文件只默认导出框架明确要求的
单一入口；普通组件和工具使用具名导出。

## 4. 组件选择

- 优先组合现有 shadcn/ui 组件；缺少基础组件时先按当前 `components.json` 配置引入 shadcn/ui，
  再考虑自行实现。
- 业务页面不重复实现 Button、Input、Dialog、Sheet、DropdownMenu、Select、Tabs、Table 等通用
  交互原语。`web/eslint.config.js` 中的限制是最低强制边界。
- 图标使用 Lucide；同一操作在不同页面使用同一图标和语义。
- 页面组件负责数据与业务状态，基础组件负责视觉变体和通用交互状态。不要把页面请求或领域逻辑
  放入 `components/ui/`。
- 新增依赖前先检查现有依赖和组件能否完整满足需求。

## 5. 布局与视觉

- 界面与视觉设计遵循本地 `frontend-design` skill，结合本项目桌面端定位与设计系统基准执行。
- 前端设计时只需要适配桌面浏览器。
- 页面采用扁平布局。使用背景层级、留白和排版表达结构，分割线、描边和阴影只用于明确边界，
  不作为装饰重复叠加。
- App 主布局使用直角的左右区域，不使用包裹主内容的椭圆容器。
- 不添加重复解释标题、卡片或表单用途的微文案；必要的状态、错误和操作反馈放在对应容器内。
- 页面级 Tailwind class 负责布局、尺寸和局部排列；颜色、交互状态和通用控件外观由语义 token 或
  `components/ui/` 的 variant 负责。
- 不在页面中硬编码品牌色，也不使用 `dark:` 重复维护一套页面颜色。确需新增全局视觉语义时，
  同时定义浅色、深色变量，并通过 `@theme inline` 暴露为 Tailwind token。

## 6. 品牌与资源

- 产品名称、Logo 语义和品牌展示位置以
  [`docs/spec/product/branding/spec.md`](../spec/product/branding/spec.md) 为准。
- `web/src/assets/logo.svg` 是前端 Logo 的唯一源文件；favicon、导航和认证页面复用该资源，不创建
  页面专用副本。
- 静态图片、标志和字体放在 `web/src/assets/`；只有无需构建处理、需要按原路径直接提供的资源才放
  在 `web/public/`。

## 7. 颜色、间距与主题 token

`index.css` 中的 `:root` 定义浅色主题，`.dark` 定义深色主题，`@theme inline` 将 CSS 变量映射为
Tailwind 颜色。页面使用语义类名，不依赖具体色值。

主色为 `#046a82`，hover 为 `#24839a`，active 为 `#035065`；白色画布搭配
`#1e1f1f` 正文和 `#697070` 次要文字，边框使用 `#eef0f0` / `#e4e6e6`。
浅色、深色的 `--main-*` 与 `--gray-*` 只在主题层定义，组件继续消费现有语义 token。
状态背景与边框使用 `success-muted` / `success-border`、`warning-muted` / `warning-border`、
`destructive-muted` / `destructive-border`，不自行混合浅色背景。

间距以 4px / 8px 为基础：图标与文字间隔 6px / 8px，表单字段内部 6px，字段组之间 16px，
卡片内边距 16px、内部间隔 10px，弹窗内容内边距 24px，主要区块间隔 24px / 32px。
管理页面复用 `--page-padding`（18px）；默认按钮与输入框高 32px，大按钮高 40px。
普通按钮、输入框、选择器和卡片圆角为 8px；小控件为 4px / 6px，弹窗为 12px。
聊天输入区圆角为 22.4px，发送按钮为 32px 圆形。

实际组件尺寸优先于通用间距建议：

| 对应来源 | 尺寸与布局 |
| --- | --- |
| `AppLayout.vue` | 主侧栏 230px，收起 52px；品牌行 32px、顶部 6px；导航行 32px、横向内边距 6px、行距 2px |
| `ConversationNavItem.vue` | 会话行 32px、文字 13px、横向内边距 8px |
| `PageHeader.vue` | 管理页标题栏 48px、横向 18px、标题 16px / 600 |
| `SettingsModal.vue` | 宽 90%、最大 980px、顶部 5vh、高 min(84vh,840px)；侧栏 176px、内边距 52px 10px 12px；内容内边距 16px |
| `AgentChatComponent.vue` | 消息区与输入区最大 800px；消息区内边距 16px 32px；欢迎区位于 45% 高度 |
| `MessageInputComponent.vue` | 固定文本行和工具行；内边距 12.8px 12px 9.6px；文本区 44–200px、15px / 1.5 |
| `ActionTrigger.vue` | 聊天工具按钮 30px、文字 13px、圆角 8px；模型触发器最大 168px |
| `AgentMessageComponent.vue` | 用户气泡最大 95%、圆角 8px、内边距 8px 16px、文字 14px / 24px |
| `InfoCard.vue` | 卡片内边距 16px、间隔 10px、图标 32px、标题 14px / 600、描述 13px / 1.4 |
| `LoginView.vue` | 登录卡片 900px、最小高 560px、圆角 16px；图片/表单比例 1.4:1；表单内边距 40px、输入与提交按钮高 44px |

工作区采用 `WorkspaceView.vue` 的 168px 侧栏与 `WorkspaceSidebar.vue` 的 32px 导航行。

全局正文为 15px / 1.6，常规控件与列表使用 14px，辅助文字与标签使用 12px，标题使用
18px / 20px / 24px 和 600 字重。字体使用系统字体栈，不使用负字距。
主题通过 `next-themes` 写入根节点 `.dark`，由 Settings 切换浅色、深色和系统主题，选择保存在 `am-theme`。

| 用途 | 背景 | 文本和图标 |
| --- | --- | --- |
| 页面画布 | `bg-background` | `text-foreground` |
| 卡片 | `bg-card` | `text-card-foreground` |
| 浮层 | `bg-popover` | `text-popover-foreground` |
| 主操作 | `bg-primary` | `text-primary-foreground` |
| 次操作 | `bg-secondary` | `text-secondary-foreground` |
| 悬停或展开 | `bg-accent` | `text-accent-foreground` |
| 次要内容 | `bg-muted` | `text-muted-foreground` |
| 当前选择 | `bg-selection` | `text-selection-foreground` |
| 危险操作 | `bg-destructive/10` | `text-destructive` |

`foreground` 表示某个 surface 上承载的内容颜色。`text-foreground` 将它用于文字颜色，
`bg-foreground` 才会将同一个 token 用作背景。surface 与对应的 `*-foreground` 应成对使用，
不要假定按钮文字始终为白色。

主按钮的默认、悬停和按下状态分别使用 `primary`、`primary-hover`、`primary-active`。普通控件悬停
使用 `accent`，当前选中项使用 `selection`，两者不混用。侧栏的悬停和选中状态分别使用
`sidebar-accent` 与 `sidebar-primary`。未选中项悬停时使用中性灰背景；选中项使用
`--gray-150` 背景与 `--main-700` 文字，悬停时保留选中配色。
输入框聚焦时使用主色边框和轻量 focus ring，键盘焦点始终可见；Dialog 和 Sheet 的遮罩使用 `overlay`。
普通管理卡片不使用阴影。聊天输入区、新建会话入口和登录容器使用轻量阴影。

按钮外观通过共享 `Button` variant 选择：

```tsx
<Button>保存</Button>
<Button variant="outline">取消</Button>
<Button variant="secondary">预览</Button>
<Button variant="ghost">更多</Button>
<Button variant="destructive">删除</Button>
```

页面可以调整按钮的布局和尺寸，但不得重新定义 variant 的颜色状态；需要改变所有同类按钮时，修改
`web/src/components/ui/button.tsx`。

## 8. 交互与可访问性

- 图标按钮必须有可访问名称，通常使用 `aria-label`；Tooltip 只补充提示，不代替可访问名称。
- 共享组件提供可见的键盘焦点；菜单高亮、选中态和禁用态按各自状态样式呈现。
- 加载、空状态、错误和禁用状态应在原位置呈现，避免因状态切换造成主要布局跳动。
- 动画只用于表达状态变化，并遵守 `prefers-reduced-motion`。
- 共享控件的 hover 使用 `--hover-transition-duration`（150ms）和 `ease-in-out`，仅改变背景、文字或
  描边，不位移或缩放。减少动态效果时 hover 过渡时长为 0ms。
- 删除、覆盖等不可逆操作使用明确的危险样式，并按产品能力要求提供确认流程。

## 9. 修改与验证

- 优先使用已有依赖、组件和状态；新增抽象必须服务于当前任务。
- 保留任务范围外的现有改动。改变架构边界、公开契约或文件所有权时遵循仓库级工作规则。
- 修改前端代码后，在 `web/` 运行 `npm run typecheck`、`npm run lint`、`npm test` 和
  `npm run build`；路由或交互变化还要验证对应页面。
- 只报告实际执行的检查，并区分静态检查、浏览器验证和服务运行结果。
- 仅修改文档时，至少执行 `git diff --check` 检查格式。
