# Data Platform Domain

Data Platform Domain 管理卫星影像多来源目录与受控访问。它不承载 Agent Run 生命周期，
也不在数据 Gateway 中执行影像算法。

| Capability | 当前契约 | 职责 |
| --- | --- | --- |
| satellite-imagery-catalog | [spec.md](satellite-imagery-catalog/spec.md) | 卫星来源、集合、场景、波段资产与 Agent 接管 |
| imagery-ogc-publishing | [spec.md](imagery-ogc-publishing/spec.md) | 影像图层、主题、发布状态与 OGC 服务控制面 |

Agent 的委派和取消仍遵循
[Subagent Delegation Spec](../agent/subagent-delegation/spec.md)，平台任务状态由 Data Platform
Domain 自己持久化。
