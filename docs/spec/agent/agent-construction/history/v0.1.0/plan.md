# Agent library 与运行时创建计划
计划版本：v0.1.0

## 1. 当前状态与实施范围

状态：实施完成，定向测试和真实 Worker 集成验证通过。

本次将预定义角色、SQL 注册与每次 Run 的创建分开，取消 `AgentManager`。
它目前承担的四项职责分别落入已有边界：

| 当前职责 | 目标承载位置 |
| --- | --- |
| 扫描目录并发现 Agent class | `src/agents/agent_library/` 中按角色文件声明的实体实例 |
| 为 Worker 提供注册信息 | 定义清单与 `AgentRepository` 的 SQL 同步 |
| 提供公开 Agent 列表 | `thread_router` 查询 SQL 中公开且启用的 orchestrator |
| 缓存并返回执行实例 | `thread_service._build_agent_runtime()` 直接实例化 |

SQL 中的 class 标识仍需要对应代码实现。仅在 `thread_service.py` 中维护两个 class 的字典，
不增加 IoC 框架、Factory、注册服务或新的调度通道。

## 2. 目标文件与数据关系

对应 AG-CON-001/002/003/005：

```text
src/agents/
├── agent_library/
│   ├── __init__.py      # 共用的 AgentLibrary 实体类
│   ├── leader.py        # Leader 的预定义实体
│   └── subagents/
│       ├── __init__.py  # 导入各角色实体并汇总注册清单
│       ├── search.py
│       ├── citation.py
│       ├── image_processing.py
│       └── satellite.py
├── leaderagent/          # Leader 自己的构图实现
├── subagents/
│   ├── __init__.py
│   ├── subagent_context.py
│   └── subagentgraph.py  # 所有子 Agent 共用的执行类
└── ...                  # 现有通用执行协议和中间件
```

工具与 Middleware 的必要实现归入现有工具适配层、通用中间件和 backend。
专业子目录在行为迁移和引用替换完成后删除；`manager.py` 同时退出业务代码。

保留已有 SQL 身份，例如：

| slug | backend_id | role |
| --- | --- | --- |
| `LeaderAgent` | `LeaderAgent` | orchestrator |
| `search_agent` | `SubAgentGraph` | subagent |
| `citation_agent` | `SubAgentGraph` | subagent |
| `image_processing_agent` | `SubAgentGraph` | subagent |
| `satellite_agent` | `SubAgentGraph` | subagent |

不修改已有会话和 Run 保存的 slug，不增加数据库表或字段。

## 3. 角色定义与 SQL 同步

对应 AG-CON-001/002。目标文件：`agent_library/__init__.py` 的 `AgentLibrary`、
`agent_library/leader.py` 与 `agent_library/subagents/` 各角色文件的预定义实体、
`server/worker.py` 的 `ensure_agents_exist()`，
以及 `src/database/repositories/agent_repository.py` 的定义同步方法。

实体类放在 `src/agents/agent_library/__init__.py`：

```python
from dataclasses import dataclass
from typing import Any


@dataclass(kw_only=True)
class AgentLibrary:
    slug: str
    name: str
    description: str
    backend_id: str
    context: dict[str, Any]
```

Search 角色在 `src/agents/agent_library/subagents/search.py` 中直接实例化该实体类：

```python
from src.agents.agent_library import AgentLibrary

SEARCH_PROMPT = "你负责资料检索、来源比较和证据整理。"

SEARCH_AGENT = AgentLibrary(
    slug="search_agent",
    name="资料检索",
    description="检索资料、比较来源并整理证据",
    backend_id="SubAgentGraph",
    context={"system_prompt": SEARCH_PROMPT},
)
```

其他角色分别在 `citation.py`、`image_processing.py`、`satellite.py` 中声明各自的实体和 Prompt。
`agent_library/subagents/__init__.py` 仅导入和汇总这些实体：

```python
from .search import SEARCH_AGENT
from .citation import CITATION_AGENT
from .image_processing import IMAGE_AGENT
from .satellite import SATELLITE_AGENT

SUBAGENTS = (SEARCH_AGENT, CITATION_AGENT, IMAGE_AGENT, SATELLITE_AGENT)
```

