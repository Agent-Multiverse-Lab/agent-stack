# Multi-Agent S2C 文档总览

本目录采用“能力优先”的文档架构：  
先定义跨模块行为约束（Constitution / Architecture / ADR / Spec），再用 Plan/Tasks 指向实现边界。

## 推荐阅读顺序

- [doc/constitution.md](constitution.md)（宪章）
- [doc/architecture](architecture/README.md)（系统全景）
- [doc/adr](adr/README.md)（决策记录）
- [doc/spec](spec/README.md)（能力规范）

## 文档分层

1. `constitution.md`
2. `architecture/*`
3. `adr/*`
4. `spec/*`
5. `spec/*`（最新实现规范）

## 当前有效文档边界

- `doc/spec/` 仅保留按能力组织的规格（run、agent、knowledge、persistence）与实施计划。
- `doc/spec/server`、`doc/spec/src`、`doc/spec/web` 不再保留在主文档树，迁移/整理为能力文档后不另保留归档副本。
- 任何行为变更建议先改 `doc/spec/...` 的 spec，再由实现代码同步。
