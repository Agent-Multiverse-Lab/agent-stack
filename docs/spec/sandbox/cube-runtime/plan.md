# CubeSandbox 单机 Compose 集成计划
计划版本：v0.1.0

状态：应用代码与部署配置已实现，目标 Ubuntu 的运行验收待执行。未完成部署验收前保留当前计划。

## 1. 范围与基线

关联需求：SB-CUBE-001 至 SB-CUBE-008，见 [spec.md](spec.md)。

- 同机 Ubuntu、Compose、32GB 内存、200GB SSD；CPU/KVM、文件系统和剩余资源由主机预检确认。
- 固定组件镜像 v0.7.2、PyPI cubesandbox==0.7.0；对应核对源码提交
  2bbaf74ba7565992ec2a3dbc9928ed5b720639a2。镜像 digest 和 Linux 运行情况需在目标机器记录。
- 保留现有 BackendProtocol、middleware、Composite 与工作区 API；移除 sandbox_server、
  provision_client 和 agent-sandbox/docker Python 依赖。
- 业务数据库不新增 cube_sandbox_id 或沙盒表。Cube 自己使用现有 PostgreSQL 中的独立 cube
  数据库和角色、Redis DB 1、独立配置/证书/模板目录；业务文件继续使用 RustFS。
- 简化审查保留 metadata 发现、一个 Redis 创建锁、官方 SDK 和 BaseSandbox；不引入业务
  resolver、Repository 绑定、数据库迁移、通用 provider 工厂或旧实现回退。

## 2. 部署实现

落点：根 docker-compose.yml、docker-compose.prod.yml 与 docker/cube/。

cube-prepare 使用幂等 SQL 补建 Cube 库/角色，生成 Master/TemplateCenter 配置及可复用证书。
Master/Ops/TemplateCenter/API/Proxy/生命周期管理器采用 bridge 网络。Cubelet 和出站网络组件
使用 host network；宿主机控制端口绑定 loopback，节点容器通过 extra_hosts 访问 Master/Ops。
四个官方 install 容器以 staged 标记健康；node-init 成功退出后开始安装和运行。

node-init 使用已有 KVM，禁用 loopback 格式化、内核安装、设备 chmod 和 udev 写入。读写工作
目录和节点状态通过明确绑定目录提供。prepare 不操作主机磁盘或内核。Cubelet 的命令入口、组件
路径和网络配置依据官方 chart，未自建 Hypervisor。

docker/cube/manage.py::build_template 显式提交代码镜像构建任务并等待 READY；smoke 验证应用
适配器。部署参数、目录、凭据与命令以 [部署指南](../../../../docker/cube/README.md) 为准。

## 3. 实例发现与并发

落点：src/agents/backends/sandbox/provider_service.py::SandboxProviderService.acquire。

以 app/uid/thread_id metadata 查找实例。通过标准 Redis Lock 将同会话的查询、connect 和创建
串行化；进程锁协调本地引用。同一查询出现重复实例立即报错。通过 CubeMaster 的
`/cube/sandbox/inventory?host_id=<CUBE_NODE_ID>` 严格查询本机节点；仅在 ret_code=0、
size=1 且 data 为数组时接受结果。普通 CubeAPI 列表会忽略节点连接失败，不用于发现。

控制流示例（acquire 的实际语义）：

    with scope_lock, redis_creation_lock as lease:
        existing = client.find(identity)
        data = client.connect(existing_id, idle_timeout) if existing else None
        if data is None:
            require_lease_owned()
            data = client.create(metadata, idle_timeout)
        require_lease_owned()
        return retain_local_client(data)

connect 只有 404 返回 None；401/403/超时/5xx 直接失败。未知创建结果不自动重试，下一次按
metadata 重新发现。Redis 不存实例 ID；锁租约失效时不发布本地成功结果。

落点：cube_client.py::CubeClient。官方 SDK 的 create/connect 未传 HTTP 请求超时，且 list
不提供完整的发现约束，所以管理面保留有超时的薄 httpx 客户端；命令和上传使用 SDK 公共接口。

## 4. 工具、文件与引用

落点：sandbox_backend.py::CubeSandboxBackend、sandbox_middleware.py::SandboxMiddleware。

命令通过 VM 中 GNU timeout 设置进程组终止上限，SDK 超时略长；保持真实退出码和 stdout/stderr。
Backend 输出不截断，以保证 BaseSandbox 的文件 JSON 可解析；只有 execute 工具消息在
middleware 截断。字节下载按 64KiB 分块，并检查文件签名及块长度，不返回截断的文件。

middleware 的每次工具调用 acquire，finally release；async acquire 等待者取消后，后台线程
取得的引用通过 done callback 归还。backend 操作 borrow 引用，最后一个使用者完成才 close SDK。
这些 close 均不 delete VM。Run 取消不杀共享实例，已开始的远端命令仍受自身期限约束。

落点：provider_service.py::workspace_paths 与 composite_backend.py::create_composite_backend。
本地 SAVE_DIR/workspaces/<uid>/<thread_id> 和 Cube host-mount 的 /workspace 指向同一宿主目录，
/skill 只读。校验标识符、路径归属和符号链接。CubeAPI 会将 host-mount 从 metadata 移入
annotations，列表不返回原始挂载；因此 metadata 同时记录 mounts_sha256，复用前对照配置摘要，
挂载配置变更时拒绝悄悄复用不同挂载的 VM。

落点：server/service/sandbox_service.py。保留归属校验、前端响应和预览限制；路径统一为
/workspace，删除旧 /home/gem 路径转换。工作区调用结束同样归还连接引用。

## 5. 验证与完成边界

- 应用：供应服务、中间件、Composite、工作区与 SDK 适配测试；并发、重启发现、错误分类、
  引用、取消、上传下载完整性和命令不重放均有定向检查。
- 静态：ruff、Python 编译、git diff --check。
- 配置：使用官方 Compose v2.39.4 独立程序验证基础/生产配置；测试凭据覆盖 env_file，不操作容器。
- Linux：执行 preflight、镜像拉取与 digest 记录、模板 READY、manage.py smoke，再完成 Worker
  Run → 前端工作区、TTL 回收、组件重启和 VM 私网隔离。此部分本机尚未执行。

本轮不把静态配置和 SDK 单测作为真实 VM 部署成功的证据。T5 完成前不归档当前计划。

## 6. 上游依据

- [官方 chart](https://github.com/TencentCloud/CubeSandbox/tree/2bbaf74ba7565992ec2a3dbc9928ed5b720639a2/deploy/kubernetes/chart)
- [组件入口](https://github.com/TencentCloud/CubeSandbox/blob/2bbaf74ba7565992ec2a3dbc9928ed5b720639a2/deploy/kubernetes/images/scripts/component-entrypoint.sh)
- [Host Mount](https://docs.cubesandbox.com/zh/guide/persistent-storage)
