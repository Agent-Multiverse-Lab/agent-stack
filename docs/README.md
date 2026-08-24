# Multi-Agent S2C 文档总览

本目录采用“能力优先”的文档架构：  
先定义跨模块行为约束（Constitution / Architecture / ADR / Spec），再用 Plan/Tasks 指向实现边界。

## 推荐阅读顺序

- [docs/working-rules.md](working-rules.md)（开发与代理规则）
- [docs/constitution.md](constitution.md)（宪章）
- [docs/architecture](architecture/README.md)（系统全景）
- [docs/spec](spec/README.md)（能力规范）
- [docs/development.md](development.md)（开发与验证）
- [docs/contributing.md](contributing.md)（贡献与提交）
- [docs/adr](adr/README.md)（决策记录）

## 文档分层

1. `working-rules.md`
2. `constitution.md`
3. `architecture/*`
4. `spec/*`（最新能力规范）
5. `development.md`（需要启动或验证时）
6. `contributing.md`（需要提交或发起 PR 时）
7. `adr/*`（需要确认技术取舍时）

## 当前有效文档边界

- `docs/spec/` 仅保留按能力组织的规格（run、agent、knowledge、persistence、product）与实施计划。
- `docs/spec/server`、`docs/spec/src`、`docs/spec/web` 不再保留在主文档树，迁移/整理为能力文档后不另保留归档副本。
- 任何行为变更建议先改 `docs/spec/...` 的 spec，再由实现代码同步。

## 文档职责

- `working-rules.md`：Agent 工作规则和变更边界。
- `constitution.md`：稳定的仓库级原则。
- `architecture/`：系统拓扑、模块职责和所有权边界。
- `spec/`：能力行为、契约、实施计划和验收标准。
- `development.md`：本地开发、启动、迁移和验证命令。
- `contributing.md`：贡献流程和 Git 提交规范。
- `adr/`：长期技术决策及其取舍理由。

如果文档、测试和实现之间存在冲突，先识别冲突并确定权威文档，再继续修改。
