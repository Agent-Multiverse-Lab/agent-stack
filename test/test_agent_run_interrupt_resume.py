"""多问题 Resume 的请求、Service、checkpoint 和 Worker 接线验证。"""

import asyncio
import copy
import json
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import ValidationError

from server.entities.agent import AgentRunResumeRequest
from server.entities.thread import InteractionRequired
from server.service import agent_run_service, thread_service
from server import worker
from test.test_ask_user_tool import ask_user

QUESTIONS = [
    {"question_id": "database", "question": "请选择数据库", "options": [
        {"label": "PostgreSQL", "value": "postgresql"}, {"label": "SQLite", "value": "sqlite"}]},
    {"question_id": "environment", "question": "请选择环境", "options": [
        {"label": "本地部署", "value": "local"}, {"label": "云端部署", "value": "cloud"}]},
]
ANSWERS = {"database": "postgresql", "environment": "local"}


class ResumeRepository:
    def __init__(self):
        self.parent = SimpleNamespace(
            id="parent-run", uid="user-1", thread_id="thread-1", conversation_id=7,
            agent_id="LeaderAgent", agent_status="interrupted",
            run_metadata={"model": "parent-model", "interrupt": {"kind": "ask_user", "questions": copy.deepcopy(QUESTIONS)}},
        )
        self.existing = None
        self.create_arguments = None

    async def get_by_id_for_user(self, **values):
        return self.parent if values["uid"] == self.parent.uid else None

    async def get_for_resume_for_update(self, **_values):
        return self.parent

    async def get_resume_child(self, _parent_run_id):
        return self.existing

    async def create_run(self, **values):
        self.create_arguments = values
        return SimpleNamespace(id=values["run_id"], **{key: value for key, value in values.items() if key != "run_id"})


class ResumeRequestTest(unittest.TestCase):
    def test_answers_request_and_thread_response(self):
        request = AgentRunResumeRequest(thread_id="thread-1", thread_metadata={"resume": {"answers": ANSWERS}})
        self.assertEqual(request.thread_metadata["resume"], {"answers": ANSWERS})
        response = InteractionRequired(kind="ask_user", parent_run_id="parent-run", questions=QUESTIONS)
        self.assertEqual(response.model_dump()["questions"], QUESTIONS)

    def test_invalid_answer_types_and_old_answer_rejected(self):
        for resume in ({"answer": "postgresql"}, {"answers": {}}, {"answers": []}, {"answers": {"database": 1}}):
            with self.subTest(resume=resume), self.assertRaises(ValidationError):
                AgentRunResumeRequest(thread_id="thread-1", thread_metadata={"resume": resume})


class ResumeServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.repo = ResumeRepository()
        self.db = SimpleNamespace(commit=AsyncMock())
        self.enqueue = AsyncMock()
        self.repo_patch = patch.object(agent_run_service, "AgentRunRepository", return_value=self.repo)
        self.enqueue_patch = patch.object(agent_run_service, "enqueue_agent_run", self.enqueue)
        self.repo_patch.start()
        self.enqueue_patch.start()
        self.addCleanup(self.repo_patch.stop)
        self.addCleanup(self.enqueue_patch.stop)

    async def submit(self, answers=None, uid="user-1", thread_id="thread-1", request_id="request-1"):
        return await agent_run_service.create_resume_agent_run_service(
            db=self.db, current_user=SimpleNamespace(uid=uid), interrupted_run_id="parent-run",
            thread_id=thread_id, thread_metadata={"request_id": request_id, "model": "injected-model",
                                                "resume": {"answers": ANSWERS if answers is None else answers}},
        )

    async def test_new_run_preserves_parent_identity_and_model(self):
        run = await self.submit()
        created = self.repo.create_arguments
        self.assertNotEqual(run.id, "parent-run")
        self.assertEqual(created["parent_run_id"], "parent-run")
        self.assertEqual(created["run_type"], "resume")
        self.assertIsNone(created["trigger_message_id"])
        self.assertEqual(created["run_metadata"]["resume"], {"answers": ANSWERS})
        self.assertEqual(created["run_metadata"]["model"], "parent-model")
        self.assertEqual(self.repo.parent.agent_status, "interrupted")
        self.enqueue.assert_awaited_once_with(run.id)

    async def test_absent_parent_model_does_not_accept_request_model(self):
        self.repo.parent.run_metadata.pop("model")
        await self.submit()
        self.assertNotIn("model", self.repo.create_arguments["run_metadata"])

    async def test_missing_extra_and_invalid_answers(self):
        for answers in ({}, {"database": "postgresql"}, {**ANSWERS, "extra": "x"},
                        {**ANSWERS, "database": "PostgreSQL"}, {**ANSWERS, "database": " postgresql "}):
            with self.subTest(answers=answers), self.assertRaises(ValueError):
                await self.submit(answers)
        self.enqueue.assert_not_awaited()

    async def test_invalid_parent_questions(self):
        for questions in ([], [QUESTIONS[0], QUESTIONS[0]], [None],
                          [{**QUESTIONS[0], "options": ["postgresql"]}]):
            self.repo.parent.run_metadata["interrupt"]["questions"] = questions
            with self.subTest(questions=questions), self.assertRaises(ValueError):
                await self.submit()

    async def test_ownership_thread_and_status(self):
        with self.assertRaises(LookupError):
            await self.submit(uid="another-user")
        with self.assertRaises(agent_run_service.AgentRunConflictError):
            await self.submit(thread_id="another-thread")
        self.repo.parent.agent_status = "completed"
        with self.assertRaises(agent_run_service.AgentRunConflictError):
            await self.submit()

    async def test_idempotency_compares_answers(self):
        self.repo.existing = SimpleNamespace(id="resume-run", request_id="request-1",
                                             run_metadata={"resume": {"answers": ANSWERS}})
        self.assertIs(await self.submit(), self.repo.existing)
        with self.assertRaises(agent_run_service.AgentRunConflictError):
            await self.submit({**ANSWERS, "database": "sqlite"})
        with self.assertRaises(agent_run_service.AgentRunConflictError):
            await self.submit(request_id="request-2")
        self.enqueue.assert_not_awaited()


class FixtureContext(SimpleNamespace):
    def update_context(self, values):
        self.__dict__.update(values)


class FixtureAgent:
    agent_context = FixtureContext

    def __init__(self, graph):
        self.graph = graph
        self.command = None

    async def get_agent(self, _context):
        return self.graph

    async def stream_message_by_resume(self, command, runtime_context):
        self.command = command
        await self.graph.ainvoke(command, {"configurable": {
            "thread_id": runtime_context["thread_id"], "uid": runtime_context["uid"]}})
        yield "messages", ({"event": "message-start", "id": "resume-output"}, {})
        yield "messages", ({"event": "content-block-delta", "delta": {"type": "text-delta", "text": "已继续"}}, {})