Leader 的实体由 `agent_library/leader.py` 声明；Worker 显式导入 `LEADER_AGENT` 和 `SUBAGENTS` 同步 SQL。
角色名称、描述、Prompt 和其他预设参数都在对应角色文件中填写。

`AgentLibrary.from_record()` 作为实体类的方法，从已查询的 SQL 行构造实体，并复制 `agent_config`。
Python 定义用于部署时同步，SQL 行是执行时配置来源；执行时不再叠加另一份全局定义配置。
现有专业 Agent 中的 Prompt 迁入 `agent_library/subagents/` 对应角色文件中实体的配置，
按第 6 节确定共同结果契约后的实际语义维护。

现有 `ensure_agent_registered()` 只补缺失记录，不能更新旧 `backend_id`。
将其替换为按 slug 同步声明字段的 repository 方法，并由 Worker 在一个事务中调用。
Worker 启用该同步的变更与新 Graph、运行解析入口同时交付，避免已有 backend 提前被改成尚不可执行的标识。
同步 `name`、`description`、`backend_id`、`agent_config`、`role`、`internal_only`；
已有记录保留主键、slug 和 `enabled`，新记录使用现有启用默认值。
同一份声明重复同步得到相同配置；同步失败终止启动事务。

`context` 仅包含 JSON 可表示的预设参数；运行身份字段不得来自定义。
同步前检查重复 slug、支持的 backend 标识和 Context 配置字段。

## 4. 运行入口直接实例化

对应 AG-CON-004/005。目标文件：`server/service/thread_service.py` 的
`_build_agent_runtime()`、`_build_agent_runtime_context()`、普通流和 Resume 入口。

结构示例：

```python
AGENT_CLASSES = {
    "LeaderAgent": LeaderAgent,
    "SubAgentGraph": SubAgentGraph,
}

# _build_agent_runtime()：现有 SQL 查询完成之后
definition = AgentLibrary.from_record(agent_row)
agent_class = AGENT_CLASSES[definition.backend_id]
constructor_args = {"definition": definition}
if agent_row.role == "orchestrator":
    constructor_args["subagents"] = tuple(
        AgentLibrary.from_record(row) for row in enabled_subagent_rows
    )
agent_instance = agent_class(**constructor_args)
```

`enabled_subagent_rows` 由当前事务中的 repository 查询得到。
不直接按数据库字符串 import Python 模块；未知 backend 转为清晰的运行初始化错误。

Context 合并在现有 service 入口完成：

1. 复制 SQL `agent_config` 的预设配置。
2. 应用当前 Run 的显式配置；模型未选择时保留预设值。
3. 写入可信的 `uid`、`run_id`、`thread_id`、`request_id` 等运行身份。
4. 将同一份配置传入现有 `BaseAgent` 执行路径，由其创建对应 Context。

保持 `agent_context` 为 Context class；不将配置字典或 Context 实例赋给它。
service 中预检 Context 和实际构图 Context 必须使用同一份合并配置。
`BaseAgent` 执行方法和 LangGraph persistence 配置保持现有协议。

普通流目前把 Run 类型固定为 `chat`；改为透传 Worker 提供的 `run_type`，以正常解析子角色。
Resume 目前固定取缓存 `LeaderAgent`；改为按原 Run 的 slug 走同一 SQL 解析和实例化入口，
继续使用原会话 checkpoint 与 `Command(resume=...)`。

## 5. 通用构图与 Leader 委派

对应 AG-CON-003/004，并遵循 AG-SUB-001/002。目标文件：
`subagents/subagentgraph.py` 的 `SubAgentGraph`、`subagent_context.py`、
`leaderagent/agent.py` 的 `LeaderAgent` 和 `middlewares/subagent_middlware.py`。

结构示例；共同工具和 Middleware 的具体清单按第 6 节确认：

```python
class SubAgentGraph(BaseAgent):
    agent_context = SubAgentContext

    def __init__(self, *, definition: AgentLibrary):
        super().__init__()
        self.definition = definition
        self.name = definition.name
        self.description = definition.description

    async def get_agent(self, context: SubAgentContext):
        return create_agent(
            model=load_model(context.model or sys_config.default_model),
            system_prompt=context.system_prompt,
            tools=await self._create_tools(context),
            middleware=self._create_middlewares(context),
            context_schema=SubAgentContext,
            checkpointer=self.get_checkpointer(),
            store=self.get_store(),
        )
```

