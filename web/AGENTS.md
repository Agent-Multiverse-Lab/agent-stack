# Web Agent Guide

`web/` 是 AM（Agent Multiverse）的 React 前端，负责调用后端 API、管理页面状态并展示结果。
本文件是前端任务入口；仓库通用规则与能力文档按 [根目录 AGENTS.md](../AGENTS.md) 的顺序读取。

## 技术栈

- 应用：React、TypeScript、Vite、React Router、React Context。
- 界面：Tailwind CSS v4、shadcn/ui（Base UI）、Lucide 图标、react-markdown。
- 传输：浏览器 `fetch`；开发环境由 Vite 将 `/api` 代理到 FastAPI。
- 工具：npm、TypeScript、ESLint。依赖及脚本以 `package.json` 和 `package-lock.json` 为准。

## 项目字符结构图

```text
web/
├── public/                  直接提供的静态文件
├── src/
│   ├── api/                 后端请求与协议处理
│   ├── app/                 应用根组件、路由与登录校验
│   ├── assets/              图片、标志与字体
│   ├── components/          跨页面复用组件；shadcn/ui 基础组件放 ui/
│   ├── context/             跨页面共享的认证与模型状态
│   ├── layouts/MainLayout/  主布局与侧栏专用组件
│   ├── lib/utils.ts         shadcn/ui 类名合并工具
│   ├── pages/
│   │   ├── auth/            登录页及其表单
│   │   ├── chat/            聊天页、专用组件与 Hooks
│   │   ├── knowledge/       知识页及其专用组件
│   │   ├── library/         资料库页、专用组件与演示数据
│   │   └── agent|static|sandbox/  其他路由页
│   ├── styles/index.css     全局样式与主题
│   ├── types/               共享类型
│   └── main.tsx             应用入口
├── components.json          shadcn/ui 组件生成配置
├── index.html               页面入口
├── package.json             依赖与脚本
├── package-lock.json        npm 锁文件
├── vite.config.ts           构建配置与开发代理
└── tsconfig.json            TypeScript 配置
```

## 任务规则

1. 从用户目标定位页面或功能，读取真实定义、调用点和类型；按需追踪 `app/App.tsx → app/routes.tsx → pages/layouts → 页面组件与 Hooks → api`，跨接口任务同时核对后端协议。
2. 页面专用组件和 Hooks 放在对应的 `pages/<页面>/` 下；布局专用组件放在对应的 `layouts/` 下；只有跨页面复用的组件才放 `src/components/`。跨页面状态放 `context/`，网络请求放 `api/`。保留工作区内其他人的改动。
3. 优先使用已有依赖和实现；新增组件、状态或依赖要有当前任务的实际需要。架构边界或公开契约需要变更时，遵循根目录的工作规则。
4. 修改前端代码后，在 `web/` 执行 `npm run typecheck`、`npm run lint`、`npm test`、`npm run build`；路由或交互变化再验证对应页面。仅修改本文档时，检查 `git diff --check -- web/AGENTS.md`。
5. 只报告实际执行过的检查，并区分静态检查、浏览器验证和服务运行结果。
