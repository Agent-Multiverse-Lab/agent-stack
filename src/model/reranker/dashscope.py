"""通过 DashScope HTTP API 实现文本检索重排。"""

from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from .base import BaseReranker, RerankDocument, RerankError

_SUPPORTED_MODEL = "qwen3-rerank"
_MAX_DOCUMENTS = 500


class DashScopeReranker(BaseReranker):
    """调用 DashScope qwen3-rerank 并归一化返回结果。"""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        endpoint: str,
        request_timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """初始化 DashScope 文本重排适配器。"""
        model_name = model.strip()
        api_key_value = api_key.strip()
        rerank_url = endpoint.strip()

        if model_name != _SUPPORTED_MODEL:
            raise ValueError(
                f"DashScope Rerank 暂不支持模型：{model_name}"
            )
        if not api_key_value:
            raise ValueError("未配置 DashScope Rerank API Key")
        if not rerank_url:
            raise ValueError("未配置 DashScope Rerank URL")
        endpoint_url = httpx.URL(rerank_url)
        if endpoint_url.scheme not in {"http", "https"} or not endpoint_url.host:
            raise ValueError("DashScope Rerank URL 必须是有效的 HTTP 地址")
        if request_timeout <= 0:
            raise ValueError("Rerank 请求超时必须大于 0")

        self.model = model_name
        self.api_key = api_key_value
        self.endpoint = str(endpoint_url)
        self.request_timeout = request_timeout
        self._client = client

    async def _score(
        self,
        query: str,
        documents: Sequence[RerankDocument],
        *,
        top_n: int,
    ) -> Sequence[tuple[int, float]]:
        """请求 DashScope 并提取候选索引与相关性分数。"""
        if len(documents) > _MAX_DOCUMENTS:
            raise ValueError(
                "DashScope qwen3-rerank 单次候选数量不能超过 "
                f"{_MAX_DOCUMENTS}"
            )

        payload = {
            "model": self.model,
            "query": query,
            "documents": [document.text for document in documents],
            "top_n": top_n,
        }
        response = await self._post(payload)
        return self._parse_scores(response)

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        """发送单次 HTTP 请求并转换网络和状态错误。"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            if self._client is not None:
                response = await self._client.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.request_timeout,
                )
            else:
                async with httpx.AsyncClient(
                    timeout=self.request_timeout
                ) as client:
                    response = await client.post(
                        self.endpoint,
                        headers=headers,
                        json=payload,
                    )
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise RerankError("DashScope Rerank 请求超时") from exc
        except httpx.HTTPStatusError as exc:
            request_id = self._request_id(exc.response)
            request_context = (
                f"，request_id={request_id}" if request_id else ""
            )
            raise RerankError(
                "DashScope Rerank 请求失败："
                f"status={exc.response.status_code}{request_context}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RerankError("DashScope Rerank 网络请求失败") from exc

    @staticmethod
    def _parse_scores(
        response: httpx.Response,
    ) -> list[tuple[int, float]]:
        """解析 qwen3-rerank 的 OpenAI 兼容响应。"""
        try:
            payload = response.json()
        except ValueError as exc:
            raise RerankError("DashScope Rerank 返回了非法 JSON") from exc

        if not isinstance(payload, Mapping):
            raise RerankError("DashScope Rerank 响应必须是 JSON 对象")
        results = payload.get("results")
        if not isinstance(results, list):
            raise RerankError("DashScope Rerank 响应缺少 results")

        scores: list[tuple[int, float]] = []
        for result in results:
            if not isinstance(result, Mapping):
                raise RerankError("DashScope Rerank result 必须是对象")
            scores.append(
                (
                    result.get("index"),
                    result.get("relevance_score"),
                )
            )
        return scores

    @staticmethod
    def _request_id(response: httpx.Response) -> str:
        """读取可用于排查请求的非敏感 Provider ID。"""
        return (
            response.headers.get("x-request-id")
            or response.headers.get("x-dashscope-request-id")
            or response.headers.get("request-id")
            or ""
        )


__all__ = ["DashScopeReranker"]
