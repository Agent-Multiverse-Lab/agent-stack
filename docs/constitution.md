# Multi-Agent S2C Constitution

## 1. 基本原则

### C1. Source of Truth
`PostgreSQL` 是业务持久化状态的唯一来源。  
`Redis` 仅用于运行时队列、信号和事件流；`ARQ` 仅用于后台任务分发。

### C2. 能力先于文件
跨模块行为按能力定义，不按单个源码文件作为架构说明来源。

### C3. 明确边界所有权
每个状态和关键流程只能有一个持久化 Owner，避免重复写入和互相覆盖。

### C4. 终态单向
`AgentRun` 的终态只能是 `completed` / `failed` / `cancelled`，且不可从终态回退。

### C5. 事件是副本，不是真相
`Redis Stream` 是消费型事件通道，不承接状态真相；状态读取与转移必须回到数据库。

### C6. 停止一致
`cancelled` 不得覆盖 `completed/failed`。  
`cancel_requested` 只是中间态，最终落库必须通过终态确定。

### C7. Stop at Spec
所有可观察行为改动先更新 `doc/spec` 的规格，再进入实现修改。

### C8. 可验证
关键行为（状态、取消、终态事件）必须有对应验收标准并可追踪测试点。

## 2. 领域边界

- `agent`：执行与子代理协作（上下文、工具链、中间件）。
- `run`：运行生命周期、取消与事件流。
- `knowledge`：知识上传、解析、检索与重排。
- `sandbox`：代码与工具执行隔离环境。
- `persistence`：PostgreSQL、Redis、MinIO、Milvus 的持久化职责。

