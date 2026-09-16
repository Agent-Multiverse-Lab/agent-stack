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

## 本地基础设施和 Worker

```bash
docker compose up -d postgres redis minio sandbox gateway worker
```

RustFS 是独立的可选服务，不替换当前 MinIO。需要单独试用时运行 `docker compose up -d rustfs`；
默认仅在本机 `29000`（S3 API）和 `29001`（控制台）开放，数据写入 `save/volume/rustfs/data/`。
访问密钥和主机端口可通过 `.env` 中的 `RUSTFS_*` 变量调整。Linux bind mount 目录需允许容器用户
UID/GID `10001:10001` 写入。

Compose 文件位于仓库根目录 `docker-compose.yml`，镜像构建文件仍在 `docker/`。
数据卷路径相对仓库根目录，写入 `save/volume/`。已有部署若在 `volume/` 或 `docker/volume/`
保存数据，应在启动新 Compose 配置前把对应数据迁至 `save/volume/`，避免数据库和对象存储以空目录启动。

## 后端定向验证

```bash
uv run --no-sync python -m compileall server/router server/service server/worker.py src/agents src/database/repositories src/storage
git diff --check
```

除非已经安装并实际运行对应测试，否则不要报告验证结果。
如果 `uv run` 因本地缓存权限受阻，请使用仓库虚拟环境，例如
`.venv/bin/python -m compileall -q <paths>`。

修改后端源码后必须重建 Compose Worker，因为 Worker 镜像没有绑定挂载当前工作区。

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
