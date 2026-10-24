"""会话标题生成的模型选择、失败降级与权限边界。"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from server.service import thread_service as service


class ThreadTitleTests(unittest.IsolatedAsyncioTestCase):
    async def test_generates_short_title_with_flash_model(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content="知识库 检索设计")))
        with (
            patch.object(service, "_require_thread", new_callable=AsyncMock),
            patch.object(service, "build_model_list", AsyncMock(return_value=SimpleNamespace(
                flash_model="provider/fast", default_model="provider/default",
            ))),
            patch.object(service, "load_chat_model", AsyncMock(return_value=model)) as load,
        ):
            title = await service.generate_thread_title(
                object(), uid="user", thread_id="thread", query="如何设计知识库检索？",
            )
        self.assertEqual(title, "知识库 检索设计")
        load.assert_awaited_once_with("provider/fast")
        self.assertEqual(model.ainvoke.call_args.args[0][1], ("human", "如何设计知识库检索？"))

    async def test_model_failure_uses_question_prefix(self):
        with (
            patch.object(service, "_require_thread", new_callable=AsyncMock),
            patch.object(service, "build_model_list", AsyncMock(side_effect=RuntimeError("unavailable"))),
        ):
            title = await service.generate_thread_title(
                object(), uid="user", thread_id="thread", query="  问题\n" + "内容" * 30,
            )
        self.assertEqual(title, ("问题 " + "内容" * 30)[:30])

    async def test_missing_flash_uses_default_and_empty_output_uses_question(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content=" ")))
        with (
            patch.object(service, "_require_thread", new_callable=AsyncMock),
            patch.object(service, "build_model_list", AsyncMock(return_value=SimpleNamespace(
                flash_model="", default_model="provider/default",
            ))),
            patch.object(service, "load_chat_model", AsyncMock(return_value=model)) as load,
        ):
            title = await service.generate_thread_title(
                object(), uid="user", thread_id="thread", query="我的问题",
            )
        load.assert_awaited_once_with("provider/default")
        self.assertEqual(title, "我的问题")

    async def test_inaccessible_thread_never_calls_model(self):
        with (
            patch.object(service, "_require_thread", AsyncMock(side_effect=LookupError("missing"))),
            patch.object(service, "load_chat_model", new_callable=AsyncMock) as load,
        ):
            with self.assertRaises(LookupError):
                await service.generate_thread_title(
                    object(), uid="other", thread_id="thread", query="question",
                )
        load.assert_not_awaited()
