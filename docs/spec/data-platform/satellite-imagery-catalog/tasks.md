# Tasks: Satellite Imagery Catalog

## Task map

| Task ID | Requirement | Slice | Result |
| --- | --- | --- | --- |
| SAT-001 | DP-SAT-001/002/003 | [catalog-data.md](implementation/catalog-data.md) | 四张目录表和固定数据可建立 |
| SAT-002 | DP-SAT-002/004 | [gateway-runtime.md](implementation/gateway-runtime.md) | Go gRPC 检索、详情、隔离和分页可运行 |
| SAT-003 | DP-SAT-003/005 | [agent-runtime.md](implementation/agent-runtime.md) | SatelliteAgent 使用目录工具并保留 MCP |
| SAT-004 | DP-SAT-006 | [catalog-data.md](implementation/catalog-data.md) | bad-case fixture 可重复生成 |
| SAT-005 | 全部 | 根计划 | 分层测试与部署说明完成 |

## Done conditions

- Agent 不直接连接 PostgreSQL/PostGIS 或 MinIO。
- Go 不建表、不执行影像算法、不拥有 Agent Run。
- 无界检索和跨项目访问在服务端失败。
- 测试不依赖公网模型，也不提交大型影像二进制。
