# `src/database/manger.py` 设计说明

## 1. 定位

`manger.py` 只负责 PostgreSQL 运行时资源管理，不负责业务表设计。

它的职责是把数据库启动、会话创建、schema 初始化和资源释放收口到一个地方，避免后续在 router、service、agent、repository 里重复处理连接生命周期。

不在这个文件里讨论表字段、索引、业务查询、ARQ、Redis Stream 或 agent 执行逻辑。

## 2. 当前基础

现有数据库基础能力在 `src/database/session.py`：

- `get_engine()`
- `get_session_maker()`
- `session_context()`
- `get_db()`

当前 `src/database/manger.py` 已有最小结构：

- `PostgreManger.__init__()`
- `PostgreManger.initialize()`
- `PostgreManger.create_schema()`

后续整理时，`PostgreManger` 应该复用 `session.py` 里的 engine 和 session factory，不要另起一套连接创建逻辑。

## 3. 需要管理的状态

`PostgreManger` 最少维护这些状态：

| 属性 | 含义 |
| --- | --- |
| `engine` | SQLAlchemy async engine，用于 schema 初始化和连接释放 |
| `session_maker` | async session factory，用于创建 repository 使用的 session |
| `langgraph_checkpointer_pool` | LangGraph checkpoint 使用的连接池；未接入前可先为 `None` |
| `initialized` | 初始化标记，防止重复初始化 |

`engine` 和 `session_maker` 默认从 `get_engine()`、`get_session_maker()` 获取；测试或特殊场景可以通过构造函数显式传入。

## 4. 初始化流程

`initialize()` 是 manager 的统一启动入口。

流程：

1. 如果 `initialized` 已经是 `True`，直接返回。
2. 准备或复用 `engine`。
3. 准备或复用 `session_maker`。
4. 预留 LangGraph checkpoint pool 初始化位置。
5. 标记 `initialized = True`。

`initialize()` 只做资源准备，不做破坏性操作。

## 5. Schema 初始化

`ensure_tables_exist()` 用当前 SQLAlchemy model 元数据创建缺失表，并对已有
`agent_run` 表补充非破坏性的 `run_type` 字段和索引：

```python
async def ensure_tables_exist(self) -> None:
    async with self.engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                bind=sync_connection,
                checkfirst=True,
            )
        )
```

该操作不删除、重建或清空已有表，也不填充用户、会话等业务数据。旧 Run 的
`run_type` 会按照已注册 Agent 的 `role` 回填为 `chat` 或 `subagent`，不会再根据
`parent_run_id` 推断。现阶段一个 `ensure_tables_exist()` 就够；不要提前拆
`create_business_table()`、`create_knowledge_table()` 之类的方法，除非后面真的有
多套 metadata 或多库隔离。

当前由 ARQ worker startup 单点调用该方法；FastAPI lifespan 只初始化自身数据库连接，不重复执行 schema bootstrap。Worker shutdown 只释放资源，不执行任何建表或固定数据写入。

## 6. Session 上下文

Manager 需要提供一个 session 上下文入口：

```python
def get_async_session_context(self) -> AsyncContextManager[AsyncSession]:
    ...
```

职责：

1. 确认 manager 已初始化。
2. 返回 async session context。
3. 让 service 或 repository 在 context 内执行数据库操作。

它不强制自动 commit。当前项目里 repository/service 已经有自己控制 commit 的路径，manager 先只管 session 生命周期。

## 7. 关闭流程

Manager 需要提供 `dispose()`：

```python
async def dispose(self) -> None:
    ...
```

职责：

1. 关闭 LangGraph checkpoint pool，如果已经初始化。
2. dispose SQLAlchemy engine。
3. 清空或重置本地状态。
4. 标记 `initialized = False`。

## 8. 错误处理

依赖初始化状态的方法必须显式检查 `initialized`。

未初始化时直接抛错：

```python
RuntimeError("PostgreManger is not initialized.")
```

不要静默跳过。静默跳过会隐藏启动顺序问题。

## 9. 单例入口

最终暴露一个模块级实例即可：

```python
postgres_manager = PostgreManger()
```

外部代码优先通过这个实例调用：

- `initialize()`
- `ensure_tables_exist()`
- `get_async_session_context()`
- `dispose()`

## 10. 不做的事

这些都不放进 `manger.py`：

- agent 执行
- ARQ 入队
- ARQ worker 消费
- Redis Stream 发布和订阅
- MinIO 上传下载
- repository 业务 CRUD
- router 参数校验
- 具体表结构设计

## 11. 最小落地版本

下一步实现 `manger.py` 时，最小闭环是：

1. `PostgreManger.__init__`
2. `PostgreManger.initialize`
3. `PostgreManger.create_schema`
4. `PostgreManger.get_async_session_context`
5. `PostgreManger.dispose`
6. `postgres_manager = PostgreManger()`

LangGraph checkpoint pool 现在还没定具体接入方式，可以先保留属性和初始化位置，用 `None` 占位，不要提前写复杂封装。
