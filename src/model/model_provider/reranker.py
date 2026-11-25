"""检索重排契约及通用 HTTP Rerank 适配器。"""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import isfinite
from numbers import Real
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.configs import config as sys_config

from ..repository import fetch_model_config
from ..utils import ModelProtocol, normalize_base_url, resolve_provider_api_key

_MAX_DOCUMENTS = 500


@dataclass(frozen=True, slots=True)
class RerankDocument:
    """表示一个待重排的业务文档。"""

    id: str
    text: str
    original_rank: int
    retrieval_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RerankResult:
    """表示归一化后的单条重排结果。"""

    document: RerankDocument
    relevance_score: float
    rerank_rank: int


class RerankError(RuntimeError):
    """表示 Rerank Provider 请求或响应异常。"""

    def __init__(self, message: str, *, code: str = "http_error", status_code: int | None = None) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class BaseReranker(ABC):
    """校验通用输入并将 Provider 分数转换为稳定结果。"""

    async def arerank(
        self,
        query: str,
        documents: Sequence[RerankDocument],
        *,
        top_n: int,
    ) -> list[RerankResult]:
        """重排候选文档并返回稳定的相关性顺序。"""
        query_text = query.strip()
        if not query_text:
            raise ValueError("Rerank 查询不能为空")
        if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n <= 0:
            raise ValueError("Rerank top_n 必须是正整数")

        candidates = tuple(documents)
        if not candidates:
            raise ValueError("Rerank 候选文档不能为空")
        self._validate_documents(candidates)

        result_count = min(top_n, len(candidates))
        scored_indices = tuple(
            await self._score(
                query_text,
                candidates,
                top_n=result_count,
            )
        )
        if len(scored_indices) != result_count:
            raise RerankError(
                "Rerank 返回数量与请求不一致："
                f"expected={result_count}, actual={len(scored_indices)}",
                code="invalid_response",
            )

        validated_scores = self._validate_scores(
            scored_indices,
            candidate_count=len(candidates),
        )
        validated_scores.sort(
            key=lambda item: (
                -item[1],
                candidates[item[0]].original_rank,
            )
        )
        return [
            RerankResult(
                document=candidates[index],
                relevance_score=score,
                rerank_rank=rank,
            )
            for rank, (index, score) in enumerate(
                validated_scores,
                start=1,
            )
        ]

    @abstractmethod
    async def _score(
        self,
        query: str,
        documents: Sequence[RerankDocument],
        *,
        top_n: int,
    ) -> Sequence[tuple[int, float]]:
        """调用具体 Provider 并返回输入索引及相关性分数。"""

    @staticmethod
    def _validate_documents(
        documents: Sequence[RerankDocument],
    ) -> None:
        """校验候选业务标识、正文和原始排名。"""
        document_ids: set[str] = set()
        original_ranks: set[int] = set()

        for document in documents:
            if not isinstance(document.id, str) or not document.id.strip():
                raise ValueError("Rerank 文档 ID 不能为空")
            if document.id in document_ids:
                raise ValueError(f"Rerank 文档 ID 重复：{document.id}")
            document_ids.add(document.id)

            if not isinstance(document.text, str) or not document.text.strip():
                raise ValueError(f"Rerank 文档正文不能为空：{document.id}")
            if (
                isinstance(document.original_rank, bool)
                or not isinstance(document.original_rank, int)
                or document.original_rank <= 0
            ):
                raise ValueError(
                    f"Rerank 原始排名必须是正整数：{document.id}"
                )
            if document.original_rank in original_ranks:
                raise ValueError(
                    f"Rerank 原始排名重复：{document.original_rank}"
                )
            original_ranks.add(document.original_rank)

            retrieval_score = document.retrieval_score
            if retrieval_score is not None and (
                isinstance(retrieval_score, bool)
                or not isinstance(retrieval_score, Real)
                or not isfinite(float(retrieval_score))
            ):
                raise ValueError(
                    f"Rerank 原始检索分数非法：{document.id}"
                )

    @staticmethod
    def _validate_scores(
        scored_indices: Sequence[tuple[int, float]],
        *,
        candidate_count: int,
    ) -> list[tuple[int, float]]:
        """校验 Provider 返回的索引和有限分数。"""
        seen_indices: set[int] = set()
        validated_scores: list[tuple[int, float]] = []

        for item in scored_indices:
            if not isinstance(item, tuple) or len(item) != 2:
                raise RerankError("Rerank 结果必须包含 index 和 score", code="invalid_response")

            index, score = item
            if (
                isinstance(index, bool)
                or not isinstance(index, int)
                or index < 0
                or index >= candidate_count
            ):
                raise RerankError(f"Rerank 返回了非法文档索引：{index}", code="invalid_response")
            if index in seen_indices:
                raise RerankError(f"Rerank 返回了重复文档索引：{index}", code="invalid_response")
            if (
                isinstance(score, bool)
                or not isinstance(score, Real)
                or not isfinite(float(score))
            ):
                raise RerankError(f"Rerank 返回了非法相关性分数：{score}", code="invalid_response")

            seen_indices.add(index)
            validated_scores.append((index, float(score)))

        return validated_scores


