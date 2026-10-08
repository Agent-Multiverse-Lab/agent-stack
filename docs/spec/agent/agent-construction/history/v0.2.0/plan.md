# 内置 Agent 按 Backend ID 解析执行类
计划版本：v0.2.0

状态：执行类解析、SQL 属性直接构造实例、启动时补齐缺失 Agent，以及 `is_subagent` 字段和迁移代码
已实施；本地现有数据库已迁移到 `0014_agent_is_subagent`，5 条 Agent 的既有属性保持不变。
模拟模型和经用户授权的真实 DashScope 模型均已通过 PostgreSQL、Redis/ARQ 的父子 Run 验证。

关联契约：[Agent Construction Spec](../../spec.md) 的 AG-CON-001 至 AG-CON-005。

## 1. 统一入口与标识

所有运行入口统一通过 `agent.get_agent_class(backend_id)` 获取执行类，然后按本次 Run 创建实例。
函数实现在 `src/agents/buildin/__init__.py`，调用方使用完整模块路径：

```python
import src.agents.buildin as agent

agent_class = agent.get_agent_class(agent_record.backend_id)
```

这里传给解析函数的 Agent 标识就是 **Backend ID**，其值等于继承 `BaseAgent` 的实体类名。
参数命名为 `backend_id`，明确它与数据库中具体角色的 `slug` 的区别：

| 标识或属性 | 示例 | 职责 |
| --- | --- | --- |
| SQL `agent.slug` | `search_agent`、`citation_agent` | 查询具体角色及其属性配置 |
| SQL `agent.backend_id` | `LeaderAgent`、`SubAgentGraph` | 传给 `get_agent_class`，定位执行类 |
| SQL `agent.is_subagent` | `false`、`true` | 标记角色类型、校验记录、选择实例构造参数 |
| `AgentLibrary` | 名称、描述、Prompt、Context 预设 | 为启动时缺失的 Agent 提供初始属性 |

`get_agent_class` 只有一个参数，不接收角色 slug、`is_subagent` 或 `AgentLibrary`。
返回值是 `type[BaseAgent]`，具体映射只有两项：

| Backend ID | 返回的类 |
| --- | --- |
| `LeaderAgent` | `LeaderAgent(BaseAgent)` |
| `SubAgentGraph` | `SubAgentGraph(BaseAgent)` |

例如 `search_agent` 和 `citation_agent` 是两条不同的角色记录，
但它们的 `backend_id` 都是 `SubAgentGraph`，因此取得同一个执行类。
不同角色的属性通过各自的 Context 生效；每次 Run 创建新的执行实例。

## 2. 函数实现

目标文件：`src/agents/buildin/__init__.py`。
负责函数：`get_agent_class()`。

```python
from src.agents.base_agent import BaseAgent
from src.agents.buildin.leader.agent import LeaderAgent
from src.agents.buildin.subagents.subagent_graph import SubAgentGraph

AGENT_CLASSES: dict[str, type[BaseAgent]] = {
    "LeaderAgent": LeaderAgent,
    "SubAgentGraph": SubAgentGraph,
}


def get_agent_class(backend_id: str) -> type[BaseAgent]:
    agent_class = AGENT_CLASSES.get(backend_id)
    if agent_class is None:
        raise ValueError(f"未知 Agent backend：{backend_id}")
    return agent_class
```

函数精确匹配这两个类名；空字符串、大小写不匹配、未知 Backend ID 和角色 slug 均报错。
不会把无法识别的输入自动视为子 Agent，也不使用反射或动态模块导入。
执行类通过完整模块路径导入，集中存放在 `AGENT_CLASSES` 常量字典中；
扩展类查找时只需添加字典项，无需增加函数分支。

此入口只负责取得执行类；角色存在性、启用状态、Run 类型和属性装配仍由 Service 负责。
取得执行类不代表该角色获得运行许可。

## 3. 运行入口与 Worker 接入

目标文件：`server/service/thread_service.py`。
负责函数：`_build_agent_runtime()`。

```text
角色 slug
  → 原有会话归属校验
  → AgentRepository.get_by_slug_for_run_type(slug, run_type)
  → 得到已启用且适用于本次 Run 的 agent_record
  → agent.get_agent_class(agent_record.backend_id)
  → 校验角色标记及属性配置
  → 每次 Run 创建新的执行实例
  → 从 agent_record.agent_config 组装本次运行 Context
  → instance.get_agent(context)
```