class ResumeStreamTest(unittest.IsolatedAsyncioTestCase):
    async def graph(self, rounds=1):
        async def node(state):
            completed = sum(isinstance(message, ToolMessage) for message in state["messages"])
            if completed >= rounds:
                return {"messages": [AIMessage(content="完成")]}
            return {"messages": [AIMessage(content="", tool_calls=[{
                "name": ask_user.name, "args": {"questions": QUESTIONS},
                "id": f"ask-{completed + 1}", "type": "tool_call"}])]}
        builder = StateGraph(MessagesState)
        builder.add_node("agent", node)
        builder.add_node("tools", ToolNode([ask_user]))
        builder.add_edge(START, "agent")
        builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", "__end__": END})
        builder.add_edge("tools", "agent")
        graph = builder.compile(checkpointer=InMemorySaver())
        await graph.ainvoke({"messages": [HumanMessage(content="开始")]}, self.config)
        return graph

    async def asyncSetUp(self):
        self.config = {"configurable": {"thread_id": "thread-1", "uid": "user-1"}}
        self.saved = AsyncMock()
        self.require = AsyncMock()
        for name, value in (("save_message_from_langgraph_state", self.saved), ("_require_thread", self.require)):
            p = patch.object(thread_service, name, value)
            p.start()
            self.addCleanup(p.stop)

    async def consume(self, agent, **overrides):
        values = dict(resume_input=ANSWERS, thread_id="thread-1",
                      runtime_metadata={"run_id": "resume-run", "request_id": "request-1"},
                      current_user=SimpleNamespace(uid="user-1"), db=SimpleNamespace())
        values.update(overrides)
        with patch.object(thread_service.agent_manager, "get_agent", return_value=agent) as get_agent:
            chunks = [json.loads(chunk) async for chunk in thread_service.resume_agent_response(**values)]
        if agent is not None:
            get_agent.assert_called_once_with("LeaderAgent")
        return chunks

    async def test_real_checkpoint_resumes_all_answers(self):
        graph = await self.graph()
        agent = FixtureAgent(graph)
        chunks = await self.consume(agent)
        self.assertEqual(chunks[-1]["status"], "finished")
        self.assertIs(agent.command.resume, ANSWERS)
        state = await graph.aget_state(self.config)
        self.assertFalse(state.interrupts)
        result = next(message for message in state.values["messages"] if isinstance(message, ToolMessage))
        self.assertEqual(result.tool_call_id, "ask-1")
        self.assertEqual(json.loads(result.content), ANSWERS)
        self.saved.assert_awaited_once()
        self.assertEqual(self.saved.await_args.kwargs["run_id"], "resume-run")

    async def test_again_interrupt_uses_unchanged_handler(self):
        graph = await self.graph(rounds=2)
        chunks = await self.consume(FixtureAgent(graph))
        self.assertEqual(chunks[-1]["status"], "ask_human")
        self.assertEqual(chunks[-1]["pending_interrupt"]["questions"], QUESTIONS)
        self.assertEqual(chunks[-1]["pending_interrupt"]["run_id"], "resume-run")
        self.assertNotIn("finished", [chunk["status"] for chunk in chunks])
        self.saved.assert_awaited_once()

    async def test_missing_checkpoint_fails_without_replay(self):
        agent = FixtureAgent(SimpleNamespace(aget_state=AsyncMock(return_value=SimpleNamespace(tasks=()))))
        chunks = await self.consume(agent)
        self.assertEqual(chunks[-1]["status"], "error")
        self.assertIn("checkpoint", chunks[-1]["error"])
        self.assertIsNone(agent.command)
        self.saved.assert_not_awaited()

    async def test_initialization_failure_uses_error_chunk(self):
        self.require.side_effect = LookupError("thread missing")
        chunks = await self.consume(None)
        self.assertEqual(chunks, [dict(request_id="request-1", response=None, thread_id="thread-1",
                                      status="error", error="thread missing", error_type="LookupError")])

    async def test_save_failure_keeps_original_error(self):
        graph = await self.graph()
        self.saved.side_effect = RuntimeError("checkpoint save failed")
        @asynccontextmanager
        async def session():
            yield SimpleNamespace()
        with patch.object(thread_service.postgres_manager, "get_async_session_context", session), patch.object(
            thread_service, "save_interrupt_message", AsyncMock(side_effect=RuntimeError("fallback failed"))
        ) as fallback:
            chunks = await self.consume(FixtureAgent(graph))
        self.assertEqual(chunks[-1]["status"], "error")
        self.assertEqual(chunks[-1]["error"], "checkpoint save failed")
        self.assertEqual(fallback.await_args.kwargs["accumulated_msg"].content, "已继续")


