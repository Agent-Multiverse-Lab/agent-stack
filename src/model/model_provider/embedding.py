"""基于 HTTP URL 的向量化模型实现，支持 OpenAI 兼容与 Gemini 协议。"""

from collections.abc import Mapping, Sequence
from typing import Any

import httpx
from langchain_core.embeddings import Embeddings

from ..utils import ModelProtocol, normalize_base_url

SUPPORTED_EMBEDDING_PROTOCOLS = frozenset({"openai_compatible", "gemini"})


class EmbeddingError(RuntimeError):
    """表示 Embedding 请求或响应异常，不暴露敏感凭据。"""

    def __init__(self, message: str, *, code: str = "http_error", status_code: int | None = None) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _default_embedding_url(*, protocol: ModelProtocol, base_url: str, model: str) -> str:
    root = normalize_base_url(base_url)
    if protocol == "openai_compatible":
        if root.endswith("/embeddings"):
            return root
        return f"{root}/embeddings"
    if protocol == "gemini":
        if ":batchEmbedContents" in root:
            return root
        if root.endswith("/v1beta"):
            return f"{root}/models/{model}:batchEmbedContents"
        return f"{root}/v1beta/models/{model}:batchEmbedContents"
    raise ValueError(f"不支持的 Embedding 协议：{protocol}")


def _request_id(response: httpx.Response) -> str:
    return (
        response.headers.get("x-request-id")
        or response.headers.get("x-dashscope-request-id")
        or response.headers.get("request-id")
        or ""
    )


