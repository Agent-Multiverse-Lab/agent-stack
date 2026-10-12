# Sandbox System Architecture

## 1. Responsibility

提供工具/代码执行隔离边界，避免主应用与外部执行环境混用。

## 2. Deployment Model

- Cube 控制服务和计算节点由根 Compose 编排，配置及预检见 `docker/cube/`。
- API/Worker 通过 CubeMaster inventory 发现会话实例，通过 CubeAPI 获取/连接实例，通过
  CubeProxy 调用实例内的 envd；VM 由 Cubelet 管理。
- Cube 使用独立 PostgreSQL 数据库、Redis DB 1 和模板制品目录，应用持久化职责不变。

## 3. Runtime Rules

- 沙箱服务可在主请求失败后回收，不影响 run 主流程的持久化状态。
- 主服务不依赖沙箱本地状态做 run 终态决策。
- 沙箱返回错误通过标准化错误码与日志回传给上游服务。
- `(uid, thread_id)` 对应 Cube metadata；业务库不保存 `cube_sandbox_id`。
- 每次工具调用重新发现并连接实例，跨进程创建由应用 Redis 锁串行化。只有明确不存在才重建。
- 本地引用在调用结束时释放；有限空闲 TTL 由 Cube 回收 VM，宿主机工作文件保留。

## 4. Security Boundary

- 命令在 VM 中执行；Composite 文件路由和 VM Host Mount 共享同一会话工作目录。
- 工作区 API 先校验会话归属，再访问该实例的 `/workspace`；技能目录在 VM 内只读。
- 主服务只下发最小参数，不传递敏感会话凭据。
- API/Worker 不持有 Docker Socket；控制端口仅供可信服务访问。目标主机仍需完成部署及隔离验收。

能力契约见 [cube-runtime](../spec/sandbox/cube-runtime/spec.md)，启动步骤见
[部署指南](../../docker/cube/README.md)。
