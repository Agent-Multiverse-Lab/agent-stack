"""Agent Run 事件与取消辅助函数测试。"""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from server.entities.agent import AgentRunCreateRequest
from server.service import agent_run_service
from server.service.arq_queue_servcie import build_agent_chunk_envolope
from server.utils.agent_run_utils import format_agent_run_sse


class AgentRunEventTest(unittest.IsolatedAsyncioTestCase):
    def test_request_uses_unified_metadata(self):
        self.assertIn("request_metadata", AgentRunCreateRequest.model_fields)
        self.assertNotIn("thread_metadata", AgentRunCreateRequest.model_fields)
        self.assertNotIn("msg_metadata", AgentRunCreateRequest.model_fields)
        self.assertNotIn("attachment_ids", AgentRunCreateRequest.model_fields)
        self.assertNotIn("is_resume", AgentRunCreateRequest.model_fields)
        self.assertNotIn("created_by_run_id", AgentRunCreateRequest.model_fields)

    def test_format_sse_uses_queue_envelope(self):
        envelope = build_agent_chunk_envolope(
            run_id="r1",
            event_type="end",
            thread_id="thread-1",
            payload={"status": "completed"},
            created_at="2026-08-16T00:00:00+00:00",
        )
        frame = format_agent_run_sse("1-0", envelope)
        data = json.loads(
            next(line for line in frame.splitlines() if line.startswith("data: "))[6:]
        )

        self.assertIn("id: 1-0\n", frame)
        self.assertIn("event: end\n", frame)
        self.assertEqual("agent_run", data["scope"])
        self.assertEqual("r1", data["run_id"])
        self.assertEqual("end", data["type"])
        self.assertEqual("completed", data["status"])

    def test_decode_event_fields_from_redis_bytes(self):
        payload = agent_run_service._decode_event_fields(
            {b"event": b'{"type":"done"}'}
        )

        self.assertEqual({"type": "done"}, payload)

    async def test_subagent_progress_reads_nested_payload(self):
        envelope = build_agent_chunk_envolope(
            run_id="r1",
            event_type="end",
            thread_id="thread-1",
            payload={"status": "failed", "error": "boom"},
            created_at="2026-08-16T00:00:00+00:00",
        )
        fields = {b"event": json.dumps(envelope).encode()}

        with patch(
            "server.service.agent_run_service.read_recent_agent_run_stream_events",
            return_value=[(b"1-0", fields)],
        ):
            progress = await agent_run_service.read_subagent_progress(run_id="r1")

        self.assertEqual("failed", progress["status"])
        self.assertTrue(progress["terminal"])
        self.assertEqual("boom", progress["error"])
        self.assertEqual(envelope, progress["events"][0]["payload"])

    async def test_user_cancel_rejects_direct_subagent_cancellation(self):
        sub_run = SimpleNamespace(
            id="sub-1",
            uid="user-1",
            thread_id="thread-sub-1",
            agent_id="search_agent",
            run_type="subagent",
            agent_status="running",
        )
        repo = SimpleNamespace(
            get_by_id_for_user=AsyncMock(return_value=sub_run),
            cascade_cancel_descendants=AsyncMock(return_value=[]),
            request_cancel=AsyncMock(),
        )
        db = SimpleNamespace(commit=AsyncMock())
        with patch(
            "server.service.agent_run_service.AgentRunRepository",
            return_value=repo,
        ):
            with self.assertRaisesRegex(
                agent_run_service.AgentRunConflictError,
                "子智能体运行不支持直接取消",
            ):
                await agent_run_service.cancel_agent_run(
                    run_id="sub-1",
                    current_user_id="user-1",
                    db=db,
                )
        repo.request_cancel.assert_not_awaited()
        db.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
