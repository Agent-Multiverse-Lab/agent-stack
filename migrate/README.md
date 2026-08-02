# 数据库迁移样例

`migrate/` 只保存数据库结构的版本变更，不负责应用启动、数据库连接管理、
业务数据初始化、Worker、Agent 或队列逻辑。

当前目录只提供 Alembic 迁移骨架和空版本样例，不包含真实 Schema 变更，也不会
由 FastAPI 或 ARQ Worker 自动执行。

## 版本文件

每个版本文件通过 `revision` 和 `down_revision` 连接前后版本，并提供两个入口：

- `upgrade()`：把数据库升级到当前版本。
- `downgrade()`：尽可能退回上一个版本。

以后增加或修改 Schema 时，复制 `versions/0001_example.py`，更新版本号和
`down_revision`，然后分别实现 `upgrade()` 和 `downgrade()`。普通业务数据修改
不应放入迁移；只有与结构变更强绑定的数据回填才属于迁移范围。

## 执行

```bash
uv run --no-sync alembic upgrade head
uv run --no-sync alembic downgrade -1
```

即使版本文件中的两个函数为空，执行命令仍会创建或更新 Alembic 自己的
`alembic_version` 版本记录。本样例不会在仓库验证过程中连接或修改真实数据库。
