import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command, interrupt
from pydantic import ValidationError

from server.entities.agent import AgentRunResumeRequest
from server.service import agent_run_service, thread_service


# FIXEME: 第一版仅用于锁定当前 LangGraph interrupt/resume 的真实结构。
@tool
def ask_user(question: str, options: list[str]) -> str:
    """向用户提出一个单选问题。"""

    return str(
        interrupt(
            {
                "kind": "ask_user",
                "question": question,
                "options": options,
            }
        )
    )


class AgentRunInterruptResumeFixtureTest(unittest.IsolatedAsyncioTestCase):
    async def test_interrupt_state_and_resume_tool_message(self) -> None:
        tool_call_id = "ask-user-call-1"
        question = "请选择继续执行所使用的数据库"
        options = ["PostgreSQL", "MySQL"]

        # FIXEME: 用确定性节点隔离模型差异，只验证 LangGraph 运行语义。
        async def agent_node(state: MessagesState) -> dict:
            if any(isinstance(message, ToolMessage) for message in state["messages"]):
                return {"messages": [AIMessage(content="已选择 PostgreSQL")]}
            return {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": ask_user.name,
                                "args": {
                                    "question": question,
                                    "options": options,
                                },
                                "id": tool_call_id,
                                "type": "tool_call",
                            }
                        ],
                    )
                ]
            }

        builder = StateGraph(MessagesState)
        builder.add_node("agent", agent_node)
        builder.add_node("tools", ToolNode([ask_user]))
        builder.add_edge(START, "agent")
        builder.add_conditional_edges(
            "agent",
            tools_condition,
            {"tools": "tools", "__end__": END},
        )
        builder.add_edge("tools", "agent")
        graph = builder.compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "interrupt-fixture"}}

        interrupted_result = await graph.ainvoke(
            {"messages": [HumanMessage(content="开始")]},
            config,
        )
        state = await graph.aget_state(config)

        self.assertIn("__interrupt__", interrupted_result)
        self.assertEqual(len(state.interrupts), 1)
        self.assertEqual(
            state.interrupts[0].value,
            {
                "kind": "ask_user",
                "question": question,
                "options": options,
            },
        )

        resumed_result = await graph.ainvoke(Command(resume="PostgreSQL"), config)
        tool_messages = [
            message
            for message in resumed_result["messages"]
            if isinstance(message, ToolMessage)
        ]

        self.assertEqual(len(tool_messages), 1)
        self.assertEqual(tool_messages[0].tool_call_id, tool_call_id)
        self.assertEqual(tool_messages[0].content, "PostgreSQL")
        self.assertEqual(resumed_result["messages"][-1].content, "已选择 PostgreSQL")

    async def test_interrupt_handler_reads_state_snapshot_interrupts(self) -> None:
        payload = {
            "kind": "ask_user",
            "question": "请选择数据库",
            "options": ["PostgreSQL", "MySQL"],
        }
        graph = SimpleNamespace(
            aget_state=AsyncMock(
                return_value=SimpleNamespace(
                    interrupts=(SimpleNamespace(value=payload),)
                )
            )
        )
        agent = SimpleNamespace(get_agent=AsyncMock(return_value=graph))
        context = SimpleNamespace(uid="user-1", thread_id="thread-1")

        result = await thread_service.check_agent_interrupt_handler(
            agent_instance=agent,
            context=context,
        )

        self.assertEqual(payload, result)
        graph.aget_state.assert_awaited_once_with(
            {
                "configurable": {
                    "thread_id": "thread-1",
                    "uid": "user-1",
                }
            }
        )

    async def test_interrupt_handler_rejects_multiple_interrupts(self) -> None:
        graph = SimpleNamespace(
            aget_state=AsyncMock(
                return_value=SimpleNamespace(
                    interrupts=(SimpleNamespace(), SimpleNamespace())
                )
            )
        )
        agent = SimpleNamespace(get_agent=AsyncMock(return_value=graph))

        with self.assertRaisesRegex(ValueError, "单个"):
            await thread_service.check_agent_interrupt_handler(
                agent_instance=agent,
                context=SimpleNamespace(uid="user-1", thread_id="thread-1"),
            )


