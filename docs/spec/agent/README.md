# Agent Domain

Agent Domain 管理代理能力的构造与执行边界，不直接负责持久化状态存储。

## 子能力

- `context-management/`：运行上下文组装与变更规范
- `subagent-delegation/`：父代理到子代理的委派机制

## 运行关系

1. 上下文先组装，再喂给 `leader agent`
2. 子代理执行结果返回给父流程
3. 运行/终态仍依赖 `run domain` 完成
