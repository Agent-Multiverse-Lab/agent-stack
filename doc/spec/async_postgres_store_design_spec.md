# AsyncPostgresStore 与 AsyncPostgresSaver 接入设计

状态：已实现；真实 PostgreSQL 集成验证仍需在可用数据库环境中执行。

术语说明：LangGraph 官方类名是 `AsyncPostgresSaver`。本文将其称为
LangGraph PostgreSQL Checkpointer；用户所说的 `AsyncPostgresCheckpointer`
对应的就是这个类，不新增同名自定义类。

相关代码：

- `src/agents/base_agent.py`
- `src/agents/leaderagent/agent.py`
- `src/agents/subagents/searchagent/agent.py`
- `src/agents/subagents/outlineagent/agent.py`
- `src/database/manger.py`
- `src/configs/config.py`
- `.env`
- `.env.template`
- `docker/docker-compose.yml`
- `server/lifespan.py`
- `server/worker.py`
- `test/test_langgraph_postgres_persistence.py`

## 1. 目标

本次接入为所有 Agent Graph 提供一组进程级共享的 PostgreSQL-backed LangGraph
持久化组件：

1. `BaseAgent` 暴露统一的 `get_store()` 和 `get_checkpointer()`。
2. `LeaderAgent`、`SearchAgent`、`OutlineAgent` 在各自的
   `create_agent(...)` 调用中分别传入 `store=` 和 `checkpointer=`。
3. Store 与 Checkpointer 的连接、初始化和释放由进程生命周期管理，不由一次 Agent Run
   临时创建。
4. Store 与 Checkpointer 的库表迁移在 worker 启动阶段单点执行，保证真正执行
   Agent 的进程在接单前可用。

首期同时启用普通持久化 KV Store 和 thread-level Checkpointer。以下内容不在本次范围：

- 启用 pgvector、Embedding 语义检索或向量索引。
- 启用 TTL sweeper。
- 新增长期记忆提取、写入、召回策略或记忆工具。
- 迁移现有 `/memory/` 文件数据。
- 基于 Checkpoint 自动恢复被取消或失败的 Agent Run。
- 将 Checkpoint 表当作业务消息、Agent Run 或会话表的替代品。

仅注入 Store 不会自动产生“长期记忆”行为；只有后续工具或中间件通过
`Runtime.store` / `ToolRuntime.store` 读写时，Store 中才会出现业务数据。仅注入
Checkpointer 也不会自动实现 Run 恢复；它只让 Graph 在同一个 `thread_id` 下持久化
状态，真正的恢复策略仍属于后续 worker/service 设计。

## 2. 实现前基础

当前依赖已经包含 Store 实现：

- `langgraph-checkpoint-postgres==3.0.5`
- `psycopg==3.3.4`
- `psycopg-pool==3.3.1`

公开导入路径为：

```python
from langgraph.store.postgres import AsyncPostgresStore, PoolConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
```

实施前代码尚未形成完整的 Store/Checkpointer 调用链：

- `BaseAgent.get_checkpointer()` 仍是空实现，没有 `get_store()`。
- 三个具体 Agent 的 `create_agent(...)` 已传入 `checkpointer=`，但实际 getter
  返回 `None`，因此当前并未启用 PostgreSQL Checkpointer，也没有调用
  `AsyncPostgresSaver.setup()`。
- 三个具体 Agent 都没有传入 `store=`。
- `PostgreManger.langgraph_checkpointer_pool` 只是 `None` 占位，并不是可用的
  Psycopg pool 或 `AsyncPostgresSaver` 实例。
- FastAPI lifespan 只初始化 API 进程的 PostgreSQL/Redis/Sandbox 资源。
- Agent Run 实际在独立 ARQ worker 中调用 `stream_agent_response(...)`。
- worker 有独立的 `startup()` / `shutdown()`，不会执行 FastAPI lifespan。

因此，只在 `server/lifespan.py` 中创建 Store，worker 进程无法获得该 Python
对象或连接池；只调用 `AsyncPostgresStore.setup()` / `AsyncPostgresSaver.setup()`
而不向 `create_agent(...)` 传入对应参数，也只会建表，不会让 Graph 使用持久化组件。

## 3. Store 与 Checkpointer 的边界