class NormalStreamFinalizationTest(unittest.IsolatedAsyncioTestCase):
    async def consume(self, interrupted, save_error=None):
        order = []
        async def events(*_args, **_kwargs):
            return
            yield
        async def handler(**kwargs):
            order.append("detect")
            if interrupted:
                yield kwargs["chunk_iterator"](
                    status="ask_human", pending_interrupt={"questions": QUESTIONS},
                )
        async def save(**_kwargs):
            order.append("save")
            if save_error:
                raise save_error
        agent = SimpleNamespace(agent_context=FixtureContext, stream_messages_with_event=events)
        with patch.object(thread_service, "_build_agent_runtime", AsyncMock(return_value=(SimpleNamespace(slug="LeaderAgent"), agent))), patch.object(
            thread_service, "_check_conv_status", AsyncMock()
        ), patch.object(thread_service, "check_agent_interrupt_handler", handler), patch.object(
            thread_service, "save_message_from_langgraph_state", side_effect=save
        ) as saved, patch.object(thread_service, "_reslove_interrupt_state", wraps=thread_service._reslove_interrupt_state) as resolve:
            chunks = []
            async for chunk in thread_service.stream_agent_response(
                agent_slug="LeaderAgent", thread_id="thread-1",
                runtime_metadata={"run_id": "parent-run", "request_id": "request-1"},
                thread_input_message=SimpleNamespace(content="开始", image_content=None, langchain_msg=HumanMessage(content="开始")),
                current_user=SimpleNamespace(uid="user-1"), db=SimpleNamespace(),
            ):
                chunks.append(json.loads(chunk))
                order.append(chunks[-1]["status"])
        saved.assert_awaited_once()
        self.assertEqual(resolve.call_count, int(interrupted))
        return chunks, order

    async def test_interrupt_is_emitted_after_checkpoint_save(self):
        chunks, order = await self.consume(True)
        self.assertEqual(order, ["detect", "save", "ask_human"])
        self.assertEqual([chunk["status"] for chunk in chunks], ["ask_human"])

    async def test_normal_finish_follows_save(self):
        _, order = await self.consume(False)
        self.assertEqual(order, ["detect", "save", "finished"])

    async def test_interrupt_save_failure_emits_only_error(self):
        chunks, order = await self.consume(True, RuntimeError("save failed"))
        self.assertEqual(order, ["detect", "save", "error"])
        self.assertEqual([chunk["status"] for chunk in chunks], ["error"])
        self.assertEqual(chunks[0]["error"], "save failed")


class ResumeWorkerTest(unittest.IsolatedAsyncioTestCase):
    async def run_stream(self, chunks, cancelled=False):
        run = SimpleNamespace(agent_status="pending", uid="user-1", agent_id="LeaderAgent",
                              request_id="request-1", thread_id="thread-1", run_type="resume",
                              run_metadata={"resume": {"answers": ANSWERS}})
        @asynccontextmanager
        async def session():
            yield SimpleNamespace()
        async def stream(**kwargs):
            self.assertIs(kwargs["resume_input"], ANSWERS)
            self.assertNotIn("agent_slug", kwargs)
            for chunk in chunks:
                yield json.dumps({"thread_id": "thread-1", **chunk}).encode()
        async def wait_cancel():
            await asyncio.Event().wait()
        controller = SimpleNamespace(start=Mock(), close=AsyncMock(), is_cancelled=AsyncMock(return_value=cancelled),
                                     wait_cancel_signal=wait_cancel)
        finalize = AsyncMock(side_effect=lambda *args, **kwargs: (kwargs["status"], True))
        patches = {
            "_get_agent_run": AsyncMock(return_value=run), "_get_user": AsyncMock(return_value=SimpleNamespace(uid="user-1")),
            "_get_agent_input_msg": AsyncMock(side_effect=AssertionError("Resume must not load HumanMessage")),
            "set_run_running": AsyncMock(return_value=SimpleNamespace(agent_status="running")),
            "AgentRunController": Mock(return_value=controller), "resume_agent_response": stream,
            "_finalize_run": finalize, "write_stream_event": AsyncMock(), "write_end_stream_event": AsyncMock(),
        }
        with patch.multiple(worker, **patches), patch.object(worker.postgres_manager, "get_async_session_context", session):
            await worker.process_agent_run({}, "resume-run")
        controller.close.assert_awaited_once()
        return finalize, patches["write_end_stream_event"]

    async def test_handler_chunk_routes_to_existing_terminal(self):
        payload = {"kind": "ask_user", "questions": QUESTIONS}
        finalize, end = await self.run_stream([{"status": "ask_human", "pending_interrupt": payload}])
        finalize.assert_awaited_once_with("resume-run", thread_id="thread-1", status="interrupted", payload=payload)
        self.assertEqual(end.await_args.args[1]["status"], "interrupted")

    async def test_empty_stream_is_failed_and_cancellation_is_awaited(self):
        finalize, _ = await self.run_stream([])
        self.assertEqual(finalize.await_args.kwargs["status"], "failed")
        finalize, _ = await self.run_stream([], cancelled=True)
        self.assertEqual(finalize.await_args.kwargs["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
