"""真实 LangGraph 轮次退出与消息收敛的回归测试。"""

import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from server.service import thread_service
from src.agents.middlewares import steer_stop_middleware as steer


@asynccontextmanager
async def fake_session():
    yield object()


class ToolModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class SteerBoundaryTest(unittest.IsolatedAsyncioTestCase):
    async def test_tools_finish_before_stop_and_checkpoint_preserves_pairs(self):
        executed = []
        queued = False

        @tool
        async def finish_work() -> str:
            """完成当前工具。"""
            nonlocal queued
            executed.append("tool")
            queued = True
            return "done"

        async def should_stop(_thread_id):
            executed.append("before_model")
            return queued

        model = ToolModel(messages=iter([
            AIMessage(content="working", tool_calls=[{"name": "finish_work", "args": {}, "id": "call-1"}]),
            AIMessage(content="should not execute"),
        ]))
        graph = create_agent(model, tools=[finish_work], middleware=[steer.SteerStopMiddleware()], checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "thread-1"}}
        with (
            patch.object(steer, "session_context", fake_session),
            patch.object(steer, "AgentRunRequestQueueRepository", return_value=SimpleNamespace(has_queued_steer_for_thread=should_stop)),
        ):
            result = await graph.ainvoke({"messages": [HumanMessage(content="go")]}, config, context=SimpleNamespace(thread_id="thread-1", run_id="run-1"))
        self.assertEqual(executed, ["before_model", "tool", "before_model"])
        self.assertEqual([m.type for m in result["messages"]], ["human", "ai", "tool"])
        checkpoint = await graph.aget_state(config)
        self.assertEqual(checkpoint.values["steered_run_id"], "run-1")
        self.assertEqual(checkpoint.values["messages"][-1].tool_call_id, "call-1")

    async def test_revoked_steer_allows_next_model(self):
        middleware = steer.SteerStopMiddleware()
        with (
            patch.object(steer, "session_context", fake_session),
            patch.object(steer, "AgentRunRequestQueueRepository", return_value=SimpleNamespace(has_queued_steer_for_thread=AsyncMock(return_value=False))),
        ):
            self.assertIsNone(await middleware.abefore_model({}, SimpleNamespace(context=SimpleNamespace(thread_id="t"))))


class PartialReconciliationTest(unittest.IsolatedAsyncioTestCase):
    async def test_partial_reuses_audit_and_keeps_output_binding(self):
        message = SimpleNamespace(id=7, message_type="model_audit")
        audits = SimpleNamespace(get=AsyncMock(return_value=message), reconcile_to_history=AsyncMock(return_value=message))
        runs = SimpleNamespace(lock_output_persistence=AsyncMock(return_value=object()), set_output_message=AsyncMock())
        db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        conversations = SimpleNamespace(session=db, add_message_by_thread_id=AsyncMock())
        with (
            patch.object(thread_service, "ModelMessageAuditRepository", return_value=audits),
            patch.object(thread_service, "AgentRunRepository", return_value=runs),
        ):
            result = await thread_service.save_partial_message(
                conversations, "t", uid="u", run_id="r", request_id="q", worker_id="w",
                full_msg=AIMessage(content="partial"), operation_id="model-1",
            )
        self.assertIs(result, message)
        conversations.add_message_by_thread_id.assert_not_awaited()
        self.assertEqual(audits.reconcile_to_history.await_args.kwargs["content"], "partial")
        runs.set_output_message.assert_awaited_once_with(run_id="r", output_message_id=7, worker_id="w")

    async def test_checkpoint_message_is_not_overwritten_or_duplicated(self):
        message = SimpleNamespace(id=7, message_type="text", content="complete")
        audits = SimpleNamespace(get=AsyncMock(return_value=message), reconcile_to_history=AsyncMock())
        runs = SimpleNamespace(lock_output_persistence=AsyncMock(return_value=object()))
        conversations = SimpleNamespace(session=Mock(), add_message_by_thread_id=AsyncMock())
        with (
            patch.object(thread_service, "ModelMessageAuditRepository", return_value=audits),
            patch.object(thread_service, "AgentRunRepository", return_value=runs),
        ):
            result = await thread_service.save_partial_message(
                conversations, "t", uid="u", run_id="r", request_id="q", worker_id="w",
                full_msg=AIMessage(content="partial"), operation_id="model-1",
            )
        self.assertIs(result, message)
        audits.reconcile_to_history.assert_not_awaited()
        conversations.add_message_by_thread_id.assert_not_awaited()

class DispatchHTTPTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import ast
        from pathlib import Path
        from typing import Any

        from fastapi import Depends, HTTPException, status
        from fastapi.responses import JSONResponse

        from server.entities.agent import AgentRunCreateRequest
        from server.service.agent_run_service import AgentRunConflictError

        tree = ast.parse(Path("server/router/agent_router.py").read_text())
        target_names = {
            "create_agent_run",
            "_conflict_response",
            "cancel_queued_agent_run_request",
            "steer_queued_agent_run_request",
        }
        nodes = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef | ast.FunctionDef) and n.name in target_names]
        for node in nodes:
            node.decorator_list = []
        self.module = dict(
            AgentRunCreateRequest=AgentRunCreateRequest, AuthenticatedUser=Any, AsyncSession=Any,
            Depends=Depends, get_db=Mock(), HTTPException=HTTPException, JSONResponse=JSONResponse,
            status=status, config=SimpleNamespace(enable_run_queue=True), AgentRunConflictError=AgentRunConflictError,
            create_agent_run_service=AsyncMock(),
            cancel_queued_agent_run_request_service=AsyncMock(),
            steer_queued_agent_run_request_service=AsyncMock(),
        )
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "router", "exec"), self.module)

    async def test_dispatch_policy_defaults_and_http_202_responses(self):
        import json
        from pydantic import ValidationError

        request_model = self.module["AgentRunCreateRequest"]
        default_req = request_model(agent_id="a", thread_id="t")
        self.assertEqual(default_req.dispatch_policy, "enqueue")
        self.assertEqual(request_model(agent_id="a", thread_id="t", dispatch_policy="reject").dispatch_policy, "reject")
        with self.assertRaises(ValidationError):
            request_model(agent_id="a", thread_id="t", dispatch_policy="queue")

        enqueue_response = {"run_id": None, "stream_url": None, "status": "queued", "dispatch_policy": "enqueue", "request_id": "q1", "queue_position": 1, "steering_run_id": None}
        self.module["create_agent_run_service"].return_value = enqueue_response
        result = await self.module["create_agent_run"](default_req, SimpleNamespace(uid="u"), object())
        self.assertEqual(result.status_code, 202)
        self.assertEqual(json.loads(result.body), enqueue_response)
        self.assertIsNone(json.loads(result.body)["steering_run_id"])

        steer_response = {"run_id": None, "stream_url": None, "status": "queued", "dispatch_policy": "steer", "request_id": "q2", "queue_position": 1, "steering_run_id": "r"}
        self.module["create_agent_run_service"].return_value = steer_response
        result = await self.module["create_agent_run"](
            request_model(agent_id="a", thread_id="t", dispatch_policy="steer"),
            SimpleNamespace(uid="u"), object(),
        )
        self.assertEqual(result.status_code, 202)
        self.assertEqual(json.loads(result.body), steer_response)
        self.assertEqual(json.loads(result.body)["steering_run_id"], "r")

    async def test_cancel_and_steer_queued_request_routes(self):
        import json
        from fastapi import HTTPException
        conflict_cls = self.module["AgentRunConflictError"]

        self.module["cancel_queued_agent_run_request_service"].return_value = {"request_id": "q1", "status": "cancelled"}
        self.assertEqual(
            await self.module["cancel_queued_agent_run_request"]("q1", SimpleNamespace(uid="u"), object()),
            {"request_id": "q1", "status": "cancelled"},
        )

        self.module["cancel_queued_agent_run_request_service"].side_effect = LookupError("等待区请求不存在")
        with self.assertRaises(HTTPException) as missing:
            await self.module["cancel_queued_agent_run_request"]("q1", SimpleNamespace(uid="u"), object())
        self.assertEqual(missing.exception.status_code, 404)

        self.module["cancel_queued_agent_run_request_service"].side_effect = conflict_cls("请求已开始执行", run_id="run-9")
        conflict_resp = await self.module["cancel_queued_agent_run_request"]("q1", SimpleNamespace(uid="u"), object())
        self.assertEqual(conflict_resp.status_code, 409)
        self.assertEqual(json.loads(conflict_resp.body), {"detail": "请求已开始执行", "run_id": "run-9"})

        self.module["steer_queued_agent_run_request_service"].return_value = {
            "run_id": None, "thread_id": "t", "status": "queued", "dispatch_policy": "steer",
            "request_id": "q1", "queue_position": 1, "steering_run_id": "run-active", "stream_url": None,
        }
        steered = await self.module["steer_queued_agent_run_request"]("q1", SimpleNamespace(uid="u"), object())
        self.assertEqual(steered.status_code, 202)
        self.assertEqual(json.loads(steered.body)["steering_run_id"], "run-active")

        self.module["steer_queued_agent_run_request_service"].return_value = SimpleNamespace(
            id="run-new", thread_id="t", agent_status="pending", request_id="q1",
        )
        promoted = await self.module["steer_queued_agent_run_request"]("q1", SimpleNamespace(uid="u"), object())
        self.assertEqual(promoted["run_id"], "run-new")
        self.assertEqual(promoted["stream_url"], "/api/agent/runs/run-new/events?thread_id=t")


