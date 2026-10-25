import ast
import json
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import configure_mappers

from src.database.models import AgentRun, AgentRunAttempt, Conversation, Message, ToolCall, User
from src.database.repositories.agent_run_repository import AgentRunRepository
from src.database.repositories.conversation_repository import (
    ConversationRepository,
)


def load_message_persistence():
    """直接加载消息保存函数，隔离 Agent 注册和基础设施启动。"""
    path = Path(__file__).resolve().parents[1] / "server/service/thread_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module = ModuleType("isolated_message_persistence")
    module.__dict__.update(
        Any=Any, AsyncSession=Any, BaseAgent=Any, Message=Message,
        AIMessage=AIMessage, ToolMessage=ToolMessage, json=json, logger=Mock(),
        AgentRunRepository=AgentRunRepository, ConversationRepository=ConversationRepository,
    )
    nodes = [node for node in tree.body if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name in {
        "_reslove_interrupt_state",
        "save_ai_message", "save_tool_message", "save_message_from_langgraph_state", "save_partial_message",
    }]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), module.__dict__)
    return module


thread_service = load_message_persistence()


class FakeContext:
    uid = ""
    run_id = ""
    thread_id = ""

    def update_context(self, values: dict) -> None:
        for key, value in values.items():
            setattr(self, key, value)


