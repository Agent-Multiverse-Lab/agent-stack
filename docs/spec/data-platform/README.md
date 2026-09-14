# Data Platform Domain

Data Platform Domain 管理通用数据资产从登记、检索、加工到成果追溯的能力。它不承载
Agent Run 生命周期，也不把领域专有字段固化到核心模型。

| Capability | 当前契约 | 职责 |
| --- | --- | --- |
| multimodal-asset-operations | [spec.md](multimodal-asset-operations/spec.md) | 多源资产目录、受控加工、成果血缘与 Agent 接管 |

Agent 的委派和取消仍遵循
[Subagent Delegation Spec](../agent/subagent-delegation/spec.md)，平台任务状态由 Data Platform
Domain 自己持久化。
