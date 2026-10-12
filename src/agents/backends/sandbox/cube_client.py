"""Cube 管理请求补充 SDK 缺少的完整查询和有界 HTTP 超时。"""

from __future__ import annotations

from urllib.parse import quote

import httpx
from cubesandbox import Config as CubeConfig
from cubesandbox import Sandbox


class CubeClient:
    def __init__(self, config: CubeConfig, *, master_url: str, node_id: str, http_client: httpx.Client | None = None):
        self.config = config
        self.inventory_url = master_url.rstrip("/") + "/cube/sandbox/inventory"
        self.node_id = node_id
        self.http = http_client or httpx.Client(
            base_url=config.api_url,
            headers={"X-API-Key": config.api_key} if config.api_key else {},
            timeout=config.request_timeout,
        )

    def find(self, identity: dict[str, str]) -> dict | None:
        response = self.http.get(self.inventory_url, params={"host_id": self.node_id})
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("ret"), dict) or body["ret"].get("ret_code") != 0:
            raise RuntimeError("Cube node inventory failed; refusing to create another sandbox")
        rows = body.get("data")
        if body.get("size") != 1 or not isinstance(rows, list):
            raise RuntimeError("Cube node inventory is incomplete; refusing to create another sandbox")
        if any(not isinstance(row, dict) or not isinstance(row.get("labels") or {}, dict) for row in rows):
            raise RuntimeError("Invalid Cube node inventory")
        matches = [row for row in rows if all((row.get("labels") or {}).get(k) == v for k, v in identity.items())]
        if len(matches) > 1:
            raise RuntimeError("Multiple Cube sandboxes match this conversation; explicit cleanup is required")
        if not matches:
            return None
        row = matches[0]
        if not isinstance(row.get("sandbox_id"), str) or not row["sandbox_id"]:
            raise RuntimeError("Cube inventory returned no sandbox_id")
        return {"sandboxID": row["sandbox_id"], "metadata": row["labels"]}

    def connect(self, sandbox_id: str, idle_timeout: int) -> dict | None:
        response = self.http.post(self.path(sandbox_id) + "/connect", json={"timeout": idle_timeout})
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def create(self, metadata: dict[str, str], idle_timeout: int) -> dict:
        response = self.http.post(
            "/sandboxes",
            json={
                "templateID": self.config.template_id,
                "timeout": idle_timeout,
                "lifecycle": {"onTimeout": "kill"},
                "metadata": metadata,
            },
        )
        response.raise_for_status()
        return response.json()

    def info(self, sandbox_id: str) -> dict | None:
        response = self.http.get(self.path(sandbox_id))
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def delete(self, sandbox_id: str) -> None:
        response = self.http.delete(self.path(sandbox_id))
        if response.status_code != 404:
            response.raise_for_status()

    def sandbox(self, data: dict) -> Sandbox:
        if not isinstance(data.get("sandboxID"), str) or not data["sandboxID"]:
            raise RuntimeError("Cube returned no sandboxID")
        return Sandbox(data, config=self.config)

    @staticmethod
    def path(sandbox_id: str) -> str:
        return "/sandboxes/" + quote(sandbox_id, safe="")

    def close(self) -> None:
        self.http.close()
