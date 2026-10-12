# CubeSandbox 当前实施任务

对应 [plan.md](plan.md) v0.1.0。

- [x] T1a — 固定 SDK 与组件镜像标签，核对官方源码；提供只读 Ubuntu 主机预检（SB-CUBE-001、008）。
- [ ] T1b — 在目标 Ubuntu 记录 CPU/KVM、XFS/reflink、可用资源、镜像拉取及 digest（SB-CUBE-001、008）。
- [x] T2a — 实现 Cube Compose、独立数据库初始化、共享制品、节点组件、代理和有限生命周期服务；
  通过基础/生产 Compose 配置校验（SB-CUBE-001、002、007）。
- [ ] T2b — 目标机器启动全部组件并构建 READY 模板（SB-CUBE-001、002、008）。
- [x] T3 — 实现 metadata 发现、Redis 并发创建锁、SDK backend、引用释放与字节传输，
  添加并通过定向单测（SB-CUBE-003、004、006、007）。
- [x] T4a — 切换 middleware/Composite/工作区服务，统一目录与配置，移除旧供应服务与依赖；
  更新架构、ADR 和部署说明（SB-CUBE-004、005、006）。
- [ ] T4b — 执行真实跨进程并发/重连和文件往返 smoke；完成 Worker Run 到 UI 工作区联调
  （SB-CUBE-004、005、006、008）。
- [ ] T5 — 验证 TTL、主机/组件重启、并行 Run 和 VM 私网隔离，记录资源占用并归档计划
  （SB-CUBE-001 至 008）。
