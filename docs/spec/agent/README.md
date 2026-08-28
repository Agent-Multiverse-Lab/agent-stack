# Agent Domain

Agent Domain 管理代理能力的构造与执行边界，不直接负责持久化状态。先读取一个能力的现行契约，
需要处理当前变更时再读取其根目录 `plan.md` 和 `tasks.md`。

| Capability | 入口 | 职责 |
| --- | --- | --- |
| context-management | [README.md](context-management/README.md) | 运行上下文来源、合并与消费边界 |
| subagent-delegation | [README.md](subagent-delegation/README.md) | 父代理到子代理的委派机制 |

上下文先完成组装，再交给 Agent；子代理结果返回父流程；Run 状态仍由 Run Domain 管理。
