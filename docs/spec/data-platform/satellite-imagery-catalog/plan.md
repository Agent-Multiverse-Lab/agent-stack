# Implementation Plan: Satellite Imagery Catalog

计划版本：v0.1.0

## 1. Scope

实现 DP-SAT-001 至 DP-SAT-006 的最小目录链路：Alembic/PostGIS 保存卫星业务数据，Go `gateway/`
提供 gRPC 查询，现有 `SatelliteAgent` 通过 Python 客户端使用目录结果并继续编排 MCP 处理工具。

## 2. Implementation order

1. 按 [catalog-data.md](implementation/catalog-data.md) 建表并建立固定 seed 多来源目录。
2. 按 [gateway-runtime.md](implementation/gateway-runtime.md) 实现 protobuf、Go 查询与容器拓扑。
3. 按 [agent-runtime.md](implementation/agent-runtime.md) 接入 Python 客户端和 SatelliteAgent 工具。
4. 完成静态、Go/Python 契约及可用环境中的迁移验证后更新架构文档。

## 3. Shared constraints

- Alembic 是唯一 schema owner；Go 启动时只连接和查询，不执行 DDL。
- PostgreSQL/PostGIS 保存目录真相，MinIO 保存影像对象；`object_ref` 不包含永久凭据。
- Gateway 只负责数据服务，不复制 MCP 的影像算法和处理状态机。
- bbox、时间、分页和项目范围在 Gateway 服务端再次校验。
- 生成代码来自唯一 proto，不手工维护第二套协议模型。

## 4. Validation

- `go test ./...`（`gateway/`）
- `python -m unittest -v test.test_satellite_gateway test.test_satellite_agent`
- `ruff check`、`python -m py_compile`、`git diff --check`
- 有 PostgreSQL/PostGIS 与 Docker 时执行 migration、fixture load 和真实 gRPC smoke test。
