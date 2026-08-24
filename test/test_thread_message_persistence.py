import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import configure_mappers

from server.service import thread_service
from src.database.models import AgentRun, Conversation, Message, ToolCall, User
from src.database.repositories.agent_run_repository import AgentRunRepository
from src.database.repositories.conversation_repository import (
    ConversationRepository,
)


class FakeContext:
    uid = ""
    run_id = ""
    thread_id = ""

    def update_context(self, values: dict) -> None:
        for key, value in values.items():
            setattr(self, key, value)


class ThreadMessagePersistenceTest(unittest.IsolatedAsyncioTestCase):
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
            create_agent_output_message=AsyncMock(side_effect=[SimpleNamespace(id=1), SimpleNamespace(id=2)]),
            create_tool_call=AsyncMock(),
            update_tool_call=AsyncMock(),
        )
        runs = SimpleNamespace(
            set_output_message=AsyncMock(),
        )
        db = SimpleNamespace(commit=AsyncMock())

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
                runtime_context={
                    "uid": "user-1",
                    "run_id": "run-1",
                    "thread_id": "thread-1",
                },
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
        conversations.create_agent_output_message.assert_has_awaits(
            [
                call(conversation_id=7, agent_run_id="run-1", content=""),
                call(conversation_id=7, agent_run_id="run-1", content="42"),
            ]
        )
        runs.set_output_message.assert_has_awaits(
            [
                call(run_id="run-1", output_message_id=1),
                call(run_id="run-1", output_message_id=2),
            ]
        )
        conversations.create_tool_call.assert_awaited_once_with(
            message_id=1,
            tool_call_id="",
            tool_name="add_numbers",
            tool_arguments={"a": 17, "b": 25},
        )
        conversations.update_tool_call.assert_awaited_once_with(
            tool_call_id="",
            tool_result="42",
            status="success",
        )
        db.commit.assert_awaited_once_with()

    async def test_repository_methods_write_tool_and_output_fields(self) -> None:
        session = SimpleNamespace(add=Mock(), flush=AsyncMock())
        conversations = ConversationRepository(session)

        tool_call = await conversations.create_tool_call(
            message_id=3,
            tool_call_id="call-1",
            tool_name="add_numbers",
            tool_arguments={"a": 17, "b": 25},
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

        run = SimpleNamespace(id="run-1", output_message_id=None)
        runs = AgentRunRepository(session)
        runs.get_by_id = AsyncMock(return_value=run)
        await runs.set_output_message(run_id="run-1", output_message_id=9)
        self.assertEqual(9, run.output_message_id)

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
