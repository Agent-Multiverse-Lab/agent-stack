from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from server.service import sandbox_service


class SandboxWorkspaceServiceTest(IsolatedAsyncioTestCase):
    def test_rejects_paths_outside_workspace(self) -> None:
        with self.assertRaisesRegex(ValueError, "inside /workspace"):
            sandbox_service.normalize_workspace_path("/uploads")

    async def test_lists_real_sandbox_entries_for_owned_thread(self) -> None:
        repository = MagicMock()
        repository.get_conversation_by_thread_id_for_user = AsyncMock(
            return_value=SimpleNamespace(thread_id="thread-1")
        )
        sandbox = MagicMock()
        sandbox.ls.return_value = SimpleNamespace(
            error=None,
            entries=[
                {
                    "path": "/home/gem/user-data/workspace/output",
                    "is_dir": True,
                },
                {
                    "path": "/home/gem/user-data/workspace/result.json",
                    "is_dir": False,
                    "size": 12,
                    "modified_at": "2026-09-21T00:00:00Z",
                },
            ],
        )
        provider = MagicMock()
        provider.acquire_async = AsyncMock(return_value="s2c-real")
        provider.get.return_value = sandbox

        with (
            patch.object(sandbox_service, "ConversationRepository", return_value=repository),
            patch.object(sandbox_service, "get_sandbox_provider", return_value=provider),
            patch.object(
                sandbox_service.asyncio,
                "to_thread",
                new=AsyncMock(side_effect=lambda function, *args: function(*args)),
            ),
        ):
            response = await sandbox_service.list_workspace(
                MagicMock(),
                uid="user-1",
                thread_id="thread-1",
                path="/workspace",
            )

        repository.get_conversation_by_thread_id_for_user.assert_awaited_once_with(
            "thread-1", "user-1"
        )
        provider.acquire_async.assert_awaited_once_with(
            "user-1",
            "thread-1",
            file_thread_id="thread-1",
            skills_thread_id="thread-1",
        )
        sandbox.ls.assert_called_once_with("/home/gem/user-data/workspace/")
        self.assertEqual(response.sandbox_id, "s2c-real")
        self.assertEqual([entry.name for entry in response.entries], ["output", "result.json"])
        self.assertEqual(response.entries[1].file_type, "data")

    async def test_reads_and_truncates_utf8_workspace_file(self) -> None:
        repository = MagicMock()
        repository.get_conversation_by_thread_id_for_user = AsyncMock(
            return_value=SimpleNamespace(thread_id="thread-1")
        )
        sandbox = MagicMock()
        sandbox.read.return_value = SimpleNamespace(
            error=None,
            file_data={
                "content": "".join(
                    f"line-{index}\n"
                    for index in range(sandbox_service.MAX_FILE_PREVIEW_LINES + 1)
                ),
                "encoding": "utf-8",
            },
        )
        provider = MagicMock()
        provider.acquire_async = AsyncMock(return_value="s2c-real")
        provider.get.return_value = sandbox

        with (
            patch.object(sandbox_service, "ConversationRepository", return_value=repository),
            patch.object(sandbox_service, "get_sandbox_provider", return_value=provider),
            patch.object(
                sandbox_service.asyncio,
                "to_thread",
                new=AsyncMock(side_effect=lambda function, *args: function(*args)),
            ),
        ):
            response = await sandbox_service.read_workspace_file(
                MagicMock(),
                uid="user-1",
                thread_id="thread-1",
                path="/workspace/report.md",
            )

        sandbox.read.assert_called_once_with(
            "/home/gem/user-data/workspace/report.md",
            0,
            sandbox_service.MAX_FILE_PREVIEW_LINES + 1,
        )
        self.assertTrue(response.truncated)
        self.assertIn("line-1999", response.content)
        self.assertNotIn("line-2000", response.content)

    async def test_rejects_non_utf8_workspace_file(self) -> None:
        with patch.object(
            sandbox_service,
            "_get_owned_sandbox",
            new=AsyncMock(
                return_value=(
                    "thread-1",
                    "s2c-real",
                    SimpleNamespace(
                        read=MagicMock(
                            return_value=SimpleNamespace(
                                error=None,
                                file_data={"content": "AAAA", "encoding": "base64"},
                            )
                        )
                    ),
                )
            ),
        ):
            with self.assertRaisesRegex(ValueError, "UTF-8 text"):
                await sandbox_service.read_workspace_file(
                    MagicMock(),
                    uid="user-1",
                    thread_id="thread-1",
                    path="/workspace/image.png",
                )
