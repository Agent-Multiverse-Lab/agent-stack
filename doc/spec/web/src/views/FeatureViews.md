# 独立功能页面拆分设计

## 目标行为

前端不再使用 `UnavailableFeatureView.vue` 承接多个导航入口。每个功能入口直接进入与自身同名、独立存在的 Vue 页面：

| 地址 | 路由名 | 页面组件 |
| --- | --- | --- |
| `/library` | `library` | `LibraryView.vue` |
| `/agent` | `agent` | `AgentView.vue` |
| `/static` | `static` | `StaticView.vue` |
| `/sandbox` | `sandbox` | `SandboxView.vue` |

现有 `/knowledge` 继续直接使用 `KnowledgeView.vue`，它已经是独立页面，不属于本次拆分和删除范围。

`UnavailableFeatureView.vue`、动态 `featureId` 路由参数以及通用 `feature` 路由名全部删除。各页面直接拥有自己的标题、图标、说明和后续业务接入边界，不再通过一份功能配置表切换页面内容。

本次只拆分前端页面与路由边界，不新增接口调用，也不改变现有后端 API。Library、Agent、Static 和 Sandbox 四个入口展示的页面内容分别迁入对应 View。Image 不建立独立页面，其导航入口、路由和功能标识直接删除。

## 边界与公开契约

- 浏览器公开地址保留 `/library`、`/agent`、`/static`、`/sandbox`；`/image` 不再是功能地址，并由现有兜底路由重定向到 `/`。
- 每个地址改为静态路由记录，并直接绑定对应的 `XXView.vue`。
- 侧边栏保留 Library、Knowledge、Agent、Static 和 Sandbox 入口；删除 Image 入口。点击目标由动态参数对象改为对应的路由名。
- 页面标题和侧边栏激活态直接依据当前路由名判断，不再读取 `route.params.featureId`。
- `FeatureId` 继续作为四个功能标识的 TypeScript 联合类型，用于约束导航配置；删除 `image` 成员，并且不再把该类型用于页面组件属性。
- 不修改后端、状态管理、接口协议和现有 Knowledge 页面。

## 文件级修改计划

### 新增

- `web/src/views/LibraryView.vue`：Library 页面边界。
- `web/src/views/AgentView.vue`：Agent 页面边界。
- `web/src/views/StaticView.vue`：Static 页面边界。
- `web/src/views/SandboxView.vue`：Sandbox 页面边界。

### 修改

- `web/src/router/index.ts`
  - 导入四个独立 View。
  - 用四条显式子路由替换 `:featureId(...)` 动态路由。
- `web/src/views/NavigationView.vue`
  - 删除 Image 导航项及图标导入。
  - 导航项直接使用自身 ID 作为路由名。
  - 页面标题和激活态改为按路由名匹配。
- `web/src/types/feature.ts`
  - 从 `FeatureId` 删除 `image`。

### 删除

- `web/src/views/UnavailableFeatureView.vue`：不再保留通用不可用页面。
- `web/src/views/ImageView.vue`：不创建或保留 Image 页面。

## 验证方式

1. 运行 `npm.cmd run typecheck`，确认路由名、导航类型和四个 View 的 TypeScript/Vue 类型正确。
2. 运行 `npm.cmd run build`，确认生产构建成功且不存在已删除组件的残留导入。
3. 使用 `rg` 确认仓库中不存在 `UnavailableFeatureView`、`name: "feature"` 或 `route.params.featureId` 残留。
4. 检查构建后的路由行为：四个保留 URL 分别渲染对应 View，侧边栏激活态和页面标题正确，侧边栏不存在 Image 入口。
