# 文档约定

本目录承载用户教程、Agent 指南、核心机制说明、运维参考与工程开发规范。仓库根 [AGENTS.md](../AGENTS.md) 与 [ARCHITECTURE.md](../ARCHITECTURE.md) 的边界同样适用；完整信息架构与写作规范由 [文档编写与维护规范](develop-guides/documentation-guidelines.md) 维护。

## 目录职责

| 目录 | 定位 |
| --- | --- |
| `intro/` | 从零完成产品任务的顺序教程（按需建页） |
| `agents/` | Agent、工具、MCP、Skills 与 SubAgent 的配置和扩展指南（按需建页） |
| `mechanisms/` | 运行链路、状态、权限与失败恢复的机制解释（见 [mechanisms/index.md](mechanisms/index.md)） |
| `advanced/` | 部署、环境变量与运维参考（按需建页） |
| `develop-guides/` | 本地开发、前端设计、文档治理与决策记录（见 [decisions/README.md](develop-guides/decisions/README.md)） |
| `vibe/` | 已加入 `.gitignore` 的本地临时草稿与计划，不进 Git 也不作为权威事实 |

## 核心约束

- **单一事实 Owner**：源码、Schema、Compose 与测试拥有可执行事实；每条规则或说明只在一个页面完整维护，其他页面用一句话和相对 Markdown 链接引用，不复制第二份副本。
- **直接陈述现在时**：优先使用肯定句和现在时说明职责、条件与结果；不在当前文档中堆砌表结构字段、逐函数流程复述、PR 过程叙事或防御性禁令清单。
- **同步清理入站链接**：新增、移动、拆分或删除页面时，同一变更内更新全部相对链接。
- **提交前检查**：仅改文档时至少运行 `git diff --check` 并核对相对链接全部有效；涉及代码或配置变更时只记录实际执行过的验证。
