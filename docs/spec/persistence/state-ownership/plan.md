# Implementation Plan: State Ownership

1. 明确 run 状态、error、cancel 信号的持久化路径。
2. 事件消费端仅做「补齐」且不做主状态重放。
3. 建立文档映射，避免在 server/doc/web 代码内再次出现权威误用。

## Mapping

- `src/database/models.py`: 状态字段定义
- `src/database/repositories/*`: 持久化更新入口
- `server/service/arq_queue_servcie.py`: 流与信号管理