class HttpReranker(BaseReranker):
    """通过标准 HTTP Rerank URL（OpenAI / DashScope / Cohere 兼容）执行重排。"""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        endpoint: str,
        extra_headers: dict[str, str] | None = None,
        request_timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        model_name = model.strip()
        api_key_value = api_key.strip()
        rerank_url = endpoint.strip()

        if not model_name:
            raise ValueError("Rerank 模型名称不能为空")
        if not api_key_value:
            raise ValueError("未配置 Rerank API Key")
        if not rerank_url:
            raise ValueError("未配置 Rerank URL")
        endpoint_url = httpx.URL(rerank_url)
        if endpoint_url.scheme not in {"http", "https"} or not endpoint_url.host:
            raise ValueError("Rerank URL 必须是有效的 HTTP 地址")
        if request_timeout <= 0:
            raise ValueError("Rerank 请求超时必须大于 0")

        self.model = model_name
        self.api_key = api_key_value
        self.endpoint = str(endpoint_url)
        self.extra_headers = dict(extra_headers or {})
        self.request_timeout = request_timeout
        self._client = client

    async def _score(
        self,
        query: str,
        documents: Sequence[RerankDocument],
        *,
        top_n: int,
    ) -> Sequence[tuple[int, float]]:
        if len(documents) > _MAX_DOCUMENTS:
            raise ValueError(
                f"Rerank 单次候选数量不能超过 {_MAX_DOCUMENTS}"
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
        headers = {
            **self.extra_headers,
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
            raise RerankError("Rerank 请求超时", code="timeout") from exc
        except httpx.HTTPStatusError as exc:
            request_id = self._request_id(exc.response)
            request_context = (
                f"，request_id={request_id}" if request_id else ""
            )
            raise RerankError(
                "Rerank 请求失败："
                f"status={exc.response.status_code}{request_context}",
                code="http_error",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise RerankError("Rerank 网络请求失败", code="connection_error") from exc

    @staticmethod
    def _parse_scores(
        response: httpx.Response,
    ) -> list[tuple[int, float]]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise RerankError("Rerank 返回了非法 JSON", code="invalid_response") from exc

        if not isinstance(payload, Mapping):
            raise RerankError("Rerank 响应必须是 JSON 对象", code="invalid_response")
        results = payload.get("results")
        if not isinstance(results, list):
            raise RerankError("Rerank 响应缺少 results", code="invalid_response")

        scores: list[tuple[int, float]] = []
        for result in results:
            if not isinstance(result, Mapping):
                raise RerankError("Rerank result 必须是对象", code="invalid_response")
            scores.append(
                (
                    result.get("index"),
                    result.get("relevance_score"),
                )
            )
        return scores

    @staticmethod
    def _request_id(response: httpx.Response) -> str:
        return (
            response.headers.get("x-request-id")
            or response.headers.get("x-dashscope-request-id")
            or response.headers.get("request-id")
            or ""
        )


def build_reranker(
    *,
    protocol: ModelProtocol,
    model_id: str,
    api_key: str,
    base_url: str,
    endpoint: str | None = None,
    extra_headers: dict[str, str] | None = None,
    request_timeout: float = 30.0,
) -> HttpReranker:
    if endpoint is not None and endpoint.strip():
        target = normalize_base_url(endpoint.strip())
    elif protocol == "openai_compatible" and base_url.strip():
        target = f"{normalize_base_url(base_url)}/reranks"
    else:
        raise ValueError("Rerank 模型缺少有效的服务地址")
    return HttpReranker(
        model=model_id,
        api_key=api_key,
        endpoint=target,
        extra_headers=extra_headers,
        request_timeout=request_timeout,
    )


async def load_reranker(
    model_ref: str | None = None,
    *,
    db: AsyncSession | None = None,
) -> BaseReranker:
    """按入库配置加载 HTTP Rerank 模型实例。"""
    ref = (model_ref or sys_config.rerank_model).strip()
    if not ref:
        raise ValueError("未配置 Rerank 模型，应设置 RERANK_MODEL=provider_id:model_id")
    provider, model = await fetch_model_config(ref, category="rerank", db=db)
    endpoint = provider.rerank_base_url or None
    if endpoint is None and provider.provider_id == "dashscope" and sys_config.dashscope_rerank_url.strip():
        endpoint = sys_config.dashscope_rerank_url.strip()
    return build_reranker(
        protocol=provider.protocol,
        model_id=model["model_id"],
        api_key=resolve_provider_api_key(provider.api_key or ""),
        base_url=provider.base_url,
        endpoint=endpoint,
        extra_headers=dict(provider.extra_headers or {}),
        request_timeout=sys_config.rerank_request_timeout_seconds,
    )


__all__ = [
    "BaseReranker",
    "HttpReranker",
    "RerankDocument",
    "RerankError",
    "RerankResult",
    "build_reranker",
    "load_reranker",
]
