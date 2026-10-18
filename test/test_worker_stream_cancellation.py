"""直接加载生产函数，隔离应用启动和外部基础设施，验证流子任务回收。"""

import ast
import asyncio
import unittest
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def load_cancellable_stream():
    path = Path(__file__).resolve().parents[1] / "server" / "worker.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                and n.name == "_cancellable_stream")
    namespace = {"asyncio": asyncio, "AsyncIterator": AsyncIterator,
                 "Any": Any, "AgentRunController": Any}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_cancellable_stream"]


class CancellableStreamTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.wrap = load_cancellable_stream()
        self.cancel_signal = asyncio.Event()
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.children = []
        self.effects = []
        self.stream_closed = asyncio.Event()

        async def wait_cancel_signal():
            self.children.append(asyncio.current_task())
            await self.cancel_signal.wait()

        self.controller = SimpleNamespace(wait_cancel_signal=wait_cancel_signal)

    async def blocked_stream(self):
        self.children.append(asyncio.current_task())
        self.started.set()
        try:
            await self.release.wait()
            self.effects.append("executed")
            yield ("messages", "late chunk")
        finally:
            self.stream_closed.set()

    def wrapped(self, stream):
        return self.wrap(stream, run_controller=self.controller)

    async def start_blocked(self):
        owner = asyncio.create_task(anext(self.wrapped(self.blocked_stream())))
        await asyncio.wait_for(self.started.wait(), 1)
        # 即使断言失败也清理旧实现泄漏的任务，避免测试框架替我们完成验收。
        self.addAsyncCleanup(self.reclaim_children)
        return owner

    async def reclaim_children(self):
        for child in self.children:
            if not child.done():
                child.cancel()
        await asyncio.gather(*self.children, return_exceptions=True)

    def assert_children_finished(self):
        self.assertGreaterEqual(len(self.children), 2)
        self.assertTrue(all(child.done() for child in self.children))

    async def test_outer_cancellation_reclaims_children_before_return(self):
        owner = await self.start_blocked()
        owner.cancel("worker stopping")
        with self.assertRaises(asyncio.CancelledError) as raised:
            await owner
        self.assertEqual(raised.exception.args, ("worker stopping",))
        self.assert_children_finished()
        self.assertTrue(self.stream_closed.is_set())
        self.release.set()
        await asyncio.sleep(0)
        self.assertEqual(self.effects, [])

    async def test_outer_cancel_waits_for_async_stream_cleanup(self):
        cleanup_started = asyncio.Event()
        cleanup_release = asyncio.Event()

        async def stream():
            self.children.append(asyncio.current_task())
            self.started.set()
            try:
                await self.release.wait()
                yield ("messages", {})
            finally:
                cleanup_started.set()
                await cleanup_release.wait()
                self.stream_closed.set()

        owner = asyncio.create_task(anext(self.wrapped(stream())))
        await self.started.wait()
        owner.cancel()
        try:
            await asyncio.wait_for(cleanup_started.wait(), 1)
            self.assertFalse(owner.done())
        finally:
            cleanup_release.set()
            await asyncio.gather(owner, return_exceptions=True)
            await self.reclaim_children()
        self.assertTrue(owner.cancelled())
        self.assertTrue(self.stream_closed.is_set())
        self.assert_children_finished()

    async def test_timeout_reclaims_children(self):
        owner = await self.start_blocked()
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(owner, 0.01)
        self.assert_children_finished()
        self.assertTrue(self.stream_closed.is_set())

    async def test_user_cancel_reclaims_children(self):
        owner = await self.start_blocked()
        self.cancel_signal.set()
        with self.assertRaises(asyncio.CancelledError):
            await owner
        self.assert_children_finished()
        self.assertTrue(self.stream_closed.is_set())

    async def test_normal_values_and_exhaustion(self):
        async def stream():
            for value in (1, 2):
                self.children.append(asyncio.current_task())
                yield ("messages", value)
        result = [chunk async for chunk in self.wrapped(stream())]
        self.assertEqual(result, [("messages", 1), ("messages", 2)])
        self.assert_children_finished()

    async def test_stream_failure_preserves_exception(self):
        failure = ValueError("model failed")
        async def stream():
            self.children.append(asyncio.current_task())
            raise failure
            yield
        with self.assertRaises(ValueError) as raised:
            await anext(self.wrapped(stream()))
        self.assertIs(raised.exception, failure)
        self.assert_children_finished()

    async def test_cancel_waiter_failure_preserves_exception(self):
        failure = RuntimeError("listener failed")
        async def failed_waiter():
            self.children.append(asyncio.current_task())
            await self.started.wait()
            raise failure
        self.controller.wait_cancel_signal = failed_waiter
        with self.assertRaises(RuntimeError) as raised:
            await anext(self.wrapped(self.blocked_stream()))
        self.assertIs(raised.exception, failure)
        self.assert_children_finished()
        self.assertTrue(self.stream_closed.is_set())

    async def test_simultaneous_cancel_and_stream_finish_prioritizes_cancel(self):
        # 两个子任务在第一次让出控制权前都完成，涵盖值、耗尽和异常三条竞争路径。
        for outcome in ("value", "exhausted", "error"):
            with self.subTest(outcome=outcome):
                self.cancel_signal.set()
                async def stream():
                    self.children.append(asyncio.current_task())
                    if outcome == "error":
                        raise ValueError("simultaneous failure")
                    if outcome == "value":
                        yield ("messages", "done")
                with self.assertRaises(asyncio.CancelledError):
                    await anext(self.wrapped(stream()))
                self.assert_children_finished()
                # gather 必须取回已完成任务的异常，不能留下未检索异常。
                self.assertTrue(all(not task._log_traceback for task in self.children))

    async def test_outer_cancellation_not_replaced_by_stream_cleanup_error(self):
        async def stream():
            self.children.append(asyncio.current_task())
            self.started.set()
            try:
                await self.release.wait()
                yield ("messages", {})
            finally:
                raise ValueError("cleanup failed")
        owner = asyncio.create_task(anext(self.wrapped(stream())))
        await self.started.wait()
        owner.cancel("original cancellation")
        with self.assertRaises(asyncio.CancelledError) as raised:
            await owner
        self.assertEqual(raised.exception.args, ("original cancellation",))
        self.assert_children_finished()

    async def test_generator_close_after_yield_has_no_pending_children(self):
        source = self.blocked_stream()
        self.release.set()
        wrapped = self.wrapped(source)
        self.assertEqual(await anext(wrapped), ("messages", "late chunk"))
        self.assert_children_finished()
        await wrapped.aclose()
        self.assert_children_finished()
        # 包装器只拥有自己的 task；底层流的关闭仍由其拥有者负责。
        await source.aclose()

    async def test_stream_self_cancellation_propagates(self):
        async def stream():
            self.children.append(asyncio.current_task())
            raise asyncio.CancelledError("stream cancelled")
            yield
        with self.assertRaises(asyncio.CancelledError) as raised:
            await anext(self.wrapped(stream()))
        self.assertEqual(raised.exception.args, ("stream cancelled",))
        self.assert_children_finished()
