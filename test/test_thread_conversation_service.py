"""Thread/Conversation 查询、更新和软删除契约测试。"""

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from server.router.thread_router import router
from server.service.thread_service import ThreadConflictError, ThreadService


class FakeSession:
    """满足 Service 构造要求的空 Session。"""


class FakeConversationRepository:
    """在内存中模拟 Conversation Repository。"""

    def __init__(self, conversation=None) -> None:
        self.conversation = conversation
        self.rows = []
        self.messages = []
        self.last_message_at = None
        self.tree = []
        self.list_arguments = None
        self.deleted_ids = []
        self.created_values = None

    async def create_conversation(self, **values):
        """记录创建参数并返回新对话。"""
        self.created_values = values
        return SimpleNamespace(
            id=1,
            uid=values["uid"],
            thread_id=values["thread_id"],
            agent_id=values["agent_slug"],
            title=values["title"],
            summary=values["summary"],
            conversation_metadata=values["conversation_metadata"],
            created_at=NOW,
            updated_at=NOW,
        )

    async def list_top_level_for_user(self, **values):
        """返回预设对话列表并记录游标参数。"""
        self.list_arguments = values
        return self.rows[: values["limit"]]

    async def get_top_level_for_user(self, **values):
        """返回预设顶层对话。"""
        return self.conversation

    async def list_messages(self, **values):
        """返回预设消息页。"""
        return self.messages[: values["limit"]]

    async def get_last_message_at(self, **values):
        """返回预设最后消息时间。"""
        return self.last_message_at

    async def update_conversation(
        self,
        conversation,
        *,
        title,
        summary,
        conversation_metadata,
    ):
        """在内存中更新对话。"""
        conversation.title = title
        conversation.summary = summary
        conversation.conversation_metadata = conversation_metadata
        conversation.updated_at = NOW
        return conversation

    async def list_tree_for_user(self, **values):
        """返回预设根子对话树。"""
        return self.tree

    async def soft_delete_tree(self, **values):
        """记录被软删除的对话 ID。"""
        self.deleted_ids = list(values["conversation_ids"])


class FakeAgentRunRepository:
    """在内存中模拟 AgentRun Repository。"""

    def __init__(self) -> None:
        self.runs = {}
        self.has_active = False

    async def get_by_ids_for_conversation(self, **values):
        """返回预设 Run 映射。"""
        return {
            run_id: self.runs[run_id]
            for run_id in values["run_ids"]
            if run_id in self.runs
        }

    async def has_active_for_conversations(self, **values):
        """返回预设活动 Run 状态。"""
        return self.has_active


class FakeUserRepository:
    """返回固定用户。"""

    async def get_by_uid(self, uid):
        """返回请求 UID 对应的用户。"""
        return SimpleNamespace(uid=uid)


class FakeAgentRepository:
    """返回固定顶层 Agent。"""

    async def get_by_slug_for_run_type(self, *, slug, run_type):
        """返回请求的顶层 Agent。"""
        return SimpleNamespace(
            slug=slug,
            backend_id="leader-backend",
            role=run_type,
        )


NOW = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)


def make_conversation(
    conversation_id: int,
    *,
    metadata: dict | None = None,
) -> SimpleNamespace:
    """构造测试 Conversation。"""
    return SimpleNamespace(
        id=conversation_id,
        uid="user-1",
        thread_id=f"thread-{conversation_id}",
        agent_id="leaderagent",
        title=f"对话 {conversation_id}",
        summary="摘要",
        conversation_metadata=metadata or {"backend_id": "system-backend"},
        created_at=NOW,
        updated_at=NOW,
    )


def make_message(
    message_id: int,
    *,
    role: str,
    run_id: str | None,
) -> SimpleNamespace:
    """构造测试 Message。"""
    return SimpleNamespace(
        id=message_id,
        agent_run_id=run_id,
        role=role,
        content=f"消息 {message_id}",
        image_content=None,
        message_type="text",
        status="completed",
        request_id="request-1",
        created_at=NOW + timedelta(minutes=message_id),
        updated_at=NOW + timedelta(minutes=message_id),
    )