# FIXEME: Resume Service 测试固定新 Run、父关联和请求幂等合同。
class ResumeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class ResumeRepository:
    def __init__(self) -> None:
        self.parent = SimpleNamespace(
            id="parent-run",
            uid="user-1",
            thread_id="thread-1",
            conversation_id=7,
            agent_id="leaderagent",
            agent_status="interrupted",
            run_metadata={
                "interrupt": {
                    "kind": "ask_user",
                    "question": "请选择数据库",
                    "options": ["PostgreSQL", "MySQL"],
                }
            },
        )
        self.existing = None
        self.create_arguments = None

    async def get_by_id_for_user(self, **_values):
        return self.parent

    async def get_for_resume_for_update(self, **_values):
        return self.parent

    async def get_resume_child(self, _parent_run_id):
        return self.existing

    async def create_run(self, **values):
        self.create_arguments = values
        return SimpleNamespace(
            id=values["run_id"],
            run_type=values["run_type"],
            parent_run_id=values["parent_run_id"],
            thread_id=values["thread_id"],
            agent_status="pending",
            request_id=values["request_id"],
        )

    async def set_agent_terminal(self, *_args, **_kwargs):
        raise AssertionError("测试不应进入入队失败分支")


class AgentRunResumeServiceTest(unittest.IsolatedAsyncioTestCase):
    def test_resume_request_requires_non_empty_answer(self) -> None:
        with self.assertRaises(ValidationError):
            AgentRunResumeRequest(
                thread_id="thread-1",
                thread_metadata={"resume": {"answer": "  "}},
            )

    async def test_create_resume_run_uses_new_id_without_trigger_message(self) -> None:
        session = ResumeSession()
        repository = ResumeRepository()
        enqueue = AsyncMock()

        with (
            patch.object(
                agent_run_service,
                "AgentRunRepository",
                return_value=repository,
            ),
            patch.object(
                agent_run_service,
                "enqueue_agent_run",
                new=enqueue,
            ),
        ):
            run = await agent_run_service.create_resume_agent_run_service(
                db=session,
                current_user=SimpleNamespace(uid="user-1"),
                interrupted_run_id="parent-run",
                thread_id="thread-1",
                thread_metadata={
                    "request_id": "resume-request-1",
                    "resume": {"answer": "PostgreSQL"},
                },
            )

        self.assertNotEqual("parent-run", run.id)
        self.assertEqual("resume", repository.create_arguments["run_type"])
        self.assertEqual("parent-run", repository.create_arguments["parent_run_id"])
        self.assertIsNone(repository.create_arguments["trigger_message_id"])
        self.assertEqual(
            {"answer": "PostgreSQL"},
            repository.create_arguments["run_metadata"]["resume"],
        )
        enqueue.assert_awaited_once_with(str(run.id))

    async def test_same_request_id_returns_existing_resume_child(self) -> None:
        session = ResumeSession()
        repository = ResumeRepository()
        repository.existing = SimpleNamespace(
            id="resume-run",
            request_id="resume-request-1",
        )
        enqueue = AsyncMock()

        with (
            patch.object(
                agent_run_service,
                "AgentRunRepository",
                return_value=repository,
            ),
            patch.object(
                agent_run_service,
                "enqueue_agent_run",
                new=enqueue,
            ),
        ):
            run = await agent_run_service.create_resume_agent_run_service(
                db=session,
                current_user=SimpleNamespace(uid="user-1"),
                interrupted_run_id="parent-run",
                thread_id="thread-1",
                thread_metadata={
                    "request_id": "resume-request-1",
                    "resume": {"answer": "PostgreSQL"},
                },
            )

        self.assertIs(run, repository.existing)
        self.assertIsNone(repository.create_arguments)
        enqueue.assert_not_awaited()

    async def test_answer_must_match_parent_options(self) -> None:
        session = ResumeSession()
        repository = ResumeRepository()
        with patch.object(
            agent_run_service,
            "AgentRunRepository",
            return_value=repository,
        ):
            with self.assertRaisesRegex(ValueError, "不在父 Run"):
                await agent_run_service.create_resume_agent_run_service(
                    db=session,
                    current_user=SimpleNamespace(uid="user-1"),
                    interrupted_run_id="parent-run",
                    thread_id="thread-1",
                    thread_metadata={
                        "resume": {"answer": "SQLite"},
                    },
                )


if __name__ == "__main__":
    unittest.main()
