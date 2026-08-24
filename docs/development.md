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

## 本地基础设施和 Worker

```bash
docker compose -f docker/docker-compose.yml up -d postgres redis minio sandbox worker
```

## 后端定向验证

```bash
uv run --no-sync python -m compileall server/router server/service server/worker.py src/agents src/database/repositories src/storage
git diff --check
```

当前项目依赖中没有声明 `pytest`。除非已经安装并实际运行测试，否则不要报告 pytest 验证结果。
如果 `uv run` 因本地缓存权限受阻，请使用仓库虚拟环境，例如
`.venv/bin/python -m compileall -q <paths>`。

修改后端源码后必须重建 Compose Worker，因为 Worker 镜像没有绑定挂载当前工作区。
