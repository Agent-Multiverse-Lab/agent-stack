# CubeSandbox 单机部署

应用已改为 CubeSandbox SDK；`docker-compose.yml` 是统一部署入口。组件固定为 `v0.7.2`，
Python SDK 固定为 `0.7.0`。这些配置依据官方源码提交
`2bbaf74ba7565992ec2a3dbc9928ed5b720639a2`；仍需在目标 Ubuntu 上验收镜像与运行行为。

## 1. 主机与配置

需要 Linux amd64、Docker Engine、Compose 2.24.4+、可访问的 `/dev/kvm`、cgroup v2，
以及位于 XFS（`reflink=1`）上的 `/data/cubelet`。32GB 内存和 200GB SSD 本身不能证明这些
条件满足。请为应用、数据库、Milvus 和镜像构建保留空间；首轮可将 `ARQ_MAX_JOBS` 设为 4。

首次准备 `/data/cubelet` 的文件系统需要按实际磁盘布局单独操作。本仓库不会格式化磁盘、
安装 PVM 内核或重启宿主机。预检只读：

```bash
sudo env CUBE_NODE_IP=192.168.1.20 bash docker/cube/preflight.sh
```

从 `.env.template` 准备 `.env`，至少填写：

| 配置 | 含义 |
| --- | --- |
| `CUBE_NODE_IP` | 宿主机真实 IPv4，控制容器必须能够回连此 IP 的 9999 端口 |
| `CUBE_SANDBOX_ETH_NAME` | 可选；显式指定宿主机上联网卡，有代理/TUN 时填写实际网卡名 |
| `CUBE_DB_PASSWORD` | Cube 独立数据库密码，16–128 个 URL 安全字符 |
| `CUBE_ADMIN_TOKEN` | Master/Proxy/生命周期管理器共用的管理 token |
| `CUBE_TEMPLATE_CALLBACK_TOKEN` | Master 与 TemplateCenter 的回调 token |
| `CUBE_HOST_SAVE_DIR` | 默认 `/data/shared/agent-stack`，宿主机共享目录 |
| `CUBE_TEMPLATE_ID` | 模板构建完成后填写 |

三个密码/token 分别使用 `openssl rand -hex 24` 生成。国内可设置
`CUBE_REGISTRY=cube-sandbox-cn.tencentcloudcr.com/cube-sandbox`。
既有业务数据库无需 Alembic 迁移；`cube-prepare` 在现有 PostgreSQL 中补建独立的 `cube` 库和
角色，Cube 组件自行迁移自己的表。不要将 `cube` 数据库给其他应用共用。

VM 网络固定使用 `172.16.0.0/16`；它不能与主机已有路由冲突。官方 node-init 会进一步检查
CPU/cgroup、BPF、网络、CubeCOW 依赖和端口，并以错误退出阻止后续启动。

代理 TUN 改变策略路由时，Cubelet 的 `ip route get 1.1.1.1` 自动检测可能选中虚拟网卡，
导致 `default gateway not found`。可保持 TUN 开启，用 `ip -4 route show default` 和
`ip -4 -br addr` 确认实际网卡与地址，然后在 `.env` 同时填写 `CUBE_NODE_IP` 和
`CUBE_SANDBOX_ETH_NAME`（例如 `192.168.0.108`、`eno1`）。显式网卡优先于自动检测。
修改节点地址后，执行 `docker compose run --rm cube-prepare` 重新生成配置，再重新创建
Cube 服务容器使配置生效。指定网卡只解决节点网络初始化，不保证 VM 的出站流量经过代理；
真实 VM 的联网和隔离仍需按下文完成 smoke 验证。

## 2. 启动控制服务与计算节点

```bash
docker compose config -q
docker compose build api
docker compose up -d --build cube-api cube-templatecenter cube-proxy cube-egress-net
docker compose ps -a
```

依赖顺序为数据库准备 → Master/Ops → 节点检查 → 四个组件安装容器 → Cubelet → 出站代理。
安装容器成功后保持运行，通过 `.staged-*` 标记判断就绪。生命周期管理器负责有限空闲 TTL。
TemplateCenter 需要权限构建 ext4；计算节点需要 host network、host PID、设备和 mount propagation。
API/Worker 不挂载 Docker Socket。

首次成功后可以重复 `up`。`down` 不会删除绑定目录；停止 Cubelet 不能当成“已销毁全部 VM”，
维护时先停止提交新任务并显式清理实例。不要通过删除宿主机目录来清理正在运行的 VM。

## 3. 构建代码模板

使用包含 envd、Python 3、bash 和 GNU coreutils `timeout` 的 Cube `sandbox-code` 镜像。
先拉取并记录 digest，再将下面的镜像参数换成该 digest；需要 GIS 包时使用基于它构建的项目镜像。

