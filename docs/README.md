# 文档总览

本目录采用“架构地图 + 按需短设计”的轻量文档结构：通过 `architecture/` 了解系统边界，再直接看源码；较大改动在 `develop/` 用单文件对齐方向。

## 文档结构

| 文档 | 职责 |
| --- | --- |
| [working-rules.md](working-rules.md) | Agent 工作规则与轻量设计规范 |
| [constitution.md](constitution.md) | 稳定的仓库级原则 |
| [architecture/](architecture/README.md) | 系统拓扑、模块职责和长期不变量 |
| [frontend/](frontend/README.md) | Web 目录、命名、组件、样式、品牌与交互规范 |
| [develop/](develop/README.md) | 进行中的单文件功能设计草稿（完成后收敛至 `architecture/` 并清理） |
| [development.md](development.md) | 本地开发、启动、迁移和验证命令 |
| [contributing.md](contributing.md) | 贡献流程和 Git 提交规范 |
| [adr/](adr/README.md) | 长期技术决策及其取舍理由 |

## 加载顺序

按任务范围按需读取，不扫描与当前任务无关的全部文档：

1. `working-rules.md`
2. `architecture/`（确定系统承载与边界后，直接阅读相关源码）
3. `frontend/`（任务涉及 `web/` 的页面、组件、目录、命名、样式或交互时）
4. `develop/`（仅当当前任务已有进行中的单文件设计稿时读取）
5. `development.md`（需要启动、迁移或验证时）
6. `contributing.md`（需要提交或发起 PR 时）
7. `adr/`（需要确认技术取舍时）

## 边界

- `docs/develop/` 仅存放当前活跃的功能单文件设计草稿，合入稳定后收敛长期约束至 `architecture/` 并清理过程文件。
- 普通功能变更直接实施，按需编写设计文档。
- 如果文档、测试和实现之间存在冲突，以真实源码和预期产品行为为准同步收敛文档。
