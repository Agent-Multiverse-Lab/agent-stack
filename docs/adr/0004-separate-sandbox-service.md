# ADR-0004: 沙箱能力独立服务运行

## Status
Accepted

## Context
代码执行、文件处理工具调用与对话逻辑耦合会扩大主服务风险面；主服务也不应承担执行环境生命周期管理。

## Decision
使用独立的 CubeSandbox 控制服务和 MicroVM 计算节点。主服务通过 CubeAPI/CubeProxy 交互，
在 `src/agents/backends/sandbox/` 适配现有工具协议；部署由根 Compose 与 `docker/cube/` 管理。
FastAPI/Worker 不直接管理 Docker 容器。会话通过 Cube metadata 发现实例，Redis 锁协调创建；
业务库不保存 Cube 实例 ID，Cube 自身状态使用独立数据库。

## Consequences
- 主服务可专注状态与流程治理。
- 工具/文件执行失败不会直接污染 run 状态更新路径，仍按统一异常入口记录。
- 沙箱侧可独立扩缩容和版本迭代。

## References
- [architecture/sandbox-system.md](../architecture/sandbox-system.md)
