# Knowledge Domain

Knowledge Domain 关注知识文件与检索能力，不承载 Run 状态。先读取一个能力的 `spec.md`；需要处理
当前变更时再读取同目录根部的 `plan.md` 和 `tasks.md`。

| Capability | 当前契约 | 职责 |
| --- | --- | --- |
| ingestion | [spec.md](ingestion/spec.md) | 上传、解析、切块、索引 |
| retrieval | [spec.md](retrieval/spec.md) | 检索与重排 |
| evaluation | [spec.md](evaluation/spec.md) | 知识链路质量评估 |
