# Web 开发约定

本目录是 `agent-stack` 的 React + TypeScript + Vite 前端。开发前先阅读根 [AGENTS.md](../AGENTS.md)、[ARCHITECTURE.md](../ARCHITECTURE.md) 与 [设计规范](../docs/develop-guides/design.md)。

## 边界与规范

- 代码按所有权放置：`api/` 负责 HTTP/SSE 请求与协议类型；`pages/<feature>/` 放页面专用组件、Hooks 与类型；`layouts/` 放布局专用组件；跨页面复用的产品组件放入 `components/common/`；`context/` 放跨页面状态。
- 复用 `web/src/components/ui/` 的 shadcn/ui（Base UI）组件与 `web/src/styles/index.css` 语义主题 token；不把页面请求或领域逻辑放入 `components/ui/`。
- 不在页面中硬编码品牌色值，也不用 `dark:` 重复维护两套颜色；界面产品名统一为 `AM`（`Agent Multiverse`）。
- 权限校验由后端最终执行，前端路由与菜单可见性仅提供界面体验约束。

## 验证命令

修改前端代码后，在 `web/` 运行：

```bash
cd web
npm run typecheck
npm run lint
npm test
npm run build
```

路由或交互变化时同步验证对应页面行为，只报告实际执行过的检查结果。