class SteerGraceTest(unittest.IsolatedAsyncioTestCase):
    async def test_expired_steer_wakes_cancellable_stream_without_losing_lease(self):
        from server import worker
        controller = worker.AgentRunController("run-1", worker_id="w")
        with (
            patch.object(worker.asyncio, "sleep", AsyncMock()),
            patch.object(worker, "_renew_run_lease", AsyncMock(return_value=True)),
            patch.object(worker.postgres_manager, "get_async_session_context", fake_session),
            patch.object(worker, "AgentRunRequestQueueRepository", return_value=SimpleNamespace(has_expired_steer_for_run=AsyncMock(return_value=True))),
        ):
            await controller._heartbeat_lease()
        self.assertTrue(await controller.has_cancel_signal())
        self.assertTrue(controller.steer_cancelled)
        self.assertFalse(controller.lease_lost)


class WorkerTwoModeDispatchTest(unittest.IsolatedAsyncioTestCase):
    async def test_reconcile_and_set_run_terminal_do_not_dispatch_queue(self):
        from server import worker
        fake_repo = SimpleNamespace(
            reconcile_expired_leases=AsyncMock(return_value=[SimpleNamespace(id="r1", thread_id="t1", agent_status="failed")]),
            recover_unclaimed_pending_runs=AsyncMock(return_value=([SimpleNamespace(id="r-pending", thread_id="t1")], [SimpleNamespace(id="r2", thread_id="t1")])),
            last_cascaded_signal_run_ids=[],
            set_agent_terminal=AsyncMock(return_value=(SimpleNamespace(id="r1", thread_id="t1", agent_status="completed"), True)),
        )
        with (
            patch.object(worker.postgres_manager, "get_async_session_context", fake_session),
            patch.object(worker, "AgentRunRepository", return_value=fake_repo),
            patch.object(worker, "dispatch_next_queued_request", AsyncMock()) as dispatch_mock,
            patch.object(worker, "enqueue_agent_run", AsyncMock()) as enqueue_mock,
        ):
            await worker.reconcile_expired_run_leases(terminate_active=True)
            enqueue_mock.assert_awaited_once_with("r-pending")
            dispatch_mock.assert_not_awaited()
            await worker.set_run_terminal("r1", status="completed", worker_id="w1")
            dispatch_mock.assert_not_awaited()

    async def test_process_agent_run_two_mode_dispatch_and_non_dispatch_outcomes(self):
        import asyncio
        from server import worker

        async def run_case(*, chunks=None, stream_error=None, final_status="completed", changed=True, steer_cancelled=False, cancelled=False, dispatch_side_effect=None):
            run = SimpleNamespace(
                id="run-1", agent_status="queued", uid="u1", agent_id="leader",
                thread_id="thread-1", request_id="req-1", run_type="chat",
                trigger_message_id=1, created_by_run_id=None, run_metadata={},
            )
            controller = SimpleNamespace(
                start=Mock(), close=AsyncMock(),
                is_cancelled=AsyncMock(return_value=cancelled),
                lease_lost=False, steer_cancelled=steer_cancelled,
            )

            async def fake_stream(**_kwargs):
                if stream_error is not None:
                    raise stream_error
                for item in (chunks or []):
                    yield item

            async def passthrough(iterator, **_kwargs):
                async for item in iterator:
                    yield item

            dispatch_mock = AsyncMock(side_effect=dispatch_side_effect)
            with (
                patch.object(worker, "_get_agent_run", AsyncMock(return_value=run)),
                patch.object(worker, "_get_agent_input_msg", AsyncMock(return_value=SimpleNamespace(content="hi", message_type="text", image_content=None, msg_metadata={}))),
                patch.object(worker, "_get_user", AsyncMock(return_value=SimpleNamespace(uid="u1"))),
                patch.object(worker, "build_agent_input_msg", Mock(return_value="input")),
                patch.object(worker, "set_run_running", AsyncMock(return_value=run)),
                patch.object(worker, "AgentRunController", return_value=controller),
                patch.object(worker, "StreamEventSmoother", return_value=SimpleNamespace(append=AsyncMock(), release=AsyncMock())),
                patch.object(worker, "stream_agent_response", side_effect=lambda **kwargs: fake_stream(**kwargs)),
                patch.object(worker, "_cancellable_stream", new=passthrough),
                patch.object(worker, "_normalize_steam_agent_chunk", side_effect=lambda c: [c]),
                patch.object(worker, "reslove_thread_id", side_effect=lambda _c, tid: tid),
                patch.object(worker, "write_stream_event", AsyncMock()),
                patch.object(worker, "write_end_stream_event", AsyncMock()),
                patch.object(worker, "_finalize_run", AsyncMock(return_value=(final_status, changed))) as finalize_mock,
                patch.object(worker, "dispatch_next_queued_request", dispatch_mock),
            ):
                await worker.process_agent_run({"worker_id": "w1"}, "run-1")
            return dispatch_mock, finalize_mock

        # 1. 自然 completed 且 changed=True -> 触发派发
        dispatch_mock, _ = await run_case(chunks=[{"status": "finished"}], final_status="completed", changed=True)
        dispatch_mock.assert_awaited_once_with("thread-1")

        # 2. Turn 边界 steered (stop_reason="steered") 且 changed=True -> 强制插入派发
        dispatch_mock, _ = await run_case(chunks=[{"status": "finished", "stop_reason": "steered"}], final_status="cancelled", changed=True)
        dispatch_mock.assert_awaited_once_with("thread-1")

        # 3. 宽限期超限 CancelledError 且 steer_cancelled=True -> 强制插入派发
        dispatch_mock, _ = await run_case(stream_error=asyncio.CancelledError(), final_status="cancelled", changed=True, cancelled=True, steer_cancelled=True)
        dispatch_mock.assert_awaited_once_with("thread-1")

        # 4. dispatch_next_queued_request 抛异常不回退把已完成 Run 标成 failed
        dispatch_mock, finalize_mock = await run_case(
            chunks=[{"status": "finished"}], final_status="completed", changed=True,
            dispatch_side_effect=RuntimeError("db temporary glitch"),
        )
        dispatch_mock.assert_awaited_once_with("thread-1")
        self.assertEqual(finalize_mock.await_count, 1)

        # 5. 不触发派发的场景: changed=False / 普通手动取消 / interrupted / error
        for kwargs in (
            dict(chunks=[{"status": "finished"}], final_status="completed", changed=False),
            dict(stream_error=asyncio.CancelledError(), final_status="cancelled", changed=True, cancelled=True, steer_cancelled=False),
            dict(chunks=[{"status": "ask_human", "pending_interrupt": {"name": "ask_user"}}], final_status="interrupted", changed=True),
            dict(chunks=[{"status": "error", "error": "boom"}], final_status="failed", changed=True),
        ):
            dispatch_mock, _ = await run_case(**kwargs)
            dispatch_mock.assert_not_awaited()
