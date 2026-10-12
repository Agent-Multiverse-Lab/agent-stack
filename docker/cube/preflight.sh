#!/usr/bin/env bash
set -euo pipefail
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ "$(uname -s)" == Linux ]] || fail 'Cube compute needs Linux'
[[ "$(uname -m)" == x86_64 ]] || fail 'This deployment is validated against amd64 images'
for tool in docker findmnt xfs_info ip ss; do command -v "$tool" >/dev/null || fail "Missing command: $tool"; done
docker compose version
[[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]] || fail '/dev/kvm must exist and be accessible (check hardware/nested virtualization)'
[[ "$(findmnt -n -o FSTYPE -T /data/cubelet)" == xfs ]] || fail '/data/cubelet must already be on XFS'
xfs_info /data/cubelet | grep -q 'reflink=1' || fail 'XFS reflink=1 is required'
[[ -f /sys/fs/cgroup/cgroup.controllers ]] || fail 'cgroup v2 is required'
[[ -n "${CUBE_NODE_IP:-}" ]] || fail 'Export CUBE_NODE_IP with the host IPv4 address'
ip -4 -o addr show | grep -Fq " ${CUBE_NODE_IP}/" || fail 'CUBE_NODE_IP does not belong to this host'
printf '\nMemory and disk capacity (retain headroom for PostgreSQL/Milvus/application):\n'
free -h
df -h /data/cubelet /data/shared
printf '\nPorts to check for unrelated listeners: 3000 3010 8081 8089 9998 9999 9966 19091\n'
ss -lntup
printf '\nHost checks passed. No filesystems or kernel settings were changed.\n'