class ThreadServiceTest(unittest.IsolatedAsyncioTestCase):
    """验证 ThreadService 的公开用例契约。"""

    def build_service(self, conversation=None):
        """构造注入 Fake Repository 的 Service。"""
        service = ThreadService(FakeSession())
        conversations = FakeConversationRepository(conversation)
        runs = FakeAgentRunRepository()
        service.conversations = conversations
        service.runs = runs
        return service, conversations, runs

    async def test_create_thread_protects_backend_metadata(self) -> None:
        """创建对话时由服务端覆盖 backend_id。"""
        service, conversations, _ = self.build_service()
        service.users = FakeUserRepository()
        service.agents = FakeAgentRepository()

        conversation = await service.create_thread(
            uid="user-1",
            agent_id="leaderagent",
            title="  新会话  ",
            summary="  摘要  ",
            metadata={"backend_id": "client", "workspace": "research"},
        )

        self.assertEqual("新会话", conversation.title)
        self.assertEqual("摘要", conversation.summary)
        self.assertEqual(
            "leader-backend",
            conversation.conversation_metadata["backend_id"],
        )

    async def test_list_threads_returns_stable_cursor(self) -> None:
        """列表只返回 limit 条并按最后一项生成游标。"""
        service, conversations, _ = self.build_service()
        first = make_conversation(2)
        second = make_conversation(1)
        conversations.rows = [
            (first, NOW + timedelta(minutes=2), NOW + timedelta(minutes=2)),
            (second, NOW + timedelta(minutes=1), NOW + timedelta(minutes=1)),
        ]

        result = await service.list_threads(
            uid="user-1",
            limit=1,
            query="  检索  ",
        )

        self.assertEqual(["thread-2"], [item["thread_id"] for item in result["items"]])
        self.assertIsNotNone(result["next_cursor"])
        activity_at, conversation_id = service._decode_cursor(
            result["next_cursor"]
        )
        self.assertEqual(NOW + timedelta(minutes=2), activity_at)
        self.assertEqual(2, conversation_id)
        self.assertEqual("检索", conversations.list_arguments["query"])

    def test_list_cursor_rejects_non_object_payload(self) -> None:
        """列表游标必须包含约定的 JSON 对象。"""
        with self.assertRaisesRegex(ValueError, "无效的对话列表游标"):
            ThreadService._decode_cursor("W10")

    async def test_detail_returns_messages_in_display_order_with_run(self) -> None:
        """详情返回最新消息页并在响应中恢复为正序。"""
        conversation = make_conversation(1)
        service, conversations, runs = self.build_service(conversation)
        conversations.messages = [
            make_message(3, role="assistant", run_id="run-1"),
            make_message(2, role="user", run_id="run-1"),
            make_message(1, role="user", run_id=None),
        ]
        conversations.last_message_at = NOW + timedelta(minutes=3)
        runs.runs["run-1"] = SimpleNamespace(
            id="run-1",
            run_type="chat",
            agent_status="completed",
            parent_run_id=None,
            run_metadata={"source": "web"},
            started_at=NOW,
            finished_at=NOW + timedelta(minutes=3),
        )

        result = await service.get_thread_detail(
            uid="user-1",
            thread_id="thread-1",
            message_limit=2,
        )

        self.assertEqual([2, 3], [item["message_id"] for item in result["messages"]])
        self.assertEqual(2, result["next_before_message_id"])
        self.assertEqual(
            {"source": "web"},
            result["messages"][0]["run"]["metadata"],
        )

    async def test_update_replaces_user_metadata_and_preserves_backend(self) -> None:
        """更新 metadata 时保留系统 backend_id。"""
        conversation = make_conversation(
            1,
            metadata={"backend_id": "system-backend", "old": True},
        )
        service, _, _ = self.build_service(conversation)

        result = await service.update_thread(
            uid="user-1",
            thread_id="thread-1",
            fields={"summary", "metadata"},
            title=None,
            summary=None,
            metadata={"backend_id": "client", "new": True},
        )

        self.assertIsNone(result["summary"])
        self.assertEqual(
            {"backend_id": "system-backend", "new": True},
            result["metadata"],
        )

    async def test_delete_rejects_active_run_then_soft_deletes_tree(self) -> None:
        """活动 Run 阻止删除，终态后删除根子对话。"""
        conversation = make_conversation(1)
        child = make_conversation(2)
        service, conversations, runs = self.build_service(conversation)
        conversations.tree = [conversation, child]
        runs.has_active = True

        with self.assertRaises(ThreadConflictError):
            await service.delete_thread(uid="user-1", thread_id="thread-1")
        self.assertEqual([], conversations.deleted_ids)

        runs.has_active = False
        await service.delete_thread(uid="user-1", thread_id="thread-1")
        self.assertEqual([1, 2], conversations.deleted_ids)

    def test_router_exposes_thread_crud(self) -> None:
        """Router 暴露统一 Thread 资源的 CRUD 方法。"""
        methods_by_path: dict[str, set[str]] = {}
        for route in router.routes:
            if hasattr(route, "methods"):
                methods_by_path.setdefault(route.path, set()).update(route.methods)

        self.assertIn("POST", methods_by_path["/chat/thread"])
        self.assertIn("GET", methods_by_path["/chat/thread"])
        self.assertIn("GET", methods_by_path["/chat/thread/{thread_id}"])
        self.assertIn("PATCH", methods_by_path["/chat/thread/{thread_id}"])
        self.assertIn("DELETE", methods_by_path["/chat/thread/{thread_id}"])


if __name__ == "__main__":
    unittest.main()