class ThreadMessagePersistenceTest(unittest.IsolatedAsyncioTestCase):
    async def test_interrupt_terminal_is_saved_before_commit(self):
        graph = SimpleNamespace(aget_state=AsyncMock(return_value=SimpleNamespace(
            values={"messages": []},
        )))
        repository = SimpleNamespace(
            lock_for_output_update=AsyncMock(), set_agent_terminal=AsyncMock(),
        )
        db = SimpleNamespace(commit=AsyncMock())
        calls = Mock()
        calls.attach_mock(repository.set_agent_terminal, "terminal")
        calls.attach_mock(db.commit, "commit")
        payload = {"name": "ask_user", "questions": [{"question": "继续？"}]}
        with patch.object(thread_service, "AgentRunRepository", return_value=repository):
            await thread_service.save_message_from_langgraph_state(
                thread_id="thread-1", run_id="run-1", worker_id="owner-1",
                context=SimpleNamespace(uid="user-1"),
                agent_instance=SimpleNamespace(get_agent=AsyncMock(return_value=graph)),
                db=db, interrupt_chunks=[json.dumps({"pending_interrupt": payload}).encode()],
            )
        self.assertEqual(calls.mock_calls, [
            call.terminal("run-1", status="interrupted", worker_id="owner-1",
                          error=json.dumps(payload, ensure_ascii=False), error_type="ask_user"),
            call.commit(),
        ])

    async def test_foreign_owner_is_rejected_before_saving_any_checkpoint_messages(self):
        graph = SimpleNamespace(aget_state=AsyncMock(return_value=SimpleNamespace(
            values={"messages": [AIMessage(content="foreign output")]},
        )))
        repository = SimpleNamespace(lock_for_output_update=AsyncMock(
            side_effect=RuntimeError("owner mismatch"),
        ))
        db = SimpleNamespace(commit=AsyncMock())
        with (
            patch.object(thread_service, "AgentRunRepository", return_value=repository),
            patch.object(thread_service, "save_ai_message", new_callable=AsyncMock) as save_ai,
            patch.object(thread_service, "save_tool_message", new_callable=AsyncMock) as save_tool,
        ):
            with self.assertRaisesRegex(RuntimeError, "owner mismatch"):
                await thread_service.save_message_from_langgraph_state(
                    thread_id="thread-1", run_id="run-1", worker_id="foreign-owner",
                    context=SimpleNamespace(uid="user-1"),
                    agent_instance=SimpleNamespace(get_agent=AsyncMock(return_value=graph)), db=db,
                )
        save_ai.assert_not_awaited()
        save_tool.assert_not_awaited()
        db.commit.assert_not_awaited()

    def _partial_repository(self, message=None, *, lock_error=None, terminal=(None, False)):
        run_repo = SimpleNamespace(
            lock_output_persistence=(
                AsyncMock(side_effect=lock_error)
                if lock_error is not None
                else AsyncMock(return_value=SimpleNamespace(id="run-1"))
            ),
            set_output_message=AsyncMock(),
            set_agent_terminal=AsyncMock(return_value=terminal),
        )
        conv_repo = SimpleNamespace(
            session=SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock()),
            add_message_by_thread_id=AsyncMock(return_value=message),
        )
        return run_repo, conv_repo

    async def test_partial_message_saves_streamed_text_and_error_metadata(self) -> None:
        message = SimpleNamespace(id=11)
        run_repo, conv_repo = self._partial_repository(message)
        with patch.object(thread_service, "AgentRunRepository", return_value=run_repo):
            result = await thread_service.save_partial_message(
                conv_repo, "thread-1",
                uid="user-1",
                full_msg=AIMessage(content="部分输出"),
                error_message="Error streaming messages: boom",
                error_type="unexpected_error",
                run_id="run-1",
                request_id="request-1",
                worker_id="owner-1",
            )

        self.assertIs(result, message)
        kwargs = conv_repo.add_message_by_thread_id.await_args.kwargs
        self.assertEqual("部分输出", kwargs["content"])
        self.assertEqual("assistant", kwargs["role"])
        self.assertEqual(False, kwargs["commit"])
        metadata = kwargs["msg_metadata"]
        self.assertTrue(metadata["is_error"])
        self.assertEqual("unexpected_error", metadata["error_type"])
        self.assertEqual("Error streaming messages: boom", metadata["error_message"])
        # 消息自身 dump 合并进 metadata，供调试面板还原上下文。
        self.assertEqual("部分输出", metadata["content"])
        run_repo.set_output_message.assert_awaited_once_with(
            run_id="run-1", output_message_id=11, worker_id="owner-1",
        )
        conv_repo.session.commit.assert_awaited_once()

    async def test_partial_message_without_run_commits_in_repository(self) -> None:
        message = SimpleNamespace(id=12)
        _run_repo, conv_repo = self._partial_repository(message)
        result = await thread_service.save_partial_message(
            conv_repo, "thread-1", uid="user-1", error_type="interrupted",
        )

        self.assertIs(result, message)
        kwargs = conv_repo.add_message_by_thread_id.await_args.kwargs
        self.assertEqual("", kwargs["content"])
        self.assertEqual(True, kwargs["commit"])
        conv_repo.session.commit.assert_not_awaited()

    async def test_partial_message_interrupt_run_commits_terminal_in_same_transaction(self) -> None:
        message = SimpleNamespace(id=13)
        run_repo, conv_repo = self._partial_repository(
            message, terminal=(SimpleNamespace(id="run-1"), True),
        )
        with patch.object(thread_service, "AgentRunRepository", return_value=run_repo):
            await thread_service.save_partial_message(
                conv_repo, "thread-1", uid="user-1",
                full_msg=AIMessage(content="半句"),
                error_type="interrupted",
                run_id="run-1", request_id="request-1", worker_id="owner-1",
                interrupt_run=True,
            )

        run_repo.set_agent_terminal.assert_awaited_once_with(
            "run-1", status="interrupted", worker_id="owner-1",
        )
        conv_repo.session.commit.assert_awaited_once()

    async def test_partial_message_interrupt_run_requires_terminal_commit(self) -> None:
        run_repo, conv_repo = self._partial_repository(
            SimpleNamespace(id=14), terminal=(SimpleNamespace(id="run-1"), False),
        )
        with patch.object(thread_service, "AgentRunRepository", return_value=run_repo):
            with self.assertRaises(ValueError):
                await thread_service.save_partial_message(
                    conv_repo, "thread-1", uid="user-1",
                    full_msg=AIMessage(content="半句"),
                    run_id="run-1", request_id="request-1", worker_id="owner-1",
                    interrupt_run=True,
                )
        conv_repo.session.rollback.assert_awaited_once()
        conv_repo.session.commit.assert_not_awaited()

    async def test_partial_message_returns_none_for_foreign_owner(self) -> None:
        run_repo, conv_repo = self._partial_repository(
            SimpleNamespace(id=15), lock_error=RuntimeError("owner mismatch"),
        )
        with patch.object(thread_service, "AgentRunRepository", return_value=run_repo):
            result = await thread_service.save_partial_message(
                conv_repo, "thread-1", uid="user-1",
                full_msg=AIMessage(content="半句"),
                run_id="run-1", request_id="request-1", worker_id="foreign-owner",
            )

        self.assertIsNone(result)
        conv_repo.add_message_by_thread_id.assert_not_awaited()
        conv_repo.session.rollback.assert_awaited_once()

    async def test_checkpoint_messages_are_saved_in_state_order(self) -> None:
        messages = [
            HumanMessage(content="调用 add_numbers 计算 17 + 25"),
            AIMessage(
                content=[
                    {
                        "type": "tool_call",
                        "id": "",
                        "name": "add_numbers",
                        "args": {"a": 17, "b": 25},
                    }
                ],
                tool_calls=[
                    {
                        "id": "",
                        "name": "add_numbers",
                        "args": {"a": 17, "b": 25},
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="42",
                tool_call_id="",
                name="add_numbers",
                status="success",
            ),
            AIMessage(content=[{"index": 0, "text": "42", "type": "text"}]),
        ]
        graph = SimpleNamespace(aget_state=AsyncMock(return_value=SimpleNamespace(values={"messages": messages})))
        agent = SimpleNamespace(
            agent_context=FakeContext,
            get_agent=AsyncMock(return_value=graph),
        )
        conversations = SimpleNamespace(
            get_conversation_by_thread_id_for_user=AsyncMock(return_value=SimpleNamespace(id=7)),
            get_message_by_langgraph_id=AsyncMock(return_value=None),
            add_message_by_thread_id=AsyncMock(
                side_effect=[
                    SimpleNamespace(id=1, agent_run_id="run-1"),
                    SimpleNamespace(id=2, agent_run_id="run-1"),
                ]
            ),
            add_tool_call=AsyncMock(),
            update_tool_call=AsyncMock(),
        )
        runs = SimpleNamespace(
            lock_for_output_update=AsyncMock(return_value=SimpleNamespace(id="run-1")),
            set_output_message=AsyncMock(),
        )
        db = SimpleNamespace(commit=AsyncMock())
        # FIXEME: state 持久化与 interrupt handler 都使用完整 Agent context。
        context = FakeContext()
        context.update_context({"uid": "user-1", "thread_id": "thread-1"})

        with (
            patch.object(
                thread_service,
                "ConversationRepository",
                return_value=conversations,
            ),
            patch.object(
                thread_service,
                "AgentRunRepository",
                return_value=runs,
            ),
        ):
            await thread_service.save_message_from_langgraph_state(
                agent_instance=agent,
                context=context,
                thread_id="thread-1",
                run_id="run-1",
                worker_id="owner-1",
                db=db,
            )

        graph.aget_state.assert_awaited_once_with(
            {
                "configurable": {
                    "thread_id": "thread-1",
                    "uid": "user-1",
                }
            },
        )
        conversations.add_message_by_thread_id.assert_has_awaits(
            [
                call(
                    thread_id="thread-1",
                    user_id="user-1",
                    agent_run_id="run-1",
                    content="",
                    role="ai",
                    msg_metadata=None,
                ),
                call(
                    thread_id="thread-1",
                    user_id="user-1",
                    agent_run_id="run-1",
                    content="42",
                    role="ai",
                    msg_metadata=None,
                ),
            ]
        )
        runs.lock_for_output_update.assert_awaited_once_with("run-1", worker_id="owner-1")
        runs.set_output_message.assert_awaited_once_with(
            run_id="run-1",
            output_message_id=2,
            worker_id="owner-1",
        )
        conversations.add_tool_call.assert_awaited_once_with(
            message_id=1,
            tool_call_id="",
            tool_name="add_numbers",
            tool_arguments={"a": 17, "b": 25},
            status="pending",
        )
        conversations.update_tool_call.assert_not_awaited()
        db.commit.assert_awaited_once_with()

    async def test_repository_methods_write_tool_and_output_fields(self) -> None:
        # FIXEME: add_tool_call 会先按外部 Tool Call ID 检查幂等记录。
        session = SimpleNamespace(
            add=Mock(),
            flush=AsyncMock(),
            execute=AsyncMock(
                return_value=SimpleNamespace(
                    scalar_one_or_none=lambda: None, scalar=lambda: None
                )
            ),
        )
        conversations = ConversationRepository(session)

        tool_call = await conversations.add_tool_call(
            message_id=3,
            tool_call_id="call-1",
            tool_name="add_numbers",
            tool_arguments={"a": 17, "b": 25},
            status="pending",
        )
        self.assertEqual({"a": 17, "b": 25}, tool_call.tool_arguments)
        session.add.assert_called_once_with(tool_call)

        session.execute = AsyncMock(return_value=SimpleNamespace(scalar_one=lambda: tool_call))
        await conversations.update_tool_call(
            tool_call_id="call-1",
            tool_result="42",
            status="success",
        )
        self.assertEqual("42", tool_call.tool_result)
        self.assertEqual("success", tool_call.status)

        run = SimpleNamespace(id="run-1", output_message_id=None, worker_id="owner-1", agent_status="running")
        runs = AgentRunRepository(session)
        runs._lock_update = AsyncMock(return_value=run)
        await runs.set_output_message(run_id="run-1", output_message_id=9, worker_id="owner-1")
        self.assertEqual(9, run.output_message_id)

        output_session = SimpleNamespace(
            add=Mock(),
            flush=AsyncMock(),
            execute=AsyncMock(
                return_value=SimpleNamespace(
                    scalar_one_or_none=lambda: SimpleNamespace(id=7),
                    scalar=lambda: None,
                )
            ),
        )
        output_message = await ConversationRepository(
            output_session
        ).add_message_by_thread_id(
            thread_id="thread-1",
            user_id="user-1",
            agent_run_id="run-1",
            content="42",
            role="ai",
        )
        self.assertEqual(7, output_message.conversation_id)
        self.assertEqual("ai", output_message.role)
        output_session.add.assert_called_once_with(output_message)

    async def test_result_query_uses_output_message_pointer(self) -> None:
        result_message = SimpleNamespace(id=9, content="42")
        session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: result_message)))

        result = await ConversationRepository(session).get_run_result_message("run-1")

        self.assertIs(result_message, result)
        statement = session.execute.await_args.args[0]
        self.assertIn(
            "agent_run.output_message_id = message.id",
            str(statement),
        )


