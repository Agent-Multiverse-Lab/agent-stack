"""Chat / Embedding / Rerank 运行时工厂与统一解析入口测试。"""

import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from src.model.model_provider.chat import build_chat_model
from src.model.model_provider.embedding import HttpEmbeddings
from src.model.model_provider.reranker import HttpReranker
from src.model.runtime import (
    load_chat_model,
    load_embedding_model,
    load_reranker,
    validate_model,
)
from src.model.service import create_model_provider
from test.test_model_repository import SQLiteModelTestCase


class ModelProtocolFactoryTest(unittest.TestCase):
    def test_chat_protocols_dispatch_to_official_langchain_classes(self):
        with patch("src.model.model_provider.chat.ChatOpenAI", return_value=object()) as openai_cls:
            res = build_chat_model(
                protocol="openai_compatible",
                model_id="deepseek-v4-pro",
                api_key="sk-ds",
                base_url="https://api.deepseek.com/v1",
                extra_headers={"X-Tenant": "t1"},
            )
            self.assertIs(res, openai_cls.return_value)
            openai_cls.assert_called_once_with(
                model="deepseek-v4-pro",
                api_key="sk-ds",
                base_url="https://api.deepseek.com/v1",
                default_headers={"X-Tenant": "t1"},
            )

        with patch("src.model.model_provider.chat.ChatAnthropic", return_value=object()) as claude_cls:
            res = build_chat_model(
                protocol="anthropic",
                model_id="claude-sonnet-4-6",
                api_key="sk-ant",
                base_url="https://api.anthropic.com",
                extra_headers={"X-Tenant": "t2"},
            )
            self.assertIs(res, claude_cls.return_value)
            claude_cls.assert_called_once_with(
                model="claude-sonnet-4-6",
                api_key="sk-ant",
                base_url="https://api.anthropic.com",
                default_headers={"X-Tenant": "t2"},
            )

        with patch("src.model.model_provider.chat.ChatGoogleGenerativeAI", return_value=object()) as gemini_cls:
            res = build_chat_model(
                protocol="gemini",
                model_id="gemini-2.5-pro",
                api_key="AIza-key",
                base_url="https://generativelanguage.googleapis.com",
                extra_headers={"X-Tenant": "t3"},
            )
            self.assertIs(res, gemini_cls.return_value)
            gemini_cls.assert_called_once_with(
                model="gemini-2.5-pro",
                api_key="AIza-key",
                base_url="https://generativelanguage.googleapis.com",
                additional_headers={"X-Tenant": "t3"},
            )

        with self.assertRaisesRegex(ValueError, "不支持的模型协议"):
            build_chat_model(
                protocol="unknown",  # type: ignore[arg-type]
                model_id="m",
                api_key="k",
                base_url="https://example.com",
            )


class HttpEmbeddingsTest(unittest.IsolatedAsyncioTestCase):
    async def test_openai_compatible_and_gemini_http_embeddings(self):
        captured: list[dict] = []

        async def openai_handler(request: httpx.Request) -> httpx.Response:
            captured.append({"url": str(request.url), "headers": dict(request.headers), "body": json.loads(request.content)})
            return httpx.Response(200, json={"data": [{"index": 1, "embedding": [0.2, 0.3]}, {"index": 0, "embedding": [0.1, 0.4]}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(openai_handler)) as client:
            emb = HttpEmbeddings(
                model="text-embedding-3-small",
                protocol="openai_compatible",
                api_key="sk-open",
                base_url="https://api.openai.com/v1",
                client=client,
            )
            vectors = await emb.aembed_documents(["a", "b"])
        self.assertEqual(vectors, [[0.1, 0.4], [0.2, 0.3]])
        self.assertEqual(captured[0]["url"], "https://api.openai.com/v1/embeddings")
        self.assertEqual(captured[0]["headers"]["authorization"], "Bearer sk-open")

        async def gemini_handler(request: httpx.Request) -> httpx.Response:
            captured.append({"url": str(request.url), "headers": dict(request.headers), "body": json.loads(request.content)})
            return httpx.Response(200, json={"embeddings": [{"values": [0.5, 0.6]}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(gemini_handler)) as client:
            emb = HttpEmbeddings(
                model="gemini-embedding-001",
                protocol="gemini",
                api_key="AIza-key",
                base_url="https://generativelanguage.googleapis.com",
                client=client,
            )
            vector = await emb.aembed_query("hello")
        self.assertEqual(vector, [0.5, 0.6])
        self.assertEqual(captured[1]["url"], "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents")
        self.assertEqual(captured[1]["headers"]["x-goog-api-key"], "AIza-key")


class RuntimeFacadeTest(SQLiteModelTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        with patch("src.model.service.refresh_model_list_cache", AsyncMock(return_value=True)):
            await create_model_provider(
                self.db,
                provider_id="dashscope",
                name="Qwen",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                embedding_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                rerank_base_url="https://dashscope.aliyuncs.com/compatible-api/v1/reranks",
                protocol="openai_compatible",
                api_key="sk-ds",
                is_enabled=True,
                enabled_models=[
                    {"model_id": "qwen3.8-max", "model_type": "qwen", "category": "chat"},
                    {"model_id": "text-embedding-v4", "model_type": "qwen", "category": "embedding"},
                    {"model_id": "qwen3-rerank", "model_type": "qwen", "category": "rerank"},
                ],
            )

    async def test_validate_and_load_three_categories_with_mismatch_guard(self):
        await validate_model(self.db, "dashscope/qwen3.8-max", category="chat")
        await validate_model(self.db, "dashscope/text-embedding-v4", category="embedding")
        await validate_model(self.db, "dashscope/qwen3-rerank", category="rerank")

        with self.assertRaisesRegex(ValueError, "模型类型不匹配"):
            await validate_model(self.db, "dashscope/text-embedding-v4", category="chat")

        with patch("src.model.model_provider.chat.ChatOpenAI", return_value=object()) as chat_cls:
            chat = await load_chat_model("dashscope/qwen3.8-max", db=self.db)
            self.assertIs(chat, chat_cls.return_value)

        emb = await load_embedding_model("dashscope/text-embedding-v4", db=self.db)
        self.assertIsInstance(emb, HttpEmbeddings)
        self.assertEqual(emb.endpoint, "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings")

        reranker = await load_reranker("dashscope/qwen3-rerank", db=self.db)
        self.assertIsInstance(reranker, HttpReranker)
        self.assertEqual(reranker.endpoint, "https://dashscope.aliyuncs.com/compatible-api/v1/reranks")
