# AGENTS.md

## 文档职责

`web/AGENTS.md` 只描述长期有效的架构职责、目录边界、依赖方向、代码归属和验证方式。

- 不把一次任务的实现方案写成永久架构；任务方案放在仓库根目录的 `doc/spec/`。
- 不把运行时数据、测试结果、部署状态或排障结论写入本文件。
- 只有目录所有权、公共契约或工作流程发生变化时，才同步更新本文件。
- 代码与本文件不一致时，先核对真实调用链；如果代码变更确实改变了长期边界，在同一任务中修正文档。

## 核心工程规则

- Do not preserve backward compatibility. Remove obsolete paths instead of adding compatibility layers, fallbacks, or migrations.
- Choose the simplest implementation that fully meets the current requirements. Avoid speculative abstractions, configuration, and indirection.
- Grow the system in layers. Start from the smallest version that works end to end, and add each new capability on top of a product that already works. Never trade a working product for unfinished complexity.
- Keep components modular and concerns clearly separated.
- Prefer established, well-maintained libraries when they reduce overall complexity or improve reliability. Do not reimplement common functionality without a clear reason.
- Lean on the dependencies already in the project before writing your own implementation or adding packages. Do not assume a library lacks a capability without checking its documentation and types.
- Make architectural decisions for the long term. Do not accept a stopgap that only works for now and is meant to be replaced later.
- 前端数据合同以后端公开协议为准，前端样式优先使用 Tailwind CSS v4；具体字段映射和组件
  样式写入对应 `doc/spec/`，不在本文件展开。

补充执行原则：

- 删除旧入口、旧组件、旧类型和旧样式，不保留兼容文件、别名、转发层或双路径。
- 不为“以后可能需要”创建空目录、空组件、通用工厂、配置开关或接口层。
- 一个直接实现能够清楚完成任务时，不增加包装组件、聚合对象或额外状态层。
- 依赖已经安装不等于必须使用；只有真实需求需要时才接入。
- 重构不得用未完成的新链路替换仍可工作的完整链路。

## 技术与应用入口

前端使用 Vue 3、TypeScript、Vite、Vue Router、Tailwind CSS、Ant Design Vue、Lucide 和 GSAP。依赖与脚本以 `package.json` 和锁文件为准，不在本文件维护版本快照。

标准启动链为：

```text
src/main.ts
  -> src/App.vue
  -> src/router/index.ts
  -> src/views/*View.vue
  -> src/components/**/*Component.vue
```

职责按以下顺序判断：

1. Router 直接挂载的页面使用 View，负责路由参数、页面状态和功能组合。
2. 有模板且能描述为独立界面功能的部分使用 Component，通过 props 和 emits 通信。
3. 无模板且需要复用的响应式状态与行为使用 Composable。
4. 多个路由或无共同所有者的功能需要共享同一份客户端状态时使用 Store。

状态默认留在最近的使用者；同一组件树共享时提升到最近的共同所有者，跨树共享时才进入 Store。

约束如下：

- `main.ts` 只负责创建应用、安装应用级插件并挂载根节点。
- `App.vue` 只保留应用根出口，不承接页面业务。
- Router 只定义 URL、路由名、参数、页面组件、元数据和重定向。
- API adapter 只负责传输和协议转换，不持有界面状态。
- `types/`、`styles/` 和 `assets/` 是叶子边界，不反向协调业务。
- 从 `src/` 导入时使用 `@/` 别名；同一功能目录内部可使用相对导入。

## 目录职责

