# Agent library 与运行时创建任务

状态：实施完成。方案细节与验证结果见 [plan.md](plan.md)。以下工作项均已完成。

| Task ID | 关联需求 | 工作项 | 完成验证 |
| --- | --- | --- | --- |
| AGC-001 | AG-CON-003 | 确认共同工具、Middleware、Context 与结果表达；将专业行为迁移清单补入计划第 6 节，并确认目录删除范围 | 专业能力均有明确承接方式，无待定实现路径 |
| AGC-002 | AG-CON-001/002 | 定义共用 AgentLibrary 实体；各角色在 agent_library/subagents/ 对应命名的文件中声明实例；实现并测试 SQL 同步，Worker 切换随 AGC-005 一起交付 | 角色属性位于对应文件，旧 backend 更新，配置落库，主键和禁用状态保留 |
| AGC-003 | AG-CON-003/004 | 实现 SubAgentGraph 与共同 SubAgentContext；迁移确认保留的工具和 Middleware | 两个专业角色共用构图，Prompt 和配置各自生效 |
| AGC-004 | AG-CON-003/005；AG-SUB-001/002 | Leader 注入定义集合；Middleware 使用独立 slug 和角色描述 | 不创建子实例即可展示角色并创建、入队子 Run |
| AGC-005 | AG-CON-002/004/005；AG-CONT-001/003 | 普通执行与 Resume 改为 SQL 查询后直接实例化；统一配置合并，修复 run_type 透传；Worker 启用定义同步 | 实例与 Context 隔离，模型覆盖正确，Resume 延续原 checkpoint |
| AGC-006 | AG-CON-004；AG-SUB-004 | 修复现有 uid、await 和事件列表等待问题，复用 SQL 结果和既有取消/超时契约 | task 和 subagent_await 获得终态结果，失败和超时可追踪 |
| AGC-007 | AG-CON-005；AG-SUB-005 | 公开列表查询 SQL；替换测试引用，删除 Manager 和专业 Agent 包，维护架构及相关落点文档 | 内部角色不可见，导入可用，旧实现引用清零 |
| AGC-008 | AG-CON-001 至 AG-CON-005 | 定向测试、compileall、diff 检查和真实 Worker 子 Run 验证 | 分别记录单测、模拟检查与实际集成结果 |

AGC-001 至 AGC-008 已完成。定向测试 66 项通过，真实模型与 PostgreSQL/Redis/ARQ Worker
委派链路通过，Ruff、compileall 和 diff 检查通过。临时数据库与队列已清理。
