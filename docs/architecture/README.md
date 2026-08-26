# Architecture 文档说明

本目录给出 `agent-stack` 的架构主视图与边界定义，覆盖全系统运行层次与职责归属。

## 阅读入口

先按任务选择架构文档，再进入对应的能力规格。架构文档回答“哪个系统承载什么”，
`docs/spec/` 回答“该能力必须如何工作”。

| 任务范围 | 架构文档 | 能力规格 |
| --- | --- | --- |
| Agent 构造、上下文、子代理 | [agent-system.md](agent-system.md) | [docs/spec/agent](../spec/agent/README.md) |
| Run 生命周期、取消、事件流 | [run-system.md](run-system.md) | [docs/spec/run](../spec/run/README.md) |
| 知识上传、解析、索引、检索 | [knowledge-system.md](knowledge-system.md) | [docs/spec/knowledge](../spec/knowledge/README.md) |
| 状态和存储所有权 | [persistence-system.md](persistence-system.md) | [docs/spec/persistence](../spec/persistence/README.md) |
| 沙箱与工具执行隔离 | [sandbox-system.md](sandbox-system.md) | 暂无独立能力规格 |
| 认证和用户身份 | [auth-system.md](auth-system.md) | 暂无独立能力规格 |
| 跨系统拓扑和目录职责 | [overview.md](overview.md) | — |

- [overview.md](overview.md)
  - 全局运行拓扑、数据所有权与跨域约束。
- [run-system.md](run-system.md)
  - Run 生命周期与队列/事件流协作视图。
- [agent-system.md](agent-system.md)
  - 代理运行、工具与子代理协同边界。
- [knowledge-system.md](knowledge-system.md)
  - 知识处理与检索链路边界。
- [persistence-system.md](persistence-system.md)
  - PostgreSQL / Redis / MinIO / Milvus 的持久化边界。
- [sandbox-system.md](sandbox-system.md)
  - 工具执行隔离边界与服务职责。
- [auth-system.md](auth-system.md)
  - 用户身份、JWT 和受保护路由边界。

具体行为以 `docs/spec/` 为准；本目录只保留系统之间的承载关系、依赖方向和所有权边界。