| 项目 | AsyncPostgresStore | AsyncPostgresSaver |
| --- | --- | --- |
| 官方角色 | LangGraph Store | LangGraph Checkpointer |
| 用途 | 跨 thread 保存共享 KV 数据 | 保存单个 Graph thread 的执行状态与恢复所需快照 |
| Graph 参数 | `store=` | `checkpointer=` |
| 典型作用域 | 用户偏好、跨会话记忆、共享资料 | 消息状态、节点状态、Checkpoint lineage、pending writes |
| 主要表 | `store_migrations`、`store` | `checkpoint_migrations`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes` |
| 初始化 | `await store.setup()` | `await checkpointer.setup()` |
| 本次处理 | 接入 | 接入，但不实现 Run 自动恢复策略 |

两者可以连接同一个 PostgreSQL 数据库，但不是同一个对象，也不能互相代替。
两者也不复用 SQLAlchemy/asyncpg engine 或 pool；各自使用 `langgraph-checkpoint-postgres`
内部的 Psycopg 3 连接资源。Store 的 `store` 表和 Checkpointer 的 `checkpoints` 表
都是 LangGraph 内部持久化表，不替代 PostgreSQL 业务模型中的 `Conversation`、
`Message` 或 `AgentRun`。

### 3.1 Checkpointer 的实际语义

`AsyncPostgresSaver` 是 LangGraph 的短期、thread 级状态持久化边界：

- Graph 执行时按照 `configurable.thread_id` 读取和写入最新 Checkpoint。
- `checkpoints` 保存序列化后的状态、元数据和父 Checkpoint 关系。
- `checkpoint_blobs` 保存不适合直接内联到主记录的 channel 数据。
- `checkpoint_writes` 保存节点或任务产生的 pending writes。
- `checkpoint_migrations` 记录 LangGraph 包自身的 schema 版本。

当前项目的 `thread_id` 来自 `Conversation.thread_id`；`uid` 不能替代
`thread_id` 作为 Checkpointer 主键。跨用户隔离首先依赖服务层的会话归属校验，
Graph 调用时再把同一个 `thread_id` 放入 `configurable`。Checkpointer 中的状态
也不能直接视为可展示的最终回答；最终消息和 Agent Run 状态仍以 PostgreSQL
业务表为准。

## 4. 资源所有权

### 4.1 PostgreManger

`PostgreManger` 是 Store 与 Checkpointer 资源的唯一所有者，负责：

- 在运行中的 event loop 内进入
  `AsyncPostgresStore.from_conn_string(...)` 和
  `AsyncPostgresSaver.from_conn_string(...)` 返回的异步上下文。
- 每个进程只保存一个共享的 `AsyncPostgresStore` 实例。
- 每个进程只保存一个共享的 `AsyncPostgresSaver` 实例。
- 提供带初始化检查的 `get_langgraph_store()` 和
  `get_langgraph_checkpointer()`。
- 在 `dispose()` 中按相反顺序退出两个 LangGraph 工厂上下文，再释放 SQLAlchemy engine。
- 初始化中途失败时释放已经打开的资源并重新抛出异常。

建议新增的最小状态：

```python
langgraph_store: AsyncPostgresStore | None
langgraph_checkpointer: AsyncPostgresSaver | None
_langgraph_resource_stack: AsyncExitStack | None
```

使用一个 `AsyncExitStack` 的原因是两个 `from_conn_string(...)` 都返回异步上下文
管理器，真正持有和关闭 Psycopg 连接资源的是这些上下文，而不是业务代码直接调用
`close()`。初始化时先进入 Store，再进入 Checkpointer；释放时由
`AsyncExitStack` 先关闭 Checkpointer，再关闭 Store，最后释放 SQLAlchemy engine。
当前版本的 `AsyncPostgresStore` 和 `AsyncPostgresSaver` 都不应由 manager 绕过
工厂上下文自行关闭。

两者仍然是两个独立的 Psycopg 连接资源。共享 PostgreSQL DSN 不等于共享连接池，
也不允许把 SQLAlchemy/asyncpg pool 强行传给任一 LangGraph 组件。

### 4.2 BaseAgent

`BaseAgent` 只暴露同步访问方法，不创建连接、不调用迁移、不缓存第二份 Store 或
Checkpointer：

```python
def get_store(self) -> AsyncPostgresStore:
    """获取当前进程已初始化的 LangGraph Store。"""
    return postgres_manager.get_langgraph_store()

def get_checkpointer(self) -> AsyncPostgresSaver:
    return postgres_manager.get_langgraph_checkpointer()