| 路径 | 唯一职责 | 禁止放入 |
| --- | --- | --- |
| `public/` | 以原始 URL 直接提供、不经过 Vite import graph 的静态文件 | Vue 组件、业务数据、需要 TypeScript 引用的资源 |
| `src/api/` | 按后端领域组织 HTTP、上传、下载、SSE 和协议错误转换 | 页面状态、DOM、组件提示、路由跳转 |
| `src/assets/` | 由 Vue/TypeScript/CSS 显式导入并参与构建的字体、Logo 和图片 | 业务逻辑、运行时状态、远端数据 |
| `src/components/` | Chat、导航覆盖层等可命名的界面功能 | 路由定义、全局持久化、直接业务 API 编排 |
| `src/components/knowledge/` | Knowledge 页面内部的文件区、聊天区、工具区及其子组件 | Chat、认证、导航或其他页面逻辑 |
| `src/composables/` | 可复用的 Vue 响应式状态、watcher、持久化和无模板行为 | HTML、CSS、图标、页面布局 |
| `src/router/` | 路由表、路由参数绑定、元数据、滚动行为和兜底跳转 | 页面实现、请求逻辑、领域状态 |
| `src/stores/` | 跨路由或跨功能共享的 Pinia 状态和修改动作 | DOM、路由定义、组件局部状态 |
| `src/types/` | 跨文件共享的 TypeScript 数据契约和联合类型 | 请求执行、状态修改、格式化函数 |
| `src/views/` | 与路由一一对应的页面入口和页面级编排 | 可跨页面复用的通用组件、底层传输实现 |
| `src/main.ts` | Vue 应用启动 | 页面或领域逻辑 |
| `src/App.vue` | 根级 RouterView | 导航、业务布局或页面状态 |

## 任务归属规则

每个代码任务都必须遵循以下顺序：

1. 根据用户目标确定一个主要任务区域。
2. 按根 `AGENTS.md` 要求，在 `doc/spec/` 写明行为、边界、文件计划和验证方式，并等待确认。
3. 只修改该任务区域以及完成调用链所必需的直接边界。
4. 新代码放入现有责任所有者；没有真实复用时，不提升到公共目录。
5. 修改完成后删除旧路径和残留引用，并验证完整执行链。

具体约束：

- 一个帮助函数只服务一个 View 或 Component 时，留在该文件或同一功能目录。
- 两个文件出现相似代码并不自动构成共享抽象；只有语义和变化原因一致时才复用。
- 禁止为单一功能创建 `common/`、`shared/`、`helpers/`、`services/`、`core/` 或 `ui/` 兜底目录。
- 不创建只有一个实现的接口、工厂、注册表或 Provider。
- 不创建仅转发 props、emits 或 slot 的包装组件。
- 结构移动和职责变更必须作为专门的结构任务处理，不夹带在普通功能修改中。
- 如果任务跨越两个区域，明确一个协调所有者；不要让两个区域互相读取内部状态。

## 依赖方向

允许的主要依赖方向：

```text
main/App -> router -> views -> components
views/components -> composables/stores -> api
views/components -> types
components -> 功能内 components
styles/assets <- views/components
```

禁止的反向依赖：

- Component 不导入 View。
- Router 不导入 Component、Composable、Store 或 API adapter。
- API adapter 不导入 View、Component、Router 或界面状态。
- Type 文件不导入运行时代码。
- Style 和 Asset 文件不协调业务行为。
- 一个功能目录不直接修改另一个功能目录的内部状态。

跨层用例由 View、Composable 或 Store action 协调。传输层返回数据或抛出协议错误；界面层决定加载、失败、空状态和用户反馈如何呈现。

## 路由与 View 契约

| URL | 路由名 | View | 布局所有者 |
| --- | --- | --- | --- |
| `/` | `chat` | `ChatView.vue` | `NavigationView.vue` |
| `/c/:threadId` | `conversation` | `ChatView.vue` | `NavigationView.vue` |
| `/library` | `library` | `LibraryView.vue` | `NavigationView.vue` |
| `/agent` | `agent` | `AgentView.vue` | `NavigationView.vue` |
| `/static` | `static` | `StaticView.vue` | `NavigationView.vue` |
| `/sandbox` | `sandbox` | `SandboxView.vue` | `NavigationView.vue` |
| `/knowledge` | `knowledge` | `KnowledgeView.vue` | `KnowledgeView.vue` |
| `/login` | `login` | `AuthenticationView.vue` | `AuthenticationView.vue` |

- View 文件使用 PascalCase，并以 `View.vue` 结尾。
- 每个功能 URL 直接绑定职责同名的 View，不使用通用 unavailable/fallback View 伪装多个页面。
- 路由参数在 Router 或 View 边界解析，不下沉到纯展示组件。
- 未匹配 URL 的统一兜底由 Router 维护；它不是旧路由兼容机制。

## Component 契约与命名