```bash
docker pull cube-sandbox-cn.tencentcloudcr.com/cube-sandbox/sandbox-code:latest
docker image inspect --format '{{index .RepoDigests 0}}' \
  cube-sandbox-cn.tencentcloudcr.com/cube-sandbox/sandbox-code:latest

docker compose run --rm --no-deps -e PYTHONPATH=/app \
  -v "$PWD/docker/cube:/cube:ro" api \
  uv run --no-sync python /cube/manage.py template \
  --image 'cube-sandbox-cn.tencentcloudcr.com/cube-sandbox/sandbox-code@sha256:替换为实际摘要'
```

脚本等待 READY 并输出 `CUBE_TEMPLATE_ID=tpl-...`，写入 `.env` 后继续。模板默认为 1 vCPU、
1024MiB、1GiB 可写层，开放 envd/探测端口，并禁止访问私网、链路本地地址和宿主机地址。

```bash
docker compose run --rm --no-deps -e PYTHONPATH=/app \
  -v "$PWD/docker/cube:/cube:ro" api uv run --no-sync python /cube/manage.py smoke
docker compose up -d --build
```

smoke 检查跨进程并发创建/复用、命令退出码和超时、大二进制往返、共享目录、文件协议和销毁后
文件保留。测试实例最后被删除，测试工作目录保留并打印路径。还需在真实 Worker Run 中确认前端
工作区访问，等待 TTL 验证自动回收，并检查 VM 无法访问 PostgreSQL/Redis/Cube 管理端口。

## 4. 地址、目录与生命周期

| 调用方 | 管理地址 | 节点查询地址 | 命令/文件入口 |
| --- | --- | --- | --- |
| Compose API/Worker | `http://cube-api:3000` | `http://cube-master:8089` | `cube-proxy:80` |
| 同机源码进程 | `http://localhost:3000` | `http://localhost:8089` | `localhost:8081` |
| 浏览器 | 项目 API | 项目 API | 项目工作区接口 |

同机源码进程需令 `SAVE_DIR` 与 `CUBE_HOST_SAVE_DIR` 指向同一目录。容器内配置由 Compose 覆盖，
`SAVE_DIR=/app/save`；只挂载 `workspaces` 和只读 `skills` 子目录。

- 工作文件：`${CUBE_HOST_SAVE_DIR}/workspaces/<uid>/<thread_id>` ↔ VM `/workspace`。
- 技能文件：`${CUBE_HOST_SAVE_DIR}/skills` ↔ VM 只读 `/skill`。
- Cube 配置/证书/模板制品：`/data/cube-stack/`；节点状态和磁盘：`/data/cubelet` 等官方路径。
- Cube Redis 使用 DB 1；应用创建锁使用现有应用 Redis DB 0。
- `release` 只归还本地连接引用；`destroy` 或空闲到期才删除 VM，宿主机工作文件保留。

实例通过 `app=agent-stack, uid, thread_id` metadata 发现，业务库不保存 `cube_sandbox_id`。
`CUBE_NODE_ID` 默认 `agent-stack-node`，必须与同机 Cubelet 一致；更换该值前先清理原节点实例。
发现通过 CubeMaster 的严格单节点 inventory 完成，节点未注册/不可达或响应不完整均拒绝创建。
发现重复实例或挂载摘要不一致时同样拒绝自动创建；先诊断并明确清理。
网络错误和 5xx 不触发重建；命令发出后不自动重放。

控制端口 3000/3010/8089 和代理 8081 仅绑定宿主机 loopback。内部控制接口按可信部署使用，
填写 `CUBE_API_KEY` 不会自动开启 CubeAPI 鉴权。公开入口仍是应用 API。
生产环境使用仓库的 `.env.prod` 和 `docker-compose.prod.yml`，上述命令相应加上
`--env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml`。

## 5. 验证记录与来源

2026-10-12 本机验证：六组应用定向测试通过 56 项及 10 项子测试；最后的中间件连接释放与
工作区时间映射调整另行复测 13 项通过（包含新增用例）。ruff、14 个 Python 源文件的内存编译、
Bash 语法检查、git diff --check、Compose 基础/生产配置展开均通过。字节码写入受本机目录
权限影响，因此编译检查不写入 __pycache__。生产展开使用临时测试凭据覆盖 env_file，
没有读取或创建生产凭据。尚未执行目标 Ubuntu 的镜像拉取、VM/模板构建、TTL、网络隔离和 UI 联调。

`proxy-entrypoint.sh` 来自该提交的官方 chart，保留上游入口行为。
[官方镜像与入口](https://github.com/TencentCloud/CubeSandbox/tree/2bbaf74ba7565992ec2a3dbc9928ed5b720639a2/deploy/kubernetes)、
[Host Mount 文档](https://docs.cubesandbox.com/zh/guide/persistent-storage)。