```

未完成进程初始化时两个方法都应抛出明确的 `RuntimeError`，不能返回 `None` 静默
关闭持久化。

不能在 `BaseAgent.__init__()` 中构造 Store 或 Checkpointer。`AgentManager` 在模块
加载阶段实例化 Agent，而两个 LangGraph PostgreSQL 组件都要求在运行中的 event
loop 中创建；Store 还会启动后台 batch task，Checkpointer 也会绑定创建时的
event loop。

也不能在每次 `get_agent()` 时构造它们。当前每个 Run 都会重新执行
`get_agent()`；这样会为每个 Run 创建新的连接或后台任务，且没有确定的关闭位置。

### 4.3 具体 Agent

Graph 仍由具体 Agent 组装，只增加现有参数；两个参数必须来自同一个进程级 manager：

```python
return create_agent(
    ...,
    checkpointer=self.get_checkpointer(),
    store=self.get_store(),
    ...,
)
```

三个真实调用点都要接入：

- `LeaderAgent._build_agent(...)`
- `SearchAgent.get_agent(...)`
- `OutlineAgent.get_agent(...)`

不为这一次参数注入新增 Agent 工厂或额外组装层。

## 5. 连接串与连接池

SQLAlchemy 与 LangGraph 使用两个显式配置的连接串：

```text
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/multi_agent_s2c
LANGGRAPH_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/multi_agent_s2c
```

`DATABASE_URL` 仅供 SQLAlchemy/asyncpg 使用，`LANGGRAPH_DATABASE_URL` 直接供
LangGraph/Psycopg 使用。两者可以指向同一个逻辑数据库，但运行时代码不解析、不转换，
也不从一个配置推导另一个配置。

Compose Worker 需要把两个地址中的主机都显式写为服务名 `postgres`，避免在容器内
错误访问 `localhost`。

Store 使用自己由 `from_conn_string(...)` 管理的 Psycopg async pool，不能复用
SQLAlchemy/asyncpg engine 或 pool。首期显式使用：

```python
PoolConfig(min_size=1, max_size=10)
```

`from_conn_string(...)` 会为池连接设置 Store 所需的：

- `autocommit=True`
- `prepare_threshold=0`
- `row_factory=dict_row`

首期不传 `index` 和 `ttl`。固定池大小先与当前 SQLAlchemy 基础池大小保持一致；只有
实际连接压力出现后，再增加环境配置，不提前增加未使用的调参项。

Checkpointer 使用不同的连接生命周期：

- `AsyncPostgresSaver.from_conn_string(dsn)` 是异步上下文管理器，首期由 manager
  持有其创建的 Psycopg `AsyncConnection`。
- 官方工厂会为连接设置 `autocommit=True`、`prepare_threshold=0` 和
  `row_factory=dict_row`；不要改用 SQLAlchemy/asyncpg 连接，也不要把 Store 的
  `AsyncConnectionPool` 传给 Checkpointer。
- `AsyncPostgresSaver.from_conn_string(...)` 不接受 Store 的 `PoolConfig`。首期不
  自行注入另一套 Checkpointer pool；如果 worker 并发验证后确实出现 Checkpointer
  连接瓶颈，再单独评估显式 `AsyncConnectionPool` 注入及其容量、关闭顺序和当前包
  版本兼容性。

生产部署应按 `langgraph-checkpoint-postgres` 的安全说明启用严格的 checkpoint
反序列化策略，例如设置 `LANGGRAPH_STRICT_MSGPACK=true`，或传入明确的允许模块
列表；不能把数据库可写权限交给不受信任的调用方。

## 6. 初始化、迁移与关闭时序

API 与 worker 是独立进程，各自拥有自己的 SQLAlchemy engine、Store 的 Psycopg
pool、Checkpointer 的 Psycopg connection 和对应实例，只共享 PostgreSQL 中的数据。

### 6.1 FastAPI 进程

```text
server.lifespan
  -> verify_required_auth_settings()
  -> postgres_manager.initialize()
       -> 创建 SQLAlchemy engine/session factory
       -> 进入 Store factory context，保存进程级 Store
       -> 进入 Checkpointer factory context，保存进程级 AsyncPostgresSaver
  -> init_sandbox_provider()
  -> yield
  -> shutdown_sandbox_provider()
  -> close_async_redis_client()
  -> postgres_manager.dispose()
       -> 退出 Checkpointer factory context
       -> 退出 Store factory context
       -> dispose SQLAlchemy engine
