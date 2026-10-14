"""Idempotent Cube database, config and certificate preparation (no host disk setup)."""

import ipaddress
import json
import os
import re
import subprocess
from pathlib import Path


def write_json(path: Path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def main():
    node_ip = ipaddress.ip_address(os.environ["CUBE_NODE_IP"])
    if node_ip.version != 4 or node_ip.is_loopback or node_ip.is_unspecified:
        raise ValueError("CUBE_NODE_IP must be this host's reachable IPv4 address")
    password = os.environ["CUBE_DB_PASSWORD"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", password):
        raise ValueError("Use 16-128 URL-safe characters for CUBE_DB_PASSWORD (e.g. openssl rand -hex 24)")
    sql_password = password.replace("'", "''")
    subprocess.run(
        ["psql", "-X", "-v", "ON_ERROR_STOP=1", "-d", "postgres"],
        input=(
            "SELECT 'CREATE ROLE cube LOGIN' WHERE NOT EXISTS "
            "(SELECT FROM pg_roles WHERE rolname='cube')\\gexec\n"
            f"ALTER ROLE cube PASSWORD '{sql_password}';\n"
            "SELECT 'CREATE DATABASE cube OWNER cube' WHERE NOT EXISTS "
            "(SELECT FROM pg_database WHERE datname='cube')\\gexec\n"
        ),
        text=True,
        check=True,
    )
    config_dir, cert_dir = Path("/config"), Path("/certs")
    config_dir.mkdir(exist_ok=True)
    cert_dir.mkdir(exist_ok=True)
    database = dict(driver="postgres", addr="postgres:5432", user="cube", pwd=password, db_name="cube", conn_timeout=5, read_timeout=5, write_timeout=5, max_idle_conns=5, max_open_conns=20, max_conn_life_time_seconds=300)
    redis = dict(nodes="redis:6379", password="", db_no=1, max_idle=8, max_active=32, idle_timeout=30, max_retry=2)
    common = dict(http_readtimeout=120, http_writetimeout=360, http_idletimeout=360, sync_meta_data_interval="1s", sync_metric_data_interval="1s", collect_metric_interval="1s")
    log = dict(file_size=100, file_num=10, level="info")
    request = {
        "volumes": [{"name": "tmp", "volume_source": {"empty_dir": {"medium": 0}}}],
        "containers": [{"name": "cubebox-default", "volume_mounts": [{"name": "tmp", "container_path": "/"}], "security_context": {"privileged": True, "readonly_rootfs": False, "no_new_privs": False}}],
        "network_type": "tap",
        "cube_network_config": {
            "allowInternetAccess": True,
            "denyOut": [
                "10.0.0.0/8",
                "100.64.0.0/10",
                "172.16.0.0/12",
                "192.168.0.0/16",
                "169.254.0.0/16",
                f"{node_ip}/32",
            ],
        },
    }
    master = {
        "common": {**common, "http_port": 8089, "cube_ops_addr": "http://cube-ops:3010", "template_center_addr": "http://cube-templatecenter:8090", "default_headless_service_nodes_num": 1, "enable_check_com_net_id_param": False},
        "log": {**log, "module": "cubemaster", "path": "/data/log/CubeMaster"},
        "instance_db_config": database,
        "redis": redis,
        "auth": {"enable": False},
        "cube_proxy_conf": {"admin_token": os.environ["CUBE_ADMIN_TOKEN"]},
        "extra_conf": {"allowed_host_mount_prefixes": [os.environ["CUBE_HOST_SAVE_DIR"]]},
        "cubelet_conf": {
            "grpc": {"grpc_port": 9999},
            "common_timeout_insec": 30,
            "create_image_timeout_insec": 300,
            "app_snapshot_timeout_insec": 300,
            "create_timeout_insec": 600,
            "create_concurrent_limit": 4,
            "destroy_concurent_limit": 4,
            "enable_exposed_port": True,
            "exposed_port_list": ["80"],
            "disable_redis_proxy_port": True,
        },
        "req_template_conf": {"whitelist_req_tag": {name: True for name in ("WorkingDir", "RLimit", "DnsConfig", "HostAliases", "Poststop", "Prestop")}, "cube_box_req_template": json.dumps(request)},
        "scheduler": {"priority_select_num": 1, "metric_update_timeout": "300s", "local_metric_update_timeout": "300s", "filter": {"enable_filters": ["cpu", "mem", "template_locality", "realtime_create_num"]}},
    }
    templatecenter = {
        "common": {**common, "http_port": 8090, "master_addr": "http://cube-master:8089"},
        "log": {**log, "module": "templatecenter", "path": "/data/log/CubeTemplateCenter"},
        "instance_db_config": database,
        "redis": redis,
        "redis_read": redis,
        "redis_write": redis,
        "auth": {"enable": False},
    }
    write_json(config_dir / "master.yaml", master)
    write_json(config_dir / "templatecenter.yaml", templatecenter)
    ca, key = cert_dir / "cube-root-ca.crt", cert_dir / "cube-root-ca.key"
    if ca.exists() != key.exists():
        raise RuntimeError("Incomplete Cube CA; restore the missing certificate/key")
    if not ca.exists():
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:3072", "-nodes", "-keyout", str(key), "-out", str(ca), "-days", "3650", "-subj", "/CN=Agent Stack Cube CA", "-addext", "basicConstraints=critical,CA:TRUE"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    # Egress worker uid/gid 8049 reads the CA for TLS interception.
    os.chown(key, 0, 8049)
    key.chmod(0o640)
    for name in ("placeholder", "cube.app+3"):
        cert = cert_dir / f"{name}.crt"
        leaf_key = cert_dir / f"{name}.key"
        if cert.exists() != leaf_key.exists():
            raise RuntimeError(f"Incomplete Cube certificate: {name}")
        if not cert.exists():
            csr = cert_dir / f"{name}.csr"
            subject = "/CN=" + name.replace("+", r"\+")
            subprocess.run(["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", str(leaf_key), "-out", str(csr), "-subj", subject], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["openssl", "x509", "-req", "-in", str(csr), "-CA", str(ca), "-CAkey", str(key), "-CAcreateserial", "-out", str(cert), "-days", "3650"], check=True, stdout=subprocess.DEVNULL)
            leaf_key.chmod(0o600)
            csr.unlink()
    (cert_dir / "cube.app+3.pem").write_bytes((cert_dir / "cube.app+3.crt").read_bytes())
    proxy_key = cert_dir / "cube.app+3-key.pem"
    proxy_key.write_bytes((cert_dir / "cube.app+3.key").read_bytes())
    proxy_key.chmod(0o600)
    print("Cube database, configuration and certificates are ready")


if __name__ == "__main__":
    main()