- Component 文件使用 PascalCase，并以 `Component.vue` 结尾。
- 文件名必须描述真实功能，例如 `AttachmentComponent.vue`、`MessageInputComponent.vue`、`KnowledgeFileListComponent.vue`。
- 不用生命周期或临时阶段命名同一个领域对象的组件，例如 `PendingAttachmentComponent.vue`。
- 只有真实存在不同交互、数据契约或生命周期所有权时，才允许拆分不同组件。
- 使用类型化的 `defineProps` 和 `defineEmits`；不得修改 props。
- 兄弟组件通过最近的共同所有者通信，不使用全局事件总线。
- 不显式设置 Vue 组件名；文件名就是组件名。
- 不因为模板长、有边框或有独立 CSS 就拆组件。一个职责完整的长组件优于多层事件转发。
- Header、Footer、Item、Actions、Toolbar 等名称只有在它们代表真实独立功能时才可成为组件。

## 状态、持久化与传输

- Store 负责共享客户端状态和修改动作；它不是浏览器存储 API，也不是后端数据源。
- Pinia Store 统一命名为 `use<Feature>Store`，例如 `useChatStore`。
- 只把耐久、可序列化、由用户产生且允许留在浏览器的数据写入浏览器存储。
- File、AbortController、临时错误、弹窗开关、请求中状态和流式缓冲不得写入浏览器存储。
- 文件被浏览器选择不等于已经上传；界面文案和状态必须与真实传输阶段一致。
- HTTP、上传、下载、认证和流式事件归 `src/api/`；视觉组件不得直接执行这些协议。
- 需要认证头的 SSE 使用支持请求头和取消控制的流式 `fetch`，不使用无法满足契约的裸 `EventSource`。
- 不创建假用户、假会话、假 Agent 输出、假上传、假工具调用或定时模拟流。

## 样式、依赖与可访问性

- 使用 `<script setup lang="ts">` 和 Composition API。
- 使用 2 空格缩进，保持 TypeScript 严格类型。
- imports 按外部依赖、`@/` 路径、相对路径分组。
- Vue 样式默认直接写成模板内联 Tailwind utility；组件默认不写 `<style scoped>` 和 `@apply`。
- `class` 写固定、交互和响应式样式，`:class` 写 Vue 状态样式；工具类必须完整写出，不动态拼接类名。
- 重复的完整界面提取 Component，不为复用样式创建语义 CSS 类。
- `src/styles/index.css` 只保留 Tailwind 入口、主题、全局基础规则和第三方组件覆盖；运行时数值使用 `:style`，不引入 Less 或 Sass。
- 常用控件优先检查 Ant Design Vue；常用图标使用 Lucide，不增加第二套图标库。
- 简单过渡使用 Tailwind/CSS；只有协调动画和时间线才使用 GSAP，并在卸载时清理且尊重 `prefers-reduced-motion`。
- Markdown 使用项目已有依赖能力，不自行实现 Markdown 解析器，也不对不可信内容使用 `v-html`。
- 保留语义 HTML、键盘操作、清晰焦点、ARIA 标签和移动端可用性；最小实现不能删掉可访问性要求。

## 变更与验证

代码变更前：

- 先读取真实定义、调用点和类型，不依据文件名猜职责。
- 列出主要任务区域和具体文件边界。
- 需要代码、API、数据模型、架构或交互设计时，先按根规则提交 `doc/spec/` 并等待确认。
- 工作区存在其他改动时，保留用户改动，不顺手格式化或重构无关文件。

代码变更后，从 `web/` 运行：

```bash
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

从仓库根目录运行：

```bash
git diff --check -- web
```

另外必须：

- 使用 `rg` 检查旧文件名、旧路由名、旧选择器和旧导入是否残留。
- 路由或交互变化需要验证对应 URL、桌面与移动布局、键盘操作和焦点恢复。
- 只报告实际执行过的验证；静态检查不能写成运行时已验证。
- 构建警告与构建失败分开报告，不把成功退出但带警告描述为失败。

## 安全与提交

- 不把密钥、令牌、真实用户数据或服务端私有配置放进前端仓库。
- 只有可公开给浏览器的配置才能使用 `VITE_*` 暴露。
- 外部输入、文件元数据和 API 响应必须在信任边界验证。
- 遵循根 `AGENTS.md` 的 Conventional Commit 规则：英文小写 type/scope，中文 subject，不使用 `@` 包裹提交信息。