把函数中的 SQL 记录变量命名为 `agent_record`，避免覆盖导入的 `agent` 模块。
取得记录后的实例创建部分如下：

```python
agent_class = agent.get_agent_class(agent_record.backend_id)

expected_role = "subagent" if agent_record.is_subagent else "orchestrator"
expected_backend = "SubAgentGraph" if agent_record.is_subagent else "LeaderAgent"
if agent_record.role != expected_role or agent_record.backend_id != expected_backend:
    raise ValueError(f"Agent 角色或 backend 配置不一致：{agent_record.slug}")

if agent_record.is_subagent:
    agent_instance = agent_class()
else:
    rows = await agent_repo.list_agents(role="subagent", internal_only=True)
    subagents = tuple(
        {"slug": row.slug, "name": row.name, "description": row.description}
        for row in rows
    )
    agent_instance = agent_class(
        name=agent_record.name,
        description=agent_record.description,
        subagents=subagents,
    )

return agent_record, agent_instance
```

`is_subagent` 在这里用于检查数据是否一致及准备构造参数，执行类始终由 Backend ID 解析。
Service 已移除 `AGENT_CLASSES`、两个具体执行类的直接导入以及 AgentLibrary 的导入和转换。
实例创建前直接校验 SQL 的 `agent_config`：必须为字典且可 JSON 序列化，不允许 Run 身份或未知 Context 字段。
Leader 接收 `name`、`description` 和子角色字典列表；SubAgentGraph 保持无自定义 `__init__`。
普通执行、子 Run、Resume 共用这个创建入口，Context 继续由 SQL 配置和当前 Run 参数组装。

目标文件：`src/agents/buildin/leader/agent.py`、`src/agents/middlewares/subagent_middlware.py`。
`LeaderAgent.__init__()` 与 `SubAgentMiddleware.__init__()` 复制子角色字典，运行期间不保留 ORM 记录，
也不依赖 AgentLibrary。字典只传递 slug、名称、描述；Middleware 继续通过 slug 创建子 Run。
`AgentLibrary.from_record()` 已删除，AgentLibrary 仅用于启动初始化预设。

目标文件：`server/worker.py`。负责函数：`ensure_agents_exist()`。
Worker 同样导入 `src.agents.buildin as agent`，注册前通过 Backend ID 获取类：

```python
for definition in definitions:
    agent_class = agent.get_agent_class(definition.backend_id)
    definition.validate_context(agent_class.agent_context)
```

Worker 不再从 Thread Service 导入类映射。
注册循环的局部变量使用 `definition`，避免与模块名冲突。
主角色与子角色按原有分组调用 `AgentRepository.ensure_agent()`，按 slug 补齐缺失记录。
AgentLibrary 中的预定义角色只提供首次创建的属性；记录已存在时，所有字段均保留数据库中的值。
运行时从 SQL 记录提取属性，不重新套用预设；运行实例、编译后的图和运行身份不进入属性预设。

目标文件：`src/database/repositories/agent_repository.py`。负责方法：`ensure_agent()`。
该部分已实现，使用 slug 唯一约束处理重复启动及并发初始化：

```python
statement = insert(Agent).values(slug=definition.slug, enabled=True, **values)
statement = statement.on_conflict_do_nothing(index_elements=[Agent.slug])
await self.session.execute(statement)
```

`values` 包含预设属性和创建时的角色标记；冲突时不执行更新，也不自动修正已有 backend 或配置。

## 4. 已补充的 SQL 标记

`src/database/models.py:Agent.is_subagent` 为 `BOOLEAN NOT NULL DEFAULT FALSE`。
`AgentRepository.ensure_agent()` 仅在插入新记录时根据 `role == "subagent"` 写入它，冲突时保留原值。
`0014_agent_is_subagent` 迁移增加列并按已有 `role` 回填，降级只删除新列。
该标记保留为角色属性，不作为 `get_agent_class()` 的输入或替代 Backend ID。

## 5. 实施落点与验证

