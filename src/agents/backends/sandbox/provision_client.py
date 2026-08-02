from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


@dataclass(frozen=True)
class SandboxProvision:
    sandbox_id: str
    sandbox_url: str
    status: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> SandboxProvision:
        sandbox_id = str(payload.get("sandbox_id") or "").strip()
        sandbox_url = str(payload.get("sandbox_url") or "").strip()
        if not sandbox_id:
            raise ValueError("Provision response is missing sandbox_id.")
        if not sandbox_url:
            raise ValueError("Provision response is missing sandbox_url.")
        return cls(
            sandbox_id=sandbox_id,
            sandbox_url=sandbox_url,
            status=payload.get("status"),
        )

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "sandbox_id": self.sandbox_id,
            "sandbox_url": self.sandbox_url,
        }
        if self.status is not None:
            data["status"] = self.status
        return data



class SandboxProvisionClient:
    """直接调用沙箱供应服务 HTTP 接口的客户端。"""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        base_url = str(base_url).strip()
        if not base_url:
            raise ValueError("base_url is required.")

        self.base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._closed = False
        self._client = http_client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            follow_redirects=True,
        )

    def create(
        self,
        *,
        sandbox_id: str,
        thread_id: str,
        user_id: str,
        file_thread_id: str | None = None,
        skills_thread_id: str | None = None,
        env: dict[str, str] | None = None,
    ) -> SandboxProvision:
        payload: dict[str, Any] = {
            "sandbox_id": self._required(sandbox_id, "sandbox_id"),
            "thread_id": self._required(thread_id, "thread_id"),
            "uid": self._required(user_id, "user_id"),
            "env": dict(env or {}),
        }
        if file_thread_id is not None:
            payload["file_thread_id"] = self._required(file_thread_id, "file_thread_id")
        if skills_thread_id is not None:
            payload["skills_thread_id"] = self._required(
                skills_thread_id,
                "skills_thread_id",
            )

        data = self._request_json("POST", "/api/sandboxes", json=payload)
        if data is None:
            raise RuntimeError("Sandbox provisioner returned no create payload.")
        return SandboxProvision.from_payload(data)

    def get(self, sandbox_id: str) -> SandboxProvision | None:
        data = self._request_json(
            "GET",
            self._sandbox_path(sandbox_id),
        )
        if data is None:
            return None
        return SandboxProvision.from_payload(data)

    def list(self) -> list[SandboxProvision]:
        data = self._request_json("GET", "/api/sandboxes")
        sandboxes = data.get("sandboxes") if isinstance(data, dict) else None
        if not isinstance(sandboxes, list):
            raise RuntimeError("Provision response is missing sandboxes list.")
        return [
            SandboxProvision.from_payload(item)
            for item in sandboxes
            if isinstance(item, dict)
        ]

    def touch(self, sandbox_id: str) -> bool:
        """刷新供应服务中指定沙箱的空闲计时。"""
        data = self._request_json(
            "POST",
            f"{self._sandbox_path(sandbox_id)}/touch",
        )
        return bool(data.get("ok", False)) if isinstance(data, dict) else False

    def delete(self, sandbox_id: str) -> bool:
        data = self._request_json(
            "DELETE",
            self._sandbox_path(sandbox_id),
        )
        return bool(data.get("ok", True)) if isinstance(data, dict) else True

    def close(self) -> None:
        """关闭由当前适配器创建并持有的 HTTP 客户端。"""
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> SandboxProvisionClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if self._closed:
            raise RuntimeError("Sandbox provision client is closed.")
        try:
            response = self._client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Sandbox provisioner request failed: {exc}") from exc

        if response.status_code == 404:
            return None

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Sandbox provisioner returned HTTP {response.status_code}: {response.text}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError("Sandbox provisioner returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise RuntimeError("Sandbox provisioner returned non-object JSON.")
        return data

    @classmethod
    def _sandbox_path(cls, sandbox_id: str) -> str:
        encoded_id = quote(cls._required(sandbox_id, "sandbox_id"), safe="")
        return f"/api/sandboxes/{encoded_id}"

    @staticmethod
    def _required(value: str, label: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError(f"{label} is required.")
        return value