```

FastAPI lifespan 负责 API 进程资源的打开和关闭，但不是 LangGraph DDL 的唯一所有者。
当前 API 进程不执行 Agent Run，因此不需要在这里调用 `store.setup()`。

### 6.2 ARQ worker 进程

```text
server.worker.startup
  -> postgres_manager.initialize()
       -> 创建 SQLAlchemy engine/session factory
       -> 进入 Store factory context，保存进程级 Store
       -> 进入 Checkpointer factory context，保存进程级 AsyncPostgresSaver
  -> postgres_manager.ensure_tables_exist()
  -> postgres_manager.setup_langgraph_persistence()
       -> await langgraph_store.setup()
       -> await langgraph_checkpointer.setup()
  -> ensure_agents_exist()
  -> 开始接收 Agent Run

server.worker.shutdown
  -> postgres_manager.dispose()
       -> 退出 Checkpointer factory context
       -> 退出 Store factory context
       -> dispose SQLAlchemy engine
```

worker 是当前数据库 bootstrap 的单点所有者，`AsyncPostgresStore.setup()` 也放在这里。
`AsyncPostgresSaver.setup()` 同样放在这里。两个 setup 都由对应 LangGraph 包读取
迁移版本并补齐缺失迁移，不纳入 `Base.metadata.create_all()` 或 Alembic revision；
API 与 worker 不应并发执行任一套 LangGraph migration。

如果后续 API 进程也出现必须在 worker 之前直接读写 Store 的真实路径，应先调整
bootstrap 拓扑或增加独立迁移入口，不能直接把第二次 `setup()` 加进 lifespan。

### 6.3 setup() 的首期结果

不传 `index` 时，`setup()` 管理：

- `store_migrations`
- `store`
- `store.prefix` 查询索引
- `expires_at` / `ttl_minutes` 字段及过期时间索引

TTL 字段属于包内基础迁移，但首期不启动 TTL sweeper。不创建 `vector_migrations`、
`store_vectors`、pgvector extension 或向量索引。

Checkpointer 的 `setup()` 管理：

- `checkpoint_migrations`
- `checkpoints`
- `checkpoint_blobs`
- `checkpoint_writes`

这些表由 `AsyncPostgresSaver` 的包内 migration 管理，不由项目业务模型声明，
也不在 Alembic revision 中重复创建。Checkpointer setup 不会创建 Store 的向量表，
也不会启动 Run 恢复、清理或 TTL 任务。

## 7. 运行调用链

```text
worker process_agent_run(...)
  -> stream_agent_response(...)
  -> BaseAgent.stream_messages_with_event(...)
  -> concrete_agent.get_agent(context)
  -> BaseAgent.get_checkpointer()
  -> postgres_manager.get_langgraph_checkpointer()
  -> BaseAgent.get_store()
  -> postgres_manager.get_langgraph_store()
  -> create_agent(..., checkpointer=shared_checkpointer, store=shared_store)
  -> compiled graph 按 configurable.thread_id 读写 Checkpoint
  -> compiled graph 将 Store 注入 Runtime / ToolRuntime