1. 在 `buildin/__init__.py` 实现唯一的 `get_agent_class(backend_id)`。
2. 修改 `_build_agent_runtime()` 和 `ensure_agents_exist()` 的类获取调用，删除原有类映射。
3. 移除 Service、Leader、子代理 Middleware 的 AgentLibrary 依赖，直接传递 SQL 属性及子角色字典。
4. 更新 `test/test_agent_construction.py`，验证解析结果、仅存在于 SQL 的角色及每次 Run 的实例创建；
   更新 `test/test_thread_stream_events.py` 中对 `AGENT_CLASSES` 的 mock，
   改为 mock `thread_service.agent.get_agent_class`。
5. 同步 `docs/architecture/agent-system.md` 中的入口归属说明，保持现有队列与执行流程。

按 ponytail 最小方案，直接使用现有 `buildin` 包入口，类选择逻辑只有一份。
非目标：新增管理器、注册框架、独立工厂文件、执行实例缓存或新的子 Run 调度入口。

验收覆盖：

- 两个合法 Backend ID 分别返回对应类，且 `issubclass(result, BaseAgent)` 为真。
- 返回类的 `__name__` 与传入的 Backend ID 一致。
- 空值、未知类名、大小写不匹配及 `search_agent` 这类角色 slug 均被解析函数拒绝。
- 多条不同角色记录使用 `backend_id="SubAgentGraph"`，得到相同执行类和各自独立的实例、Context。
- 不存在、禁用或 Run 类型不匹配的角色在 SQL 查询环节失败。
- `role`、`is_subagent`、`backend_id` 不一致时失败；Context 未知字段继续被拒绝。
- 主角色和子角色正确传递各自构造参数；SQL 属性不被代码默认值覆盖。
- 运行时不构造 AgentLibrary，SQL 独有角色正常运行；Leader 和 Middleware 使用 SQL 中的名称与描述。
- Worker、普通执行、子 Run、Resume 的类获取均经过同一入口。
- 启动时补齐缺失角色；重复初始化不覆盖已有记录的任何字段，也不创建重复 slug。
- SQL 标记的默认值、非空约束、回填、新记录写入及降级保持已有验证。

定向验证：

```bash
.venv/bin/python -m pytest -q test/test_agent_construction.py test/test_thread_stream_events.py test/test_subagent_middleware_prompt.py test/test_agent_run_interrupt_resume.py test/test_image_processing_agent.py test/test_ask_user_tool.py
.venv/bin/ruff check src/agents/buildin src/agents/agent_library/__init__.py src/agents/middlewares/subagent_middlware.py server/service/thread_service.py server/worker.py test/test_agent_construction.py test/test_thread_stream_events.py test/test_subagent_middleware_prompt.py test/test_ask_user_tool.py
.venv/bin/python -m compileall -q src/agents/buildin src/agents/agent_library src/agents/middlewares/subagent_middlware.py server/service/thread_service.py server/worker.py
git diff --check
```

定向测试使用内存数据库和模拟模型。现有 PostgreSQL 已实际执行 `0014_agent_is_subagent`，
迁移前后比对确认 5 条 Agent 的其他字段保持不变，新增标记与 role 一致。
真实模型请求在用户明确授权后执行，使用 DashScope `qwen3.8-max` 和合成引用校验任务。
Leader 与 citation 子 Run 均为 `completed`，均保存输出消息；子 Run 的父关联、uid、Prompt 和模型配置正确。
验证使用临时数据库及独立 ARQ 队列，结束后已清理；未验证浏览器或真实 MCP/沙箱工具执行。

验证过程还发现非 v3 消息转换遗漏返回值，导致完整 AI 消息/空片段中断流。
已补齐文本事件和列表返回，并增加完整消息与空片段的回归用例。

2026-10-08 验收记录：

- 上下文、构造、委派、Resume、摘要和持久化接线：52 项测试、30 个子用例通过。
- 流式转换修复后：27 项流式/Resume 测试、16 个子用例通过，包含新增回归。
- Ruff、`compileall -q server src` 和 `git diff --check` 通过。
- 真实数据库迁移：`MIGRATION_OK`，5 条记录既有属性保持不变。
- 两次基础设施验证（模拟模型、真实模型）均得到 `INTEGRATION_OK` 和 `CLEANUP_OK`。