class HttpEmbeddings(Embeddings):
    """直连 HTTP URL 执行文本向量化并实现 LangChain Embeddings 契约。"""

    def __init__(
        self,
        *,
        model: str,
        protocol: ModelProtocol = "openai_compatible",
        api_key: str = "",
        base_url: str = "",
        endpoint: str | None = None,
        extra_headers: dict[str, str] | None = None,
        batch_size: int = 32,
        request_timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        model_name = model.strip()
        if not model_name:
            raise ValueError("Embedding 模型名称不能为空")
        if protocol not in SUPPORTED_EMBEDDING_PROTOCOLS:
            raise ValueError(f"不支持的 Embedding 协议：{protocol}")
        if batch_size <= 0:
            raise ValueError("Embedding batch_size 必须大于 0")
        if request_timeout <= 0:
            raise ValueError("Embedding 请求超时必须大于 0")

        if endpoint is not None and endpoint.strip():
            resolved_url = normalize_base_url(endpoint.strip())
        elif base_url.strip():
            resolved_url = _default_embedding_url(
                protocol=protocol,
                base_url=base_url.strip(),
                model=model_name,
            )
        else:
            raise ValueError("Embedding 缺少有效的服务地址")

        self.model = model_name
        self.protocol = protocol
        self.api_key = api_key.strip()
        self.endpoint = resolved_url
        self.extra_headers = dict(extra_headers or {})
        self.batch_size = batch_size
        self.request_timeout = request_timeout
        self._client = client

    def _headers(self) -> dict[str, str]:
        headers = {**self.extra_headers, "Content-Type": "application/json"}
        if self.api_key:
            if self.protocol == "gemini":
                headers["x-goog-api-key"] = self.api_key
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_payload(self, batch: Sequence[str]) -> dict[str, Any]:
        if self.protocol == "gemini":
            return {
                "requests": [
                    {
                        "model": f"models/{self.model}",
                        "content": {"parts": [{"text": text}]},
                    }
                    for text in batch
                ]
            }
        return {"model": self.model, "input": list(batch)}

    def _parse_response(self, response: httpx.Response, expected_count: int) -> list[list[float]]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise EmbeddingError("Embedding 返回了非法 JSON", code="invalid_response") from exc
        if not isinstance(payload, Mapping):
            raise EmbeddingError("Embedding 响应必须是 JSON 对象", code="invalid_response")

        if self.protocol == "gemini":
            items = payload.get("embeddings")
            if not isinstance(items, list) or len(items) != expected_count:
                raise EmbeddingError("Embedding 返回数量或结构无效", code="invalid_response")
            vectors: list[list[float]] = []
            for item in items:
                if not isinstance(item, Mapping) or not isinstance(item.get("values"), list):
                    raise EmbeddingError("Embedding 响应缺少 values", code="invalid_response")
                vectors.append([float(value) for value in item["values"]])
            return vectors

        items = payload.get("data")
        if not isinstance(items, list) or len(items) != expected_count:
            raise EmbeddingError("Embedding 返回数量或结构无效", code="invalid_response")
        indexed: list[tuple[int, list[float]]] = []
        for pos, item in enumerate(items):
            if not isinstance(item, Mapping) or not isinstance(item.get("embedding"), list):
                raise EmbeddingError("Embedding 响应缺少 embedding", code="invalid_response")
            index = item.get("index", pos)
            if isinstance(index, bool) or not isinstance(index, int):
                raise EmbeddingError("Embedding 响应 index 无效", code="invalid_response")
            indexed.append((index, [float(value) for value in item["embedding"]]))
        indexed.sort(key=lambda pair: pair[0])
        return [vector for _, vector in indexed]

    async def _apost_batch(self, batch: Sequence[str]) -> list[list[float]]:
        headers = self._headers()
        payload = self._build_payload(batch)
        try:
            if self._client is not None:
                response = await self._client.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.request_timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                    response = await client.post(
                        self.endpoint,
                        headers=headers,
                        json=payload,
                    )
            response.raise_for_status()
            return self._parse_response(response, len(batch))
        except EmbeddingError:
            raise
        except httpx.TimeoutException as exc:
            raise EmbeddingError("Embedding 请求超时", code="timeout") from exc
        except httpx.HTTPStatusError as exc:
            rid = _request_id(exc.response)
            ctx = f"，request_id={rid}" if rid else ""
            raise EmbeddingError(
                f"Embedding 请求失败：status={exc.response.status_code}{ctx}",
                code="http_error",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingError("Embedding 网络请求失败", code="connection_error") from exc

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors.extend(await self._apost_batch(batch))
        return vectors

    async def aembed_query(self, text: str) -> list[float]:
        vectors = await self.aembed_documents([text])
        if not vectors:
            raise EmbeddingError("Embedding 未返回向量", code="invalid_response")
        return vectors[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        headers = self._headers()
        vectors: list[list[float]] = []
        try:
            with httpx.Client(timeout=self.request_timeout) as client:
                for start in range(0, len(texts), self.batch_size):
                    batch = texts[start : start + self.batch_size]
                    response = client.post(
                        self.endpoint,
                        headers=headers,
                        json=self._build_payload(batch),
                    )
                    response.raise_for_status()
                    vectors.extend(self._parse_response(response, len(batch)))
            return vectors
        except EmbeddingError:
            raise
        except httpx.TimeoutException as exc:
            raise EmbeddingError("Embedding 请求超时", code="timeout") from exc
        except httpx.HTTPStatusError as exc:
            rid = _request_id(exc.response)
            ctx = f"，request_id={rid}" if rid else ""
            raise EmbeddingError(
                f"Embedding 请求失败：status={exc.response.status_code}{ctx}",
                code="http_error",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingError("Embedding 网络请求失败", code="connection_error") from exc

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_documents([text])
        if not vectors:
            raise EmbeddingError("Embedding 未返回向量", code="invalid_response")
        return vectors[0]


def build_embedding_model(
    *,
    protocol: ModelProtocol,
    model_id: str,
    api_key: str,
    base_url: str,
    endpoint: str | None = None,
    extra_headers: dict[str, str] | None = None,
    batch_size: int = 32,
    request_timeout: float = 30.0,
) -> HttpEmbeddings:
    return HttpEmbeddings(
        model=model_id,
        protocol=protocol,
        api_key=api_key,
        base_url=base_url,
        endpoint=endpoint,
        extra_headers=extra_headers,
        batch_size=batch_size,
        request_timeout=request_timeout,
    )


__all__ = [
    "EmbeddingError",
    "HttpEmbeddings",
    "SUPPORTED_EMBEDDING_PROTOCOLS",
    "build_embedding_model",
]
