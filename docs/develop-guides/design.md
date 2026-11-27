# Web 前端设计与开发规范

本文档是 `web/` 的前端设计基准，适用于页面、布局、组件、Hooks、样式与交互变更。具体接口协议、页面实现与样式变量值以真实源码为准。

## 1. 技术与权威来源

- 应用使用 React、TypeScript、Vite、React Router 和 React Context。
- 界面使用 Tailwind CSS v4、shadcn/ui（Base UI）和 Lucide 图标。
- 依赖与脚本以 [`web/package.json`](../../web/package.json) 和锁文件为准。
- shadcn/ui 生成方式与路径别名以 [`web/components.json`](../../web/components.json) 为准。
- 主题变量与全局样式以 [`web/src/styles/index.css`](../../web/src/styles/index.css) 为准。
- 共享组件的变体和状态以 `web/src/components/ui/` 内对应组件实现为准。

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

代码按所有权放置：页面专用组件、Hooks 和类型放在 `pages/<feature>/`；布局专用组件放在 `layouts/<Layout>/`；跨页面复用的产品组件放入 `components/common/`；`components/ui/` 仅承载基础视觉变体与通用交互原语，不放业务逻辑。

## 3. 命名

新增文件及任务范围内的重命名遵循以下约定（无需为统一命名批量修改无关旧文件）：

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

内部导入优先使用 `@/` 别名；普通组件与工具使用具名导出，仅框架明确要求的单一入口使用默认导出。

## 4. 组件选择与布局视觉

- 优先组合现有 `components/ui/` 中的 shadcn/ui 原语；缺失基础组件时先按 `components.json` 引入，再考虑自建。
- 操作图标使用 Lucide，同类操作跨页面保持一致语义；文件夹与文件类型图标复用 `assets/folder.svg` 与 `components/common/FileTypeIcon.tsx`。
- 页面面向桌面浏览器，采用扁平布局，依靠背景层级、留白与排版区分结构，不堆砌装饰性分割线或阴影。
- 页面级 Tailwind class 负责布局与尺寸，颜色与交互状态统一消费 `web/src/styles/index.css` 语义 token（如 `background`/`foreground`、`card`、`popover`、`primary`、`secondary`、`accent`、`muted`、`selection`、`destructive` 等，成对使用 surface 与 `*-foreground`），不硬编码品牌色值，不用 `dark:` 重复维护两套页面配色。
- 按钮外观通过共享 `Button` variant（默认、`outline`、`secondary`、`ghost`、`destructive`）选择，需要调整所有同类按钮外观时修改 `web/src/components/ui/button.tsx`。
- 活跃 Web 界面的产品名统一为 `AM`（全称 `Agent Multiverse`，品牌句 `A universe for agents.`）；`web/src/assets/logo.svg` 是前端 Logo 唯一源文件。

## 5. 交互、可访问性与验证

- 图标按钮必须提供可访问名称（如 `aria-label`），Tooltip 只作补充。
- 共享控件保留可见键盘焦点；加载、空状态、错误与禁用状态在原位呈现，避免主布局跳动；动效遵守 `prefers-reduced-motion`。
- 不可逆危险操作使用危险样式并按产品语义提供确认。
- 修改前端代码后，在 `web/` 运行 `npm run typecheck`、`npm run lint`、`npm test` 和 `npm run build`（详见 [web/AGENTS.md](../../web/AGENTS.md)）。
