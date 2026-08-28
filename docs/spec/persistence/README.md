# Persistence Domain

Persistence Domain 定义“谁持久化什么、谁负责清理”，不直接定义业务策略。

| Capability | 当前契约 | 职责 |
| --- | --- | --- |
| state-ownership | [spec.md](state-ownership/spec.md) | PostgreSQL、Redis、MinIO、Milvus 的状态和存储边界 |

只有处理当前实现变更时，才继续读取 capability 根目录的 `plan.md` 和 `tasks.md`。
