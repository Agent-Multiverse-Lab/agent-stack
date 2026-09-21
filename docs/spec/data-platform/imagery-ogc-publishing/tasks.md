# Tasks: 影像 OGC 发布控制面

## Task map

| Task ID | Requirement | Slice | Result |
| --- | --- | --- | --- |
| OGC-001 | DP-OGC-001/002/003/004 | [control-plane-data.md](implementation/control-plane-data.md) | 五张控制面表、约束和 fixture 可迁移验证 |
| OGC-002 | DP-OGC-002/005 | [gateway-runtime.md](implementation/gateway-runtime.md) | 有界查询、写入、状态迁移和并发控制可测试 |
| OGC-003 | DP-OGC-005/006 | [agent-runtime.md](implementation/agent-runtime.md) | SatelliteAgent 读取与 HIL 修改工具可调用 |
| OGC-004 | DP-OGC-004 | [control-plane-data.md](implementation/control-plane-data.md) | 参考接口歧义有确定的规范化测试 |
| OGC-005 | 全部 | 根计划 | 分层验证与部署边界有记录 |

## Done conditions

- 不修改既有卫星目录历史迁移，不复制栅格字节或 catalog 元数据。
- Agent 不直接连接数据库或对象存储，模型不能提供受信身份。
- 跨项目/跨 service 引用、无界查询和非法状态迁移在服务端失败。
- 修改工具必须经 HIL；读取工具不因审批阻塞。
- 完成结果不声称已经实现 WMTS/WMS renderer。
