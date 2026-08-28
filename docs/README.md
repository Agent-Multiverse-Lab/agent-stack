# 文档总览

本目录采用“能力优先、渐进披露”的文档架构：先用 architecture 定位系统，再读取一个
capability 的现行 spec；只有需要设计或实施时才加载该 capability 当前的 plan / tasks。

## 文档结构

| 文档 | 职责 |
| --- | --- |
| [working-rules.md](working-rules.md) | Agent 工作规则和变更边界 |
| [constitution.md](constitution.md) | 稳定的仓库级原则 |
| [architecture/](architecture/README.md) | 系统拓扑、模块职责和所有权边界 |
| [spec/](spec/README.md) | 现行能力契约、当前实施包和按版本隔离的计划历史 |
| [development.md](development.md) | 本地开发、启动、迁移和验证命令 |
| [contributing.md](contributing.md) | 贡献流程和 Git 提交规范 |
| [adr/](adr/README.md) | 长期技术决策及其取舍理由 |

## 加载顺序

按任务范围按需读取，不扫描与当前任务无关的全部文档：

1. `working-rules.md`
2. `architecture/`（确定承载该任务的系统）
3. `spec/`（对应 domain README 和 capability 的 `spec.md`；需要实施时读取该能力当前的
   `plan.md` / `tasks.md`，再按任务读取指定的 `implementation/` 切片）
4. `development.md`（需要启动、迁移或验证时）
5. `contributing.md`（需要提交或发起 PR 时）
6. `adr/`（需要确认技术取舍时）

## 边界

- `docs/spec/` 仅保留按能力组织的规格（run、agent、knowledge、persistence、product）与实施计划，
  不镜像源码目录。
- 任何行为变更先改 `docs/spec/` 的 spec，再由实现代码同步。
- `history/` 只保存已完成计划快照，不参与默认上下文；不要为了了解当前契约读取历史版本。
- 如果文档、测试和实现之间存在冲突，先识别冲突并确定权威文档，再继续修改。
