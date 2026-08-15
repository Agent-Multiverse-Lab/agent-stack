# Architecture 文档说明

本目录给出 `multi-agent-s2c` 的架构主视图与边界定义，覆盖全系统运行层次与职责归属。

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
