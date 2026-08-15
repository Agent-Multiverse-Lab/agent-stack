# State Ownership Spec

## 1. Canonical Owners

- `PostgreSQL`: 所有业务真相（run 状态、用户、对话、知识元数据）
- `Redis`: 临时运行状态（队列、信号、事件）
- `MinIO`: 文件内容与中间解析产物
- `Milvus`: 检索向量和 metadata

## 2. Rules

### PS-OWN-001
终态必须以 PostgreSQL 为准，Redis 事件只用于补充可见性。

### PS-OWN-002
Redis key 具备生命周期（TTL），用于控制内存占用；数据库无此限制。

### PS-OWN-003
任何组件不得“反向写”其他层的权威字段（如通过流事件更新 run 状态）。