class MessagePersistenceSchemaTest(unittest.TestCase):
    def test_message_and_tool_call_foreign_keys_keep_delete_chain(self) -> None:
        configure_mappers()

        self.assertNotIn("tool_sequence", ToolCall.__table__.c)
        self.assertTrue(ToolCall.__table__.c.status.nullable)
        self.assertEqual(
            "CASCADE",
            next(iter(Message.__table__.c.conversation_id.foreign_keys)).ondelete,
        )
        self.assertEqual(
            "CASCADE",
            next(iter(ToolCall.__table__.c.message_id.foreign_keys)).ondelete,
        )
        self.assertEqual(
            "SET NULL",
            next(iter(AgentRun.__table__.c.output_message_id.foreign_keys)).ondelete,
        )

        engine = create_engine("sqlite://")

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        for table in (
            User.__table__,
            Conversation.__table__,
            AgentRun.__table__,
            AgentRunAttempt.__table__,
            Message.__table__,
            ToolCall.__table__,
        ):
            table.create(engine)

        with engine.begin() as connection:
            rows = (
                (
                    User.__table__,
                    {
                        "id": 1,
                        "email": "user@example.com",
                        "uid": "user-1",
                        "password_hash": "hash",
                    },
                ),
                (
                    Conversation.__table__,
                    {
                        "id": 7,
                        "uid": "user-1",
                        "thread_id": "thread-1",
                        "agent_id": "test-agent",
                        "title": "test",
                    },
                ),
                (
                    AgentRun.__table__,
                    {
                        "id": "run-1",
                        "thread_id": "thread-1",
                        "conversation_id": 7,
                        "uid": "user-1",
                        "agent_id": "test-agent",
                        "agent_status": "completed",
                    },
                ),
                (
                    Message.__table__,
                    {
                        "id": 9,
                        "conversation_id": 7,
                        "agent_run_id": "run-1",
                        "role": "assistant",
                        "content": "42",
                    },
                ),
                (
                    ToolCall.__table__,
                    {
                        "id": 11,
                        "message_id": 9,
                        "tool_call_id": "",
                        "tool_name": "add_numbers",
                    },
                ),
            )
            for table, values in rows:
                connection.execute(table.insert().values(values))

            connection.execute(AgentRun.__table__.update().where(AgentRun.__table__.c.id == "run-1").values(output_message_id=9))

            connection.execute(Conversation.__table__.delete().where(Conversation.__table__.c.id == 7))

            for table in (
                AgentRun.__table__,
                Message.__table__,
                ToolCall.__table__,
            ):
                self.assertEqual(
                    0,
                    connection.scalar(select(func.count()).select_from(table)),
                )

        engine.dispose()


if __name__ == "__main__":
    unittest.main()