`_create_tools()`、`_create_middlewares()` 在该 class 内完成共同装配。
现有 `SubAgentContext.parent_thread_id` 缺少类型标注，补为有效 dataclass 字段；
保留 Context class 的每次 Run 构造方式。

Leader 的构造参数接收自己的 `definition` 和子 Agent 定义集合，仍使用自己的构图方法。
Middleware 接收 `Sequence[AgentLibrary]`，用 `definition.slug` 建索引，用名称和描述展示可用角色。
原来的 `subagent.name` 不能继续兼作 slug，因为新定义的人类可读名称与 slug 已分离。

执行控制流：

```text
Leader 的 task / subagent_start
  → 选择专业 slug
  → 现有 service 创建并入队子 AgentRun
  → Worker 按 slug 查询 SQL 定义
  → backend_id 对应 class
  → SubAgentGraph(definition=definition)
  → 本次 SubAgentContext
  → get_agent(context) 构图并执行
```

Middleware 不创建或执行子 Graph；不把 class、定义实例或 Context 对象传过 ARQ。
现有 `task` 创建子 Run 后等待结果，`subagent_start` 返回运行标识；保持这两种行为。
完成 `task` 验证前修复现有等待链路的必要缺陷：传入 uid、await 结果加载，
按事件列表和游标循环读取并检查 SQL 终态，遵守既有超时和取消语义。
这些修复在 `agent_run_service.py` 与 Middleware 调用点完成，不另建结果等待服务。
既有 AgentRunTimeOut 构造缺少 self，已修正为携带 run_id 的 TimeoutError。
真实 Worker 验证发现工具事件中的 Command 不能直接 JSON 序列化；Thread Service 在流事件边界
复用 BaseAgent 的 unpack_data 转换，确保 task 结果转发后父流程能继续执行。

## 6. 共同能力与专业规则

所有子角色使用同一工具和 Middleware 装配：

| 能力 | 实施落点 |
| --- | --- |
| 知识/网络检索 | `src/knowledge/tools.py` 保留原检索实现，共同 Graph 装配三个检索工具 |
| 目录 gRPC 和 MCP | SubAgentGraph 装配 Gateway 目录工具和 MCP；Gateway 参数进入 SubAgentContext |
| 沙箱与文件系统 | 共同 Graph 使用原 SandboxMiddleware 和 FilesystemMiddleware |
| MCP 与图片验证 | 公共 ImageValidationMiddleware 只包装 MCP 工具；图片角色通过 require_mcp_tools 预设要求工具可用 |
| 结果表达 | Citation、Satellite 的 Pydantic 报告模型与 JSON Schema 位于对应角色文件，并写入专业 Prompt；共同 State 保留原有可选任务字段 |
| 模型重试 | 共同 Graph 使用一次 ModelRetryMiddleware 重试 |

检索角色使用 flash_model，其余角色使用 default_model。运行时显式模型可覆盖这些预设。
检索 Prompt 已调整为使用实际共同工具完成有界查询，不要求子角色再次委派。
Citation 虽然具备共同工具，但 Prompt 仍要求仅校验调用方提供的声明和证据。
角色定位由各自文件的 Prompt 和 Context 预设决定；共享构造不按角色另选 builder。
Leader 在全部子角色被禁用时跳过委派 Middleware，保留独立执行能力。

## 7. 列表、引用和目录收尾

对应 AG-CON-005。目标文件：`server/router/thread_router.py` 的公开列表、
`src/agents/__init__.py`、`subagents/__init__.py`、现有 Agent 测试及架构文档。

- 公开列表用 repository 查询 `enabled=true`、`role=orchestrator`、`internal_only=false`；
  保留现有 `AgentSummary` 结构，`id` 使用 slug。请求增加现有数据库依赖。
