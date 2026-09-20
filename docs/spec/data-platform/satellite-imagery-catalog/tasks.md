# Tasks: 卫星数据资源库

## Task map

| Task ID | Requirement | Slice | Result |
| --- | --- | --- | --- |
| SAT-001 | DP-SAT-001/002/003/007 | [catalog-data.md](implementation/catalog-data.md) | 核对四表并迁移 Asset key 唯一约束 |
| SAT-002 | DP-SAT-002/004/007 | [gateway-runtime.md](implementation/gateway-runtime.md) | Go gRPC 检索、详情含 Asset key、隔离和分页可运行 |
| SAT-003 | DP-SAT-003/005/007 | [agent-runtime.md](implementation/agent-runtime.md) | SatelliteAgent 保留 Asset key 并使用目录与 MCP 工具 |
| SAT-004 | DP-SAT-006 | [catalog-data.md](implementation/catalog-data.md) | bad-case fixture 可重复生成 |
| SAT-005 | 全部 | 根计划 | 分层测试与部署说明完成 |
| SAT-006 | DP-SAT-001/003/007/008 | [catalog-data.md](implementation/catalog-data.md) | STAC 1.1.0 多来源 Collection/Item 经校验后幂等导入现有四表 |
| SAT-007 | DP-SAT-002/003/004/008 | 根计划 | 在指定目标库验证迁移、空间查询、项目隔离和资产详情 |

## Done conditions

- Agent 不直接连接 PostgreSQL/PostGIS 或 RustFS。
- Go 不建表、不执行影像算法、不拥有 Agent Run。
- 无界检索和跨项目访问在服务端失败。
- 测试不依赖公网模型，也不提交大型影像二进制。
