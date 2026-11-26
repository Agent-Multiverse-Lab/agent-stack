# Architecture 文档说明

本目录给出 `agent-stack` 的架构主视图、系统边界与长期不变量；具体类定义、接口和字段以真实源码与测试为准。

## 阅读入口

按任务范围选择对应的架构文档，确认系统承载关系与边界后直接阅读相关源码：

| 任务范围 | 架构文档 |
| --- | --- |
| Agent 构造、上下文、子代理 | [agent-system.md](agent-system.md) |
| Run 生命周期、取消、事件流 | [run-system.md](run-system.md) |
| 知识上传、解析、索引、检索 | [knowledge-system.md](knowledge-system.md) |
| 状态和存储所有权 | [persistence-system.md](persistence-system.md) |
| 沙箱与工具执行隔离 | [sandbox-system.md](sandbox-system.md) |
| 模型供应商预置、平台配置和模型列表缓存 | [model-system.md](model-system.md) |
| 卫星影像多源目录 | [data-platform-system.md](data-platform-system.md) |
| 认证和用户身份 | [auth-system.md](auth-system.md) |
| 跨系统拓扑和目录职责 | [overview.md](overview.md) |

- [overview.md](overview.md)
  - 全局运行拓扑、数据所有权与跨域约束。
- [run-system.md](run-system.md)
  - Run 生命周期与队列/事件流协作视图。
- [agent-system.md](agent-system.md)
  - 代理运行、工具与子代理协同边界。
- [knowledge-system.md](knowledge-system.md)
  - 知识处理与检索链路边界。
- [persistence-system.md](persistence-system.md)
  - PostgreSQL / Redis / RustFS / Milvus 的持久化边界。
- [sandbox-system.md](sandbox-system.md)
  - 工具执行隔离边界与服务职责。
- [model-system.md](model-system.md)
  - 模型供应商预置、平台配置真相、Redis 全局模型列表与运行时连接解析。
- [auth-system.md](auth-system.md)
  - 用户身份、JWT 和受保护路由边界。
- [data-platform-system.md](data-platform-system.md)
  - Go Gateway、PostGIS 卫星目录与 SatelliteAgent 的依赖边界。

本目录只维护系统间的承载关系、依赖方向、所有权边界和长期不变量，不镜像源码实现细节。
