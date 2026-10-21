"""隔离基础设施，验证 AskHuman 事件映射及持久化后的发布顺序。"""

import ast
import json
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock


class WorkerInteractionEventTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "server" / "worker.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        nodes = [
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {"map_stream_event", "_finalize_run"}
        ]
        self.namespace = {
            "Any": Any,
            "json": json,
            "set_run_terminal": AsyncMock(),
            "write_stream_event": AsyncMock(),
            "write_end_stream_event": AsyncMock(),
            "clear_agent_run_cancel_signal": AsyncMock(),
            "logger": Mock(),
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), self.namespace)
        self.map_event = self.namespace["map_stream_event"]
        self.finalize = self.namespace["_finalize_run"]
        self.questions = [{
            "question_id": "continue", "question": "Continue?",
            "options": [{"label": "Yes", "value": "yes"}],
        }]

    def test_maps_thread_service_ask_human_to_independent_interaction_event(self):
        pending = {
            "name": "ask_user", "run_id": "run-1", "thread_id": "thread-1",
            "questions": self.questions,
        }
        event_type, payload = self.map_event({
            "status": "ask_human", "thread_id": "thread-1", "pending_interrupt": pending,
        })
        self.assertEqual(event_type, "interrupt")
        self.assertEqual(payload, {**pending, "parent_run_id": "run-1"})
        self.assertNotIn("parent_run_id", pending)

    async def test_finalizer_uses_mapping_after_persistence_before_end(self):
        order = []
        pending = {"name": "ask_user", "questions": self.questions}

        async def persist(*args, **kwargs):
            order.append("persist")
            return "interrupted", True

        async def publish(run_id, event_type, payload, thread_id):
            order.append(event_type)

        async def publish_end(*args):
            order.append("end")

        self.namespace["set_run_terminal"].side_effect = persist
        self.namespace["write_stream_event"].side_effect = publish
        self.namespace["write_end_stream_event"].side_effect = publish_end
        result = await self.finalize(
            "run-1", worker_id="owner-1", thread_id="thread-1",
            status="interrupted", payload=pending,
        )
        self.assertEqual(result, ("interrupted", True))
        self.assertEqual(order, ["persist", "interrupt", "end"])
        self.namespace["write_stream_event"].assert_awaited_once_with(
            "run-1", "interrupt", {**pending, "parent_run_id": "run-1"}, "thread-1",
        )

    async def test_unchanged_terminal_does_not_publish_interaction(self):
        self.namespace["set_run_terminal"].return_value = ("interrupted", False)
        result = await self.finalize(
            "run-1", worker_id="owner-1", thread_id="thread-1",
            status="interrupted", payload={"name": "ask_user", "questions": self.questions},
        )
        self.assertEqual(result, ("interrupted", False))
        self.namespace["write_stream_event"].assert_not_awaited()
        self.namespace["write_end_stream_event"].assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
