# 开发指南

本文档集中记录本地开发、服务启动、数据库迁移和定向验证命令。

## 后端 API

```bash
uv sync
python server/main.py
```

## ARQ Worker

```bash
uv run --no-sync arq server.worker.WorkerSettings
```

## 数据库迁移

```bash
uv run --no-sync alembic upgrade head
uv run --no-sync alembic downgrade -1
```

卫星目录迁移完成后，可显式加载固定测试目录：

```bash
uv run --no-sync python scripts/load_satellite_catalog_fixture.py
```

## Satellite Gateway

```bash
cd gateway
go test ./...
go run ./cmd/server
```

启动前设置 `DATABASE_URL`（普通 PostgreSQL DSN）和 `GATEWAY_SHARED_TOKEN`。Python API/Worker
使用相同的 `SATELLITE_GATEWAY_TOKEN`，并通过 `SATELLITE_GATEWAY_TARGET` 指向 gRPC 服务。
Gateway 在 Compose 中属于 `gateway` profile，默认不启动。

## 本地基础设施和服务

在 WSL 中进行源码开发时，先只启动依赖服务：

```bash
docker compose up -d postgres redis rustfs milvus neo4j
```

API 和 Worker 可以从同机 Ubuntu 的 IDE/终端启动；执行隔离使用 CubeSandbox。
完整主机预检、节点启动、模板构建与 smoke 命令见
[CubeSandbox 部署指南](../docker/cube/README.md)。先填写 Cube 主机地址与三个独立凭据，
模板 READY 后填写 `CUBE_TEMPLATE_ID`。Windows 环境可做代码和单测验证，运行 VM 需要 Linux。

```bash
docker compose up -d --build cube-api cube-templatecenter cube-proxy cube-egress-net
# 完成部署指南中的模板构建和 smoke 后启动应用
docker compose up -d --build api worker
```

RustFS 是默认对象存储，在 `9000`（S3 API）和 `9001`（控制台）开放，数据写入
`save/volume/rustfs/data/`。应用继续通过 `MINIO_*` 环境变量配置 S3 客户端；Linux bind mount
目录需允许容器用户 UID/GID `10001:10001` 写入。

Compose 文件位于仓库根目录 `docker-compose.yml`，镜像构建文件仍在 `docker/`。
应用基础设施数据卷写入 `save/volume/`；Cube 使用 `/data/cube-stack`、`/data/cubelet` 等宿主机
目录，工作文件位于 `CUBE_HOST_SAVE_DIR`。已有部署若在 `volume/` 或 `docker/volume/`
保存数据，应在启动新 Compose 配置前把对应数据迁至 `save/volume/`，避免数据库和对象存储以空目录启动。

生产环境使用 `docker-compose.prod.yml` 覆盖配置。先从 `.env.template` 准备未提交的 `.env.prod`，
填写生产凭据，至少设置 `POSTGRES_PASSWORD`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`
以及应用所需的 `JWT_SECRET`、`MODEL_CREDENTIAL_KEY`。数据库密码会写入连接 URL，
请使用 URL 安全字符。随后运行：

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

此覆盖文件让 API/Worker 读取 `.env.prod`，仅将 API 的 `5050` 端口绑定到本机，
Cube 控制/调试端口保留 loopback 绑定，计算节点使用 host network，其余基础设施端口关闭。
同一主机上的开发和生产配置使用相同容器名与数据目录，
因此应选择其中一套运行。

## 后端定向验证

```bash
uv run --no-sync python -m compileall server/router server/service server/worker.py src/agents src/database/repositories src/storage
git diff --check
```

除非已经安装并实际运行对应测试，否则不要报告验证结果。
如果 `uv run` 因本地缓存权限受阻，请使用仓库虚拟环境，例如
`.venv/bin/python -m compileall -q <paths>`。

使用 Compose Worker 时，修改后端源码后必须重建镜像，因为 Worker 镜像没有绑定挂载当前工作区。

## CI 等价检查

GitHub Actions 对 `main` 的 Pull Request 和 push 执行以下核心检查：

```bash
uv sync --frozen --no-dev
uv run --no-sync python -m compileall -q server src

cd web
npm ci
npm run build
cd ..
```

这些命令只验证后端源码与前端产物可构建，不启动 Compose 服务，也不部署应用。
