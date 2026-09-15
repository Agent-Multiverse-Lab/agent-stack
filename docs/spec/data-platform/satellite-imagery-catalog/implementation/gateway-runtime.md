# Gateway Runtime Slice

关联需求：DP-SAT-002、DP-SAT-004  
关联任务：SAT-002

- `gateway/api/proto/satellite_catalog.proto` 是 Go/Python 唯一协议来源。
- `gateway/internal/catalog/` 负责范围校验、分页和 PostgreSQL/PostGIS 查询。
- `gateway/internal/grpcserver/` 从 metadata 读取可信项目范围并映射稳定 gRPC status。
- `gateway/cmd/server/` 启动 gRPC `:50051` 与标准库健康检查 `:8080`，不使用 Gin。
- `docker/gateway.Dockerfile` 与 Compose 提供独立服务；Gateway 使用普通 PostgreSQL DSN。
