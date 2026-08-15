# ADR-0004: 沙箱能力独立服务运行

## Status
Accepted

## Context
代码执行、文件处理工具调用与对话逻辑耦合会扩大主服务风险面；主服务也不应承担执行环境生命周期管理。

## Decision
保持 `sandbox_server` 独立运行，主服务通过稳定 API 进行交互，避免在 FastAPI 或 Worker 内直接混入执行容器生命周期。

## Consequences
- 主服务可专注状态与流程治理。
- 工具/文件执行失败不会直接污染 run 状态更新路径，仍按统一异常入口记录。
- 沙箱侧可独立扩缩容和版本迭代。

## References
- [architecture/sandbox-system.md](../architecture/sandbox-system.md)
