## 安装

在项目根目录运行：

```bash
sudo bash docker/cube/setup-host.sh
```

脚本在 ext4 主机上新建 16 GiB XFS 文件系统文件
`/var/lib/agent-stack/cubelet.xfs`，挂载到 `/data/cubelet` 并写入 fstab；不格式化分区。
已挂载的 XFS 直接复用。安装包保存到 `/opt/agent-stack-cube`，独立凭据保存到该目录
仅 root 可读的 `node.env`。如需指定实际物理网卡地址，使用
`sudo env CUBE_NODE_IP=<主机IPv4> bash docker/cube/setup-host.sh`。

Cube 独立 Redis/MySQL/MinIO 分别使用 16379、13306、19000/19001，避开本项目依赖服务。
CubeEgress 管理端口使用 19091，避开 Milvus 的 9091。节点 IP 从主路由表的默认网卡选取，
避免代理 TUN 策略路由将 `198.18.*` 地址写入节点配置；重跑时同步更新已有配置的节点 IP。
VM 网段使用 `10.100.0.0/18`，避开本机 `192.168.0.0/24` 局域网和 Docker 网段。
脚本会向已有 `node.env` 补写缺失的 `CUBE_SANDBOX_NETWORK_CIDR`，不覆盖已有显式配置；
官方安装器仍执行网段冲突检查。其他主机可在 `node.env` 中设置符合其网络布局的网段。
官方安装器配置 Cube 网络、DNS、组件和 systemd 自启。旧开发 VM 不参与启动，磁盘不会自动删除。

## 本机源码 API/Worker 接入

安装成功后，在未提交的 `.env` 中设置以下值；`<主机IPv4>` 使用安装脚本打印的地址。
切换前先停止正在运行的 API/Worker：

```dotenv
CUBE_API_URL=http://127.0.0.1:3000
CUBE_MASTER_URL=http://127.0.0.1:8089
CUBE_NODE_ID=<主机IPv4>
CUBE_NODE_IP=<主机IPv4>
CUBE_PROXY_NODE_IP=127.0.0.1
CUBE_PROXY_PORT_HTTP=80
CUBE_HOST_SAVE_DIR=/data/shared/agent-stack
SAVE_DIR=/data/shared/agent-stack
```

先确认 Cube inventory 中注册的节点 ID 与 `CUBE_NODE_ID` 一致。新环境需要重新构建模板，
不能复用旧开发 VM 的 template ID：

```bash
docker pull cube-sandbox-cn.tencentcloudcr.com/cube-sandbox/sandbox-code:latest
docker image inspect --format '{{index .RepoDigests 0}}' cube-sandbox-cn.tencentcloudcr.com/cube-sandbox/sandbox-code:latest
PYTHONPATH=. uv run --no-sync python docker/cube/manage.py template --image '<上一步镜像digest>'
```

把输出的 `CUBE_TEMPLATE_ID` 写入 `.env`，然后验证：

```bash
PYTHONPATH=. uv run --no-sync python docker/cube/manage.py smoke
systemctl is-enabled cube-sandbox-control.target
systemctl is-active cube-sandbox-control.target
```

API/Worker 从本机源码启动。根 Compose 中原来的 `cube-*` 服务不能与官方节点同时启动；
需要基础设施时显式选择 postgres、redis、rustfs、milvus、neo4j。
容器 API/Worker 仍使用旧 Compose 内部 Cube 地址，尚未迁移到该外部节点。

## 验收状态

本机已安装官方节点，控制 target 已启用开机自启；API health 和节点
`192.168.0.102` inventory 检查通过。模板 `tpl-d313f983f91d4af6920a4c5b` 已构建为 READY，
镜像为 `cube-sandbox-cn.tencentcloudcr.com/cube-sandbox/sandbox-code@sha256:743d264fad8c9dc9a49f07e931166d24d025363360ae770ca4b70e3f19540944`。
本机 `.env` 已指向该节点、模板和共享目录。

2026-11-07 已修复共享目录访问权限，并通过真实 `manage.py smoke`：跨进程并发复用、
命令执行与非零退出码、命令超时、大二进制上传下载、宿主共享文件回读、文件编辑与列举、
销毁重建后文件保留。测试沙箱已清理，inventory 返回空列表。
控制 target 为 enabled/active，systemd 无失败单元。主机重启恢复及真实 Agent Run/UI
联调尚未验收。

### 用户共享沙箱

同一用户的所有聊天复用一个 VM，`/workspace` 对应
`CUBE_HOST_SAVE_DIR/workspaces/<uid>`。旧会话文件保留在 `/workspace/<thread_id>`。
空闲到期由 Cube 暂停，下一次工具调用恢复原 VM；显式销毁保留共享文件，但会清除 VM 内安装的依赖。
更新后重启源码 API/Worker，使进程使用用户级发现逻辑；旧会话实例不再复用，按原生命周期回收。

2026-11-07 用户级真实 smoke 通过：跨聊天/进程并发复用、空闲到期暂停、跨进程恢复原 ID、
VM `/tmp` 文件和共享文件保留、销毁重建后共享文件保留。专用测试实例已销毁。