```

Store 是进程级共享资源，但数据隔离不能依赖 Python 实例。后续真正增加记忆读写时，
namespace 必须显式包含 `uid`，并按业务需要再包含 Agent 或用途维度；本次没有写入者，
不提前定义一套未被使用的 namespace 协议。Checkpointer 则必须使用当前会话的
`thread_id`，不能为每次 `get_agent()` 或每个模型调用生成临时 thread ID。

## 8. 异常与幂等要求

- Store 或 Checkpointer 连接、上下文进入或初始化失败时，API/worker 启动失败，
  不降级为内存组件，也不静默传 `store=None` 或 `checkpointer=None`。
- worker 的 `setup()` 失败时，沿用现有 startup 的
  `try/except -> postgres_manager.dispose() -> raise` 路径，并记录异常上下文。
- `PostgreManger.initialize()` 在同一进程内重复调用应直接复用已初始化资源。
- `setup()` 可在不同时间串行重跑以应用缺失迁移，但不能据此假设并发执行安全。
- `get_langgraph_store()` 和 `get_langgraph_checkpointer()` 在未初始化时都直接抛出
  `_NOT_INITIALIZED_MSG` 对应的 `RuntimeError`。
- `dispose()` 按初始化逆序释放资源，先关闭 Checkpointer，再关闭 Store，最后清空
  LangGraph 引用、context、engine 和 session factory，并恢复未初始化状态。
- 正常的 `asyncio.CancelledError` 不作为 Store 或 Checkpointer 故障记录。

## 9. 文件级实施结果

已按以下文件边界完成实现：

1. `.env`、`.env.template`、`docker/docker-compose.yml`
   - 已分别配置本机和 Compose Worker 使用的 `LANGGRAPH_DATABASE_URL`。
2. `src/configs/config.py`
   - 已直接声明 `langgraph_database_url`，不再解析或转换 `DATABASE_URL`。
3. `src/database/manger.py`
   - 已持有进程级 Store、`AsyncPostgresSaver` 及一个统一的异步资源上下文。
   - 已在 `initialize()` / `dispose()` 中按逆序对称打开和关闭。
   - 已新增 `get_langgraph_store()`、`get_langgraph_checkpointer()` 和
     `setup_langgraph_persistence()`。
4. `src/agents/base_agent.py`
   - 已新增只读访问方法 `get_store()` 和 `get_checkpointer()`。
5. `src/agents/leaderagent/agent.py`
   - 已向 `create_agent(...)` 注入进程级 `store=` 和 `checkpointer=`。
6. `src/agents/subagents/searchagent/agent.py`
   - 已向 `create_agent(...)` 注入进程级 `store=` 和 `checkpointer=`。
7. `src/agents/subagents/outlineagent/agent.py`
   - 已向 `create_agent(...)` 注入进程级 `store=` 和 `checkpointer=`。
8. `server/worker.py`
   - 已在接收任务前单点执行 Store 与 Checkpointer 的 `setup()`。
9. `server/lifespan.py`
   - 保持薄生命周期入口；仅更新职责注释，具体构造仍归
     `PostgreManger`，不把连接代码放进 lifespan。
10. `test/`
   - 已使用 `unittest` 和 fake/context mock 验证单进程只创建一次 Store 与
     Checkpointer、缺少初始化时 fail fast、startup 失败会释放所有已打开资源、
     三个 Agent 都传入同一对进程级对象。

实现已将 `langgraph_checkpointer_pool` 这个 `None` 占位替换为明确的
`langgraph_checkpointer` 和资源上下文；不把 Store pool 与 Checkpointer 混用。
如果后续要求 Checkpointer 使用显式 Psycopg pool，需要另行确认当前
`langgraph-checkpoint-postgres` 版本的 pool 注入、并发容量和关闭顺序。

## 10. 验证计划

静态验证：

```bash
uv run --no-sync python -m compileall server/lifespan.py server/worker.py src/agents src/configs src/database
uv run --no-sync python -m unittest test.test_langgraph_postgres_persistence
git diff --check
```

可选 PostgreSQL 集成验证需要真实数据库，不并入默认单元测试：

1. 启动 worker，确认 Store 与 Checkpointer migration 都成功。
2. 通过 `aput()` 写入测试 namespace，再通过 `aget()` 读取 Store 数据。
3. 使用真实 Graph 在同一 `thread_id` 下连续执行两次，确认第二次能读取前一次的
   Checkpoint 状态；检查 `checkpoints`、`checkpoint_blobs` 和
   `checkpoint_writes` 表存在且有对应数据。
4. 重启 worker 后分别再次读取 Store 和同一 `thread_id` 的 Graph 状态，确认数据
   跨进程生命周期持久化。
5. 确认未创建 `store_vectors`，且未启动 TTL sweeper；本次也不把 Checkpoint 当作
   Agent Run 业务状态来源。

静态编译和 mock 测试只能证明接线与生命周期约束，不能替代上述真实 PostgreSQL
验证。

官方依据：

- [LangGraph persistence and PostgreSQL Store/Checkpointer examples](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [langgraph-checkpoint-postgres README](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/README.md)
- [AsyncPostgresSaver source](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/checkpoint/postgres/aio.py)

## 11. 评审结论

本方案对最初“在 `base_agent.py` 创建 Store，并在 lifespan setup”的表述作三点收口：

1. `BaseAgent` 新增的是 `get_store()` 和 `get_checkpointer()` 访问入口，两个组件
   本身都由数据库资源管理器按进程创建，避免导入期或每 Run 创建连接和后台任务。
2. FastAPI lifespan 只管理 API 进程资源；真正执行 Agent 的 worker 必须拥有自己的
   Store 与 Checkpointer，并作为当前唯一 bootstrap owner 执行两套 `setup()`。
3. `AsyncPostgresSaver` 负责 Graph thread 状态持久化，不替代 `AgentRun` 业务状态，
   Checkpoint 接入不等于已经实现 Run 自动恢复。

当前实现已完成静态编译、目标单元测试和本次新增代码的 Ruff 检查；只有依赖真实
PostgreSQL 的迁移与跨进程持久化验证尚未执行。
