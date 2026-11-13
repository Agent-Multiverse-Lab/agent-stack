# Agent Run 请求持久化与触发计划

## 1. 当前任务

为 `POST /api/agent/runs` 增加 `AgentRunRequest` 持久化，在活动 Run 判断前提交请求。

`create_agent_run_service` 的执行顺序为：检查会话、创建输入消息和 Run、提交事务、调用 `enqueue_agent_run`。本次将请求、输入消息和附件关联放入接收事务，Run 创建放入第二个事务。Run 创建、提交、按 `run_id` 入队的顺序保持不变。

数据模型、接口和流程图见 [spec.md](spec.md)。

## 2. 任务目标

1. 在活动 Run 判断前提交请求、输入消息和附件关联。
2. 会话无活动 Run 且无待回答问题时，创建 `AgentRun`，提交后按 `run_id` 入队。
3. 会话存在活动 Run 或待回答问题时，保留请求并返回 409。
4. 使用 `request_id` 关联请求、输入消息和 Run；重复提交使用已保存的记录。
5. Run 创建或入队失败时，保留已提交的请求。

## 3. 如何修改

### 3.1 请求持久化

- 在 `src/database/models.py` 定义 `AgentRunRequest`，表名为 `agent_run_request`。
- 在 `src/database/repositories/agent_run_request_repository.py` 实现按请求 ID 查询和插入，并提供 Alembic 迁移。
- 接收事务锁定会话，检查用户、会话、Agent、模型和附件，保存请求、输入消息及附件关联后提交。
- 请求内容、模型选择、输入关联和重复提交规则按 [spec.md](spec.md) 第 2、3 节实现。
- 请求表保存标识与 `trigger_message_id`；正文、图片和消息元数据从 Message 读取，会话配置从 Conversation 读取。DAO 返回 ORM 记录，Service 使用 Request 和已锁定的 Conversation 组装本层的 `AgentRunRequestInput`。
- 接收事务失败时回滚并清理复制目标；提交后清理复制源。

### 3.2 会话活动判断

请求提交后，第二个事务取得会话行锁并执行以下分支：

| 条件 | 操作 |
| --- | --- |
| `request_id` 已关联 Run 且归属检查通过 | 返回该 Run |
| `get_pending_interaction_run` 返回记录 | 保留请求，返回 409 |
| `get_latest_active_for_thread` 返回记录 | 保留请求，返回 409 |
| 以上查询均未命中 | 读取会话当前配置并校验模型，创建 `pending` Run，设置输入消息的 `agent_run_id`，提交事务 |

会话行锁覆盖查询、Run 创建和输入关联，事务提交或回滚时释放。

### 3.3 创建 Run 并提交后入队

Run 创建事务提交后调用 `enqueue_agent_run(run_id)`。ARQ Job ID 为 `run:{run_id}`，执行入口为 `process_agent_run(run_id)`。

Run 创建失败时，回滚第二个事务并传播错误。入队失败时，调用 `set_agent_terminal(status="failed")` 处理尚未认领的 Run，保存 `error/error_type` 并提交。两条失败路径均保留接收事务提交的数据。

### 3.4 接口响应

创建 Run 或查到请求关联的 Run 时，返回 `run_id`、`thread_id`、Run `status`、`request_id` 和 `stream_url`。

存在活动 Run 或待回答问题时，请求已提交，响应为 HTTP 409 和 `detail`。状态码、字段及错误文案见 [spec.md](spec.md) 第 4 节。

## 4. 实施步骤（计划）

1. 添加请求模型、Repository 导出和迁移，实现按请求 ID 查询与插入。
2. 修改接收服务，拆分接收事务和 Run 创建事务，接入请求幂等查询。
3. 在 Run 创建事务提交后调用 `enqueue_agent_run`，保留入队失败的终态写入。
4. 检查 Router 的 HTTP 200、409 响应与规格中的字段和文案是否相同。
5. 更新 Run 架构和持久化所有权文档，记录请求表和两个事务的职责。
6. 添加请求保存、会话活动判断、重复提交、并发触发和入队失败测试；执行迁移升级与回退、后端编译检查和 `git diff --check`。

## 5. 验收标准

- 调用 `enqueue_agent_run` 时，另一个数据库会话能读取请求、Run 及其输入消息。
- 存在活动 Run 或待回答问题时返回 409；该请求的记录数为 1，关联 Run 数为 0，入队调用次数为 0。
- 同一请求重复提交后，请求记录数为 1，输入消息数为 1，关联 Run 数最多为 1。
- 同一会话并发触发时，Run 创建事务通过会话锁串行执行；因活动 Run 返回 409 的请求记录保留。
- Run 创建事务回滚后，请求及输入仍能按 `request_id` 查询。
- 入队失败后，尚未认领的 Run 状态为 `failed`，`error/error_type` 保存异常信息。
- ARQ 调用 `process_agent_run(run_id)`；HTTP 响应的 `run_id` 和 `stream_url` 指向已提交的 Run。
- 迁移升级创建请求表，回退删除请求表；记录测试、编译和差异检查的执行结果。
