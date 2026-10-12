import base64
import json
import shlex
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.agents.backends.sandbox.sandbox_backend import CubeSandboxBackend


@pytest.fixture
def backend(tmp_path):
    def write(path, data):
        (tmp_path / path.removeprefix("/workspace/")).write_bytes(data)

    def run(command, **kwargs):
        assert kwargs["cwd"] == "/workspace"
        assert command.startswith("timeout --signal=TERM --kill-after=5s ")
        inner = shlex.split(shlex.split(command)[-1])
        assert inner[:2] == ["python3", "-c"]
        path, offset, signature = json.loads(base64.b64decode(inner[3]))
        mapped = str(tmp_path / path.removeprefix("/workspace/"))
        args = base64.b64encode(json.dumps([mapped, offset, signature]).encode()).decode()
        result = subprocess.run([sys.executable, "-c", inner[2], args], capture_output=True, text=True, timeout=5)
        return SimpleNamespace(stdout=result.stdout, stderr=result.stderr, exit_code=result.returncode)

    client = SimpleNamespace(sandbox_id="cube-test", files=SimpleNamespace(write=Mock(side_effect=write)), commands=SimpleNamespace(run=Mock(side_effect=run)))
    return CubeSandboxBackend(uid="alice", thread_id="thread", client=client)


@pytest.mark.parametrize("content", [b"", bytes(range(256)) * 5000, "中文\n".encode() * 30000], ids=["empty", "binary", "utf8"])
def test_download_returns_complete_bytes_beyond_preview_limit(backend, content):
    assert backend.upload_files([("/workspace/data.bin", content)])[0].error is None
    result = backend.download_files(["/workspace/data.bin"])[0]
    assert result.error is None
    assert result.content == content


def test_missing_and_invalid_files_are_reported_individually(backend):
    results = backend.download_files(["/workspace/missing", "../escape"])
    assert results[0].error == "file_not_found"
    assert results[1].error == "invalid_path"
    assert all(result.content is None for result in results)


def test_truncated_transfer_never_returns_partial_file(backend):
    backend._client.commands.run.side_effect = None
    backend._client.commands.run.return_value = SimpleNamespace(stdout=json.dumps({"signature": [1, 2, 100, 4], "data": "YQ=="}), stderr="", exit_code=0)
    result = backend.download_files(["/workspace/data.bin"])[0]
    assert result.content is None
    assert "Incomplete" in result.error


def test_execute_preserves_exit_code_stderr_and_full_output(backend):
    backend._client.commands.run.side_effect = None
    backend._client.commands.run.return_value = SimpleNamespace(stdout="x" * 200000, stderr="failure", exit_code=7)
    result = backend.execute("printf test", timeout=2)
    assert result.exit_code == 7
    assert result.output == "x" * 200000 + "\nfailure"
    assert not result.truncated
    assert backend._client.commands.run.call_args.kwargs["timeout"] == 12


def test_transport_failure_does_not_replay_command(backend):
    backend._client.commands.run.side_effect = TimeoutError("uncertain result")
    result = backend.execute("touch /workspace/once")
    assert result.exit_code == 1
    backend._client.commands.run.assert_called_once()
