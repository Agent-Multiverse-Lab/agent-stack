"""知识库问答服务测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from server.service import knowledge_service


class FakeSession:
    """无事务边界需求的最小会话。"""

    async def commit(self) -> None:
        """记录提交。"""

    async def rollback(self) -> None:
        """记录回滚。"""


class FakeModel:
    """返回固定回答。"""

    def __init__(self) -> None:
        self.calls = []

    async def ainvoke(self, messages):
        """记录调用并返回回答。"""
        self.calls.append(messages)
        return SimpleNamespace(content="答案见[1]。")


class KnowledgeChatServiceTest(unittest.IsolatedAsyncioTestCase):
    def _patch_search(self, *, hits):
        """替换 search 返回固定检索命中。"""
        return patch.object(
            knowledge_service,
            "search",
            return_value={
                "kb_id": "kb-1",
                "hits": hits,
            },
        )

    def _build_hits(self):
        """构造两个固定检索命中。"""
        return [
            {
                "id": "f1:0",
                "distance": 0.9,
                "entity": {
                    "chunk": "OpenAI 发布了 GPT 模型。" + "长" * 500,
                    "chunk_id": "f1:0",
                    "file_id": "f1",
                    "metadata": {"file_name": "manual.pdf"},
                },
            },
            {
                "id": "f2:0",
                "distance": 0.8,
                "entity": {
                    "chunk": "GPT 是通用大语言模型。",
                    "chunk_id": "f2:0",
                    "file_id": "f2",
                    "metadata": {},
                },
            },
        ]

    async def test_chat_generates_answer_with_citations(self) -> None:
        """有命中时生成带引用的回答。"""
        model = FakeModel()
        with (
            self._patch_search(hits=self._build_hits()),
            patch.object(
                knowledge_service,
                "load_model",
                return_value=model,
            ),
        ):
            result = await knowledge_service.chat(
                FakeSession(),
                uid="user-1",
                kb_id="kb-1",
                query="GPT 是什么？",
                limit=8,
            )

        self.assertEqual("答案见[1]。", result["answer"])
        self.assertEqual(2, len(result["citations"]))
        self.assertEqual("manual.pdf", result["citations"][0]["file_name"])
        self.assertEqual("f1:0", result["citations"][0]["chunk_id"])
        self.assertEqual(300, len(result["citations"][0]["excerpt"]))
        self.assertEqual(1, len(model.calls))

    async def test_chat_returns_fixed_answer_without_llm_when_no_hits(self) -> None:
        """无命中时不调用 LLM 并返回固定答语。"""
        model = FakeModel()
        with (
            self._patch_search(hits=[]),
            patch.object(
                knowledge_service,
                "load_model",
                return_value=model,
            ),
        ):
            result = await knowledge_service.chat(
                FakeSession(),
                uid="user-1",
                kb_id="kb-1",
                query="不相关的问题",
                limit=8,
            )

        self.assertEqual(
            knowledge_service._CHAT_NO_ANSWER,
            result["answer"],
        )
        self.assertEqual([], result["citations"])
        self.assertEqual([], model.calls)


if __name__ == "__main__":
    unittest.main()
