# Tasks: Multimodal Asset Operations

## Task map

| Task ID | 关联需求 | 实施切片 | 可独立验证的结果 |
| --- | --- | --- | --- |
| MAO-001 | DP-MAO-001/002/003/005/007/008 | [platform-runtime.md](implementation/platform-runtime.md) | 资产目录、来源边界、质量与血缘 API 可运行 |
| MAO-002 | DP-MAO-004/005/008/009 | [platform-runtime.md](implementation/platform-runtime.md) | 两个 operation 完成幂等任务、取消、失败和成果闭环 |
| MAO-003 | DP-MAO-006/007/008 | [agent-runtime.md](implementation/agent-runtime.md) | `DataPlatformAgent` 经 child Run 调用平台 API 并返回证据 |
| MAO-004 | DP-MAO-010 | [evaluation-fixtures.md](implementation/evaluation-fixtures.md) | 固定 seed 多源数据稳定复现 bad case |
| MAO-005 | DP-MAO-001 至 DP-MAO-010 | 根计划 | 跨语言契约、端到端流程和架构所有权文档通过验收 |

## Done conditions

- 所有实现只覆盖现行 spec 的第一版范围，没有插件框架、任意 SQL 或管理页面。
- Agent Run 与平台 Job 的状态和持久化 Owner 清晰分离。
- Agent 不直接读取 PostgreSQL、MinIO 或处理 Worker。
- 测试断言稳定 ID、状态、来源、血缘和警告，不断言模型自由文本。
- 所有列入根计划的静态、迁移、契约和端到端检查如实记录结果。
