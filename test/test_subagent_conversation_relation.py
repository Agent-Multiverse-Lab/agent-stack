"""父子 Agent 会话关系的持久化与查询测试。"""

import unittest

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from src.database.models import (
    AgentRun,
    Conversation,
    Message,
    Project,
    SubAgentConversationRelation,
)
from src.database.repositories.conversation_repository import ConversationRepository


class AsyncSessionAdapter:
    """使用同步 SQLite 执行 Repository 的异步接口。"""

    def __init__(self, session: Session):
        self.session = session

    def add(self, value) -> None:
        self.session.add(value)

    async def execute(self, statement, **kwargs):
        return self.session.execute(statement, **kwargs)

    async def flush(self) -> None:
        self.session.flush()

    async def refresh(self, value) -> None:
        self.session.refresh(value)


class SubagentConversationRelationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine("sqlite://")
        event.listen(self.engine, "connect", lambda connection, _record: connection.execute("PRAGMA foreign_keys=ON"))
        self.addCleanup(self.engine.dispose)
        Project.__table__.create(self.engine)
        Conversation.__table__.create(self.engine)
        AgentRun.__table__.create(self.engine)
        Message.__table__.create(self.engine)
        SubAgentConversationRelation.__table__.create(self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.session.close)
        self.db = AsyncSessionAdapter(self.session)
        self.repository = ConversationRepository(self.db)

        self.parent = Conversation(
            uid="user-1",
            thread_id="parent-thread",
            agent_id="leader_agent",
            title="Parent",
            conversation_metadata={},
        )
        self.child = Conversation(
            uid="user-1",
            thread_id="child-thread",
            agent_id="search_agent",
            title="Child",
            conversation_metadata={},
        )
        self.session.add_all([self.parent, self.child])
        self.session.flush()
        self.parent_run = AgentRun(
            id="parent-run",
            thread_id="parent-thread",
            conversation_id=self.parent.id,
            uid="user-1",
            agent_id="leader_agent",
            run_type="chat",
            agent_status="completed",
            request_id="parent-request",
            run_metadata={},
        )
        self.session.add(self.parent_run)
        self.session.flush()

    async def test_relation_owns_hierarchy_and_soft_delete(self) -> None:
        relation = await self.repository.create_subagent_relation(
            uid="user-1",
            parent_conversation=self.parent,
            child_conversation=self.child,
            created_by_run_id="parent-run",
        )
        self.assertEqual(relation.parent_conversation_id, self.parent.id)
        self.assertEqual(relation.child_conversation_id, self.child.id)

        top_level = await self.repository.list_top_level_for_user(uid="user-1", limit=10)
        self.assertEqual([row.id for row, _activity in top_level], [self.parent.id])
        tree = await self.repository.list_tree_for_user(
            root_conversation_id=self.parent.id,
            uid="user-1",
        )
        self.assertEqual({row.id for row in tree}, {self.parent.id, self.child.id})

        await self.repository.soft_delete_tree(
            conversation_ids=[self.parent.id, self.child.id],
            uid="user-1",
        )
        stored_relation = self.session.execute(select(SubAgentConversationRelation)).scalar_one()
        self.assertIsNotNone(stored_relation.deleted_at)

    async def test_relation_rejects_cross_user_conversation(self) -> None:
        other = Conversation(
            uid="user-2",
            thread_id="other-thread",
            agent_id="search_agent",
            title="Other",
            conversation_metadata={},
        )
        self.session.add(other)
        self.session.flush()
        with self.assertRaisesRegex(ValueError, "子会话不属于当前用户"):
            await self.repository.create_subagent_relation(
                uid="user-1",
                parent_conversation=self.parent,
                child_conversation=other,
                created_by_run_id="parent-run",
            )
