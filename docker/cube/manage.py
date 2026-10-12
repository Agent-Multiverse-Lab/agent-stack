"""Explicit template creation and Linux smoke checks; run from the application image."""

import argparse
import hashlib
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx

from src.agents.backends.sandbox.provider_service import SandboxProviderService, workspace_paths
from src.configs import config


def build_template(image):
    headers = {"X-API-Key": config.cube_api_key} if config.cube_api_key else {}
    node_ip = os.environ["CUBE_NODE_IP"]
    with httpx.Client(base_url=config.cube_api_url, headers=headers, timeout=330) as client:
        response = client.post(
            "/templates",
            json={
                "image": image,
                "name": "agent-stack-code",
                "cpu": 1000,
                "memory": 1024,
                "writableLayerSize": "1G",
                "exposedPorts": [49983, 49999],
                "probePort": 49999,
                "networkType": "tap",
                "allowInternetAccess": True,
                "denyOut": ["10.0.0.0/8", "100.64.0.0/10", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", f"{node_ip}/32"],
            },
        )
        response.raise_for_status()
        job = response.json()
        template_id, job_id = job["templateID"], job["jobID"]
        print(f"Template {template_id}, build {job_id}", flush=True)
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            response = client.get(f"/templates/{template_id}/builds/{job_id}/status")
            response.raise_for_status()
            status = response.json()
            print(status.get("status"), status.get("phase"), flush=True)
            if status.get("status", "").upper() == "READY":
                print(f"CUBE_TEMPLATE_ID={template_id}")
                return
            if status.get("status", "").upper() == "FAILED":
                raise RuntimeError(status.get("errorMessage") or status.get("message") or "Template build failed")
            time.sleep(5)
        raise TimeoutError(f"Template {template_id} is still building; inspect Cube logs before retrying")


def acquire_in_process(uid, thread):
    provider = SandboxProviderService()
    try:
        sid = provider.acquire(uid, thread)
        provider.release(sid)
        print(sid)
    finally:
        provider.shutdown()


def smoke():
    uid, thread = "cube-smoke", uuid4().hex
    provider = SandboxProviderService()
    sid = None
    try:
        # Independent Python processes exercise the actual Redis creation lock.
        def acquire(_):
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "acquire", uid, thread], check=True, text=True, capture_output=True, timeout=1000)
            return result.stdout.strip().splitlines()[-1]

        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(acquire, range(2)))
        if ids[0] != ids[1]:
            raise RuntimeError(f"Duplicate instances: {ids}")
        sid = provider.acquire(uid, thread)
        assert sid == ids[0]
        backend = provider.get(sid)
        result = backend.execute("command -v python3; command -v timeout; printf cube-ready")
        assert result.exit_code == 0 and "cube-ready" in result.output, result.output
        failed = backend.execute("printf problem >&2; exit 7")
        assert failed.exit_code == 7 and "problem" in failed.output
        timeout = backend.execute("sleep 5", timeout=1)
        assert timeout.exit_code == 124, timeout.output
        content = bytes(range(256)) * 5000
        remote = "/workspace/outputs/smoke.bin"
        assert backend.upload_files([(remote, content)])[0].error is None
        downloaded = backend.download_files([remote])[0]
        assert downloaded.error is None
        assert hashlib.sha256(downloaded.content).digest() == hashlib.sha256(content).digest()
        workspace, _ = workspace_paths(uid, thread)
        assert (workspace / "outputs/smoke.bin").read_bytes() == content
        assert backend.write("/workspace/check.txt", "first\n").error is None
        assert backend.edit("/workspace/check.txt", "first", "second").error is None
        assert "second" in backend.read("/workspace/check.txt").file_data["content"]
        assert backend.ls("/workspace").error is None
        provider.release(sid)
        provider.destroy(sid)
        sid = provider.acquire(uid, thread)
        assert sid != ids[0]
        assert provider.get(sid).download_files([remote])[0].content == content
        provider.release(sid)
        print("PASS: cross-process reuse/concurrency, execute/timeout, binary files, shared paths, recreate")
        print(f"Retained smoke files: {workspace}")
    finally:
        if sid:
            provider.release(sid)
            provider.destroy(sid)
        provider.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("template").add_argument("--image", required=True)
    commands.add_parser("smoke")
    child = commands.add_parser("acquire", help=argparse.SUPPRESS)
    child.add_argument("uid")
    child.add_argument("thread")
    args = parser.parse_args()
    if args.command == "template":
        build_template(args.image)
    elif args.command == "smoke":
        smoke()
    else:
        acquire_in_process(args.uid, args.thread)
