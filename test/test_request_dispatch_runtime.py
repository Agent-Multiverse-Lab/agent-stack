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
            patch.object(steer, "AgentRunRequestRepository", return_value=SimpleNamespace(has_queued_steer_for_thread=should_stop)),
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
            patch.object(steer, "AgentRunRequestRepository", return_value=SimpleNamespace(has_queued_steer_for_thread=AsyncMock(return_value=False))),
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
        nodes = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "create_agent_run"]
        for node in nodes:
            node.decorator_list = []
        self.module = dict(AgentRunCreateRequest=AgentRunCreateRequest, AuthenticatedUser=Any, AsyncSession=Any,
                           Depends=Depends, get_db=Mock(), HTTPException=HTTPException, JSONResponse=JSONResponse,
                           status=status, config=SimpleNamespace(enable_run_queue=True), AgentRunConflictError=AgentRunConflictError,
                           create_agent_run_service=AsyncMock())
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

        enqueue_response = {"run_id": None, "stream_url": None, "status": "queued", "dispatch_policy": "enqueue", "request_id": "q1", "steering_run_id": None}
        self.module["create_agent_run_service"].return_value = enqueue_response
        result = await self.module["create_agent_run"](default_req, SimpleNamespace(uid="u"), object())
        self.assertEqual(result.status_code, 202)
        self.assertEqual(json.loads(result.body), enqueue_response)
        self.assertIsNone(json.loads(result.body)["steering_run_id"])

        steer_response = {"run_id": None, "stream_url": None, "status": "queued", "dispatch_policy": "steer", "request_id": "q2", "steering_run_id": "r"}
        self.module["create_agent_run_service"].return_value = steer_response
        result = await self.module["create_agent_run"](
            request_model(agent_id="a", thread_id="t", dispatch_policy="steer"),
            SimpleNamespace(uid="u"), object(),
        )
        self.assertEqual(result.status_code, 202)
        self.assertEqual(json.loads(result.body), steer_response)
        self.assertEqual(json.loads(result.body)["steering_run_id"], "r")

class SteerGraceTest(unittest.IsolatedAsyncioTestCase):
    async def test_expired_steer_wakes_cancellable_stream_without_losing_lease(self):
        from server import worker
        controller = worker.AgentRunController("run-1", worker_id="w")
        with (
            patch.object(worker.asyncio, "sleep", AsyncMock()),
            patch.object(worker, "_renew_run_lease", AsyncMock(return_value=True)),
            patch.object(worker.postgres_manager, "get_async_session_context", fake_session),
            patch.object(worker, "AgentRunRequestRepository", return_value=SimpleNamespace(has_expired_steer_for_run=AsyncMock(return_value=True))),
        ):
            await controller._heartbeat_lease()
        self.assertTrue(await controller.has_cancel_signal())
        self.assertFalse(controller.lease_lost)
