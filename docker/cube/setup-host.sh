#!/usr/bin/env bash
# 安装官方 Cube v0.7.3 节点，由 systemd 管理。
set -euo pipefail
[[ $EUID == 0 ]] || { echo '请使用 sudo bash docker/cube/setup-host.sh' >&2; exit 1; }
[[ $(uname -m) == x86_64 && -c /dev/kvm ]] || { echo '需要 Linux amd64 和 /dev/kvm' >&2; exit 1; }
for command in curl tar openssl mkfs.xfs findmnt fallocate blkid ip; do
    command -v "$command" >/dev/null
done

install_dir=/opt/agent-stack-cube
storage_file=/var/lib/agent-stack/cubelet.xfs
mkdir -p "$install_dir" /var/lib/agent-stack /data/cubelet

# 仅格式化本脚本新建的普通文件，不格式化主机分区或已有文件。
if [[ $(findmnt -n -o FSTYPE -T /data/cubelet) != xfs ]]; then
    if mountpoint -q /data/cubelet || [[ -n $(ls -A /data/cubelet) ]]; then
        echo '/data/cubelet 已被使用，请先检查其挂载和内容' >&2
        exit 1
    fi
    if awk '$2 == "/data/cubelet" { found=1 } END { exit !found }' /etc/fstab &&
       ! grep -Fxq "$storage_file /data/cubelet xfs loop,defaults 0 0" /etc/fstab; then
        echo '/etc/fstab 已配置其他 Cube 数据挂载，请先检查' >&2
        exit 1
    fi
    if [[ ! -e $storage_file ]]; then
        # 本机空闲约 39 GiB；分配 16 GiB，剩余空间用于镜像和控制服务。
        fallocate -l 16G "$storage_file"
        mkfs.xfs -m reflink=1 "$storage_file"
    fi
    [[ $(blkid -p -s TYPE -o value "$storage_file") == xfs ]]
    mount -o loop "$storage_file" /data/cubelet
    if ! awk '$2 == "/data/cubelet" { found=1 } END { exit !found }' /etc/fstab; then
        printf '%s\n' "$storage_file /data/cubelet xfs loop,defaults 0 0" >> /etc/fstab
    fi
    systemctl daemon-reload
fi

node_iface=$(ip -4 route show table main default | awk '{for(i=1;i<=NF;i++) if($i=="dev") {print $(i+1); exit}}')
node_ip=${CUBE_NODE_IP:-$(ip -4 -o addr show dev "$node_iface" scope global | awk 'NR==1 {split($4,a,"/"); print a[1]}')}
[[ -n $node_ip ]]
config_file="$install_dir/node.env"
if [[ ! -f $config_file ]]; then
    previous_umask=$(umask)
    umask 077
    cat > "$config_file" <<CONFIG
CUBE_SANDBOX_NODE_IP=$node_ip
CUBE_SANDBOX_REDIS_PORT=16379
CUBE_SANDBOX_MYSQL_PORT=13306
CUBE_SANDBOX_MINIO_API_PORT=19000
CUBE_SANDBOX_MINIO_CONSOLE_PORT=19001
CUBE_SANDBOX_REDIS_PASSWORD=$(openssl rand -hex 24)
CUBE_SANDBOX_MYSQL_ROOT_PASSWORD=$(openssl rand -hex 24)
CUBE_SANDBOX_MYSQL_PASSWORD=$(openssl rand -hex 24)
CUBE_SANDBOX_MINIO_ROOT_PASSWORD=$(openssl rand -hex 24)
CONFIG
    umask "$previous_umask"
fi

# 显式节点地址覆盖先前因代理 TUN 自动探测产生的地址。
sed -i "s/^CUBE_SANDBOX_NODE_IP=.*/CUBE_SANDBOX_NODE_IP=$node_ip/" "$config_file"
if ! grep -q '^CUBE_EGRESS_ADMIN_PORT=' "$config_file"; then
    printf '\nCUBE_EGRESS_ADMIN_PORT=19091\n' >> "$config_file"
fi

# 兼容首次安装失败后已生成的 node.env，保留已有凭据及显式网段。
if ! grep -q '^CUBE_SANDBOX_NETWORK_CIDR=' "$config_file"; then
    printf '\nCUBE_SANDBOX_NETWORK_CIDR=10.100.0.0/18\n' >> "$config_file"
fi

bundle="$install_dir/cube-sandbox-one-click-v0.7.3-amd64.tar.gz"
if [[ ! -f $bundle ]]; then
    curl --fail --location --retry 3 \
        https://github.com/TencentCloud/CubeSandbox/releases/download/v0.7.3/cube-sandbox-one-click-v0.7.3-amd64.tar.gz \
        -o "$bundle.download"
    mv "$bundle.download" "$bundle"
fi
mkdir -p "$install_dir/release"
tar -xzf "$bundle" -C "$install_dir/release"
installer=$(find "$install_dir/release" -name install.sh -print -quit)
[[ -n $installer ]]
ONE_CLICK_ENV_FILE="$config_file" MIRROR=cn bash "$installer" --yes --node-ip "$node_ip"
systemctl is-enabled cube-sandbox-control.target
systemctl is-active cube-sandbox-control.target
mkdir -p /data/shared/agent-stack/workspaces /data/shared/agent-stack/skills
# 本机非 root API/Worker 需要穿过父目录；目录内容仍由各子目录权限保护。
chmod a+x /data /data/shared
chown "${SUDO_UID:-0}:${SUDO_GID:-0}" /data/shared/agent-stack \
    /data/shared/agent-stack/workspaces /data/shared/agent-stack/skills
printf '\nCube 节点已安装；下一步构建模板、配置应用并运行 smoke。节点地址：%s\n' "$node_ip"