- Worker、service、router 和测试替换完调用后，删除 `src/agents/manager.py` 及其导出。
- 将保留的专业工具、验证和数据模型迁入对应公共职责位置，再删除
  `searchagent/`、`citationagent/`、`imageprocessingagent/`、`satelliteagent/` 专业 Agent 包。
  现有 `sub_agent.py` 仅有说明文本，统一入口落定后删除该冗余文件。
- 更新 Agent 架构和涉及 Satellite Agent 落点的数据平台文档，保持业务能力职责一致。
  不增加兼容导出或旧 class 回退。

用户已批准本计划的删除和移动范围；迁移所需行为后清理旧目录。

## 8. 顺序与验证

任务顺序见 [tasks.md](tasks.md)。先通过局部测试验证定义和共同构图；
Worker 同步、执行入口、Leader 装配和旧路径清理作为一次完整切换交付，保持运行路径完整。
不先部署会更新 SQL backend、但仍依赖旧实例管理器的阶段代码。

重点验证放在一个新的 `test/test_agent_construction.py` 中，现有行为测试随调用点修改：

1. 两个不同专业 slug 指向同一 class，SQL 配置选中各自 Prompt；两次创建得到不同实例。
2. 定义配置、运行 Context 和嵌套集合互不污染，未选择模型时不丢失预设模型。
3. 同步更新旧 backend 与配置，保留主键、slug、禁用状态；重复同步无语义变化。
4. 公开列表不含子角色；普通流、子 Run 和 Resume 都按 SQL 选择并创建实现。
5. 专业能力的行为检查依据第 6 节定稿内容迁移，保留实际工具与验证效果检查。

定向测试以现有 `unittest` 组织方式运行，并执行后端 `compileall`、引用检索和
`git diff --check`。不增加新的测试框架。

在实际 PostgreSQL/Redis/ARQ Worker 环境验证一次 `Leader task → 子 Run → 通用 Graph → 结果`，
检查专业 Prompt、本次运行身份与 `parent_run_id`。真实模型执行使用现有配置方式，
不把密钥写入定义或计划。单测和模拟检查不代替该集成验证。

验证结果随实际执行记录；定向单测、模拟模型构图与真实 Worker 集成分别报告。

## 9. 实施验证记录

2026-10-07：

- 66 项定向 unittest 通过，覆盖 SQL 同步、不同 slug 共用 class、新实例与 Context 隔离、
  Prompt 实际生效、内存 checkpoint、委派工具、普通流、Resume、MCP 图片校验、Gateway 和 Run repository。
- 改动 Python 文件的 Ruff 检查通过；`compileall -q server src` 和 `git diff --check` 通过。
- 实际使用既有模型配置、新建临时 PostgreSQL 数据库与独立 Redis/ARQ 队列验证：
  Leader 的 task 调用 citation_agent，Worker 创建 SubAgentGraph，子 Run 与父 Run 均 completed，
  二者 output_message_id 均已落库；子 Run 的 run_type、parent_run_id、uid 和专业 Prompt 正确，
  SQL 结果包含声明与来源标识，父 Agent 取得结果后继续完成。测试资源已清理。
- 扩展检查仍有现存测试阻碍：`test_worker_stream_event_smoother` 导入已不存在的 AgentRunContext；
  `test_thread_conversation_service` 的待交互 Run 夹具缺少 thread_id；`test_agent_run_service` 固定假定
  gemini/gemini-3-pro 不在当前配置目录。对应生产逻辑不属于本次改动，未修改这些测试假设。

定向命令：

```bash
NUMBA_DISABLE_JIT=1 .venv/bin/python -m unittest \
  test.test_agent_construction test.test_citation_agent test.test_satellite_agent \
  test.test_image_processing_agent test.test_image_validation_middleware \
  test.test_subagent_middleware_prompt test.test_agent_run_interrupt_resume \
  test.test_langfuse_execution_config test.test_thread_stream_events \
  test.test_langgraph_postgres_persistence test.test_satellite_gateway \
  test.test_agent_run_repository -q
```

NUMBA_DISABLE_JIT 只避免知识模块导入时的无关 JIT 编译；测试需要正常的 asyncio 线程回收与本地 gRPC 端口。
上线时同时更新 API 和 Worker；重启 Worker 后按预定义 slug 同步已有 SQL backend/config，保留记录主键和禁用状态。
