import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from server.service import sandbox_service


class SandboxWorkspaceServiceTest(IsolatedAsyncioTestCase):
    async def test_file_mutations_require_conversation_ownership(self) -> None:
        repository = MagicMock()
        repository.get_conversation_by_thread_id_for_user = AsyncMock(return_value=None)
        with patch.object(sandbox_service, "ConversationRepository", return_value=repository), patch.object(sandbox_service, "get_sandbox_provider") as provider:
            for operation in ["rename", "write", "delete"]:
                with self.subTest(operation=operation), self.assertRaises(LookupError):
                    await sandbox_service.mutate_workspace_file(
                        MagicMock(), uid="other", thread_id="thread", path="/workspace/file.txt",
                        operation=operation, name="new.txt", content="new", previous_content="old",
                    )
            provider.assert_not_called()

    async def test_mutation_releases_sandbox_after_a_conflict(self) -> None:
        sandbox = MagicMock()
        sandbox.execute.return_value = SimpleNamespace(exit_code=0, output=json.dumps({"kind": "conflict", "error": "Name already exists"}))
        provider = MagicMock()
        with patch.object(sandbox_service, "_get_owned_sandbox", new=AsyncMock(return_value=("thread", "real-id", sandbox, provider))):
            with self.assertRaisesRegex(FileExistsError, "Name already exists"):
                await sandbox_service.mutate_workspace_file(
                    MagicMock(), uid="user", thread_id="thread", path="/workspace/file.txt", operation="rename", name="new.txt",
                )
        provider.release.assert_called_once_with("real-id")

    async def test_large_editor_payload_is_uploaded_instead_of_inlined(self) -> None:
        sandbox = MagicMock()
        sandbox.upload_files.return_value = [SimpleNamespace(error=None)]
        sandbox.execute.return_value = SimpleNamespace(exit_code=0, output='{"path":"/workspace/file.txt"}')
        provider = MagicMock()
        content = "x" * 180_000
        with patch.object(sandbox_service, "_get_owned_sandbox", new=AsyncMock(return_value=("thread", "real-id", sandbox, provider))):
            await sandbox_service.mutate_workspace_file(
                MagicMock(), uid="user", thread_id="thread", path="/workspace/file.txt", operation="write", content=content, previous_content="old",
            )
        staged_path, uploaded = sandbox.upload_files.call_args.args[0][0]
        self.assertEqual(json.loads(uploaded)["content"], content)
        self.assertIn(staged_path, sandbox.execute.call_args.args[0])
        self.assertLess(len(sandbox.execute.call_args.args[0]), 10_000)
        provider.release.assert_called_once_with("real-id")

    async def test_unauthorized_thread_never_acquires_sandbox(self) -> None:
        repository = MagicMock()
        repository.get_conversation_by_thread_id_for_user = AsyncMock(return_value=None)
        with patch.object(sandbox_service, "ConversationRepository", return_value=repository), patch.object(sandbox_service, "get_sandbox_provider") as provider:
            with self.assertRaises(LookupError):
                await sandbox_service.list_workspace(MagicMock(), uid="other", thread_id="thread", path="/workspace")
            provider.assert_not_called()

    def test_rejects_paths_outside_workspace(self) -> None:
        with self.assertRaisesRegex(ValueError, "inside /workspace"):
            sandbox_service.normalize_workspace_path("/uploads")

    async def test_lists_real_sandbox_entries_for_owned_thread(self) -> None:
        repository = MagicMock()
        repository.get_conversation_by_thread_id_for_user = AsyncMock(return_value=SimpleNamespace(thread_id="thread-1"))
        sandbox = MagicMock()
        sandbox.ls.return_value = SimpleNamespace(
            error=None,
            entries=[
                {
                    "path": "/workspace/output",
                    "is_dir": True,
                },
                {
                    "path": "/workspace/result.json",
                    "is_dir": False,
                    "size": 12,
                    "mtime": 0,
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

        repository.get_conversation_by_thread_id_for_user.assert_awaited_once_with("thread-1", "user-1")
        provider.acquire_async.assert_awaited_once_with(
            "user-1",
            "thread-1",
        )
        sandbox.ls.assert_called_once_with("/workspace")
        provider.release.assert_called_once_with("s2c-real")
        self.assertEqual(response.sandbox_id, "s2c-real")
        self.assertEqual([entry.name for entry in response.entries], ["output", "result.json"])
        self.assertEqual(response.entries[1].file_type, "data")
        self.assertEqual(response.entries[1].modified_at, "1970-01-01T00:00:00+00:00")

    async def test_reads_and_truncates_utf8_workspace_file(self) -> None:
        repository = MagicMock()
        repository.get_conversation_by_thread_id_for_user = AsyncMock(return_value=SimpleNamespace(thread_id="thread-1"))
        sandbox = MagicMock()
        sandbox.read.return_value = SimpleNamespace(
            error=None,
            file_data={
                "content": "".join(f"line-{index}\n" for index in range(sandbox_service.MAX_FILE_PREVIEW_LINES + 1)),
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
            "/workspace/report.md",
            0,
            sandbox_service.MAX_FILE_PREVIEW_LINES + 1,
        )
        self.assertTrue(response.truncated)
        self.assertIn("line-1999", response.content)
        self.assertNotIn("line-2000", response.content)

    @patch.object(sandbox_service, "get_sandbox_provider", return_value=MagicMock())
    async def test_rejects_non_utf8_workspace_file(self, _provider) -> None:
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
                    MagicMock(),
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


class SandboxFileOperationsTest(TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="sandbox-file-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        namespace = {"__name__": "file_operation_test"}
        exec(sandbox_service._FILE_OPERATION_SCRIPT, namespace)
        self.apply = namespace["apply_operation"]

    def test_read_and_save_preserve_complete_content_and_crlf(self) -> None:
        file = self.root / "report.md"
        file.write_bytes("# Report\r\n\r\n原文\r\n".encode())
        response = self.apply(self.root, {"operation": "read", "path": "/workspace/report.md"})
        self.assertEqual(response["content"], "# Report\r\n\r\n原文\r\n")
        self.assertFalse(response["truncated"])
        self.apply(self.root, {"operation": "write", "path": "/workspace/report.md", "previous_content": response["content"], "content": "# Changed\n\n修改\n"})
        self.assertEqual(file.read_bytes(), "# Changed\r\n\r\n修改\r\n".encode())

    def test_save_conflict_leaves_existing_content_intact(self) -> None:
        file = self.root / "report.txt"
        file.write_text("Agent updated this", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.apply(self.root, {"operation": "write", "path": "/workspace/report.txt", "previous_content": "Old text", "content": "Draft"})
        self.assertEqual(file.read_text(encoding="utf-8"), "Agent updated this")

    def test_empty_file_can_be_edited_and_large_file_is_flagged(self) -> None:
        file = self.root / "empty.txt"
        file.write_text("", encoding="utf-8")
        response = self.apply(self.root, {"operation": "read", "path": "/workspace/empty.txt"})
        self.assertEqual(response["content"], "")
        self.apply(self.root, {"operation": "write", "path": "/workspace/empty.txt", "previous_content": "", "content": "New text"})
        self.assertEqual(file.read_text(encoding="utf-8"), "New text")
        file.write_text("line\n" * 2001, encoding="utf-8")
        self.assertTrue(self.apply(self.root, {"operation": "read", "path": "/workspace/empty.txt"})["truncated"])

    def test_rename_refuses_existing_target_then_delete_only_removes_the_file(self) -> None:
        source = self.root / "source.txt"
        source.write_text("Source", encoding="utf-8")
        target = self.root / "target.txt"
        target.write_text("Target", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.apply(self.root, {"operation": "rename", "path": "/workspace/source.txt", "name": "target.txt"})
        self.assertEqual(target.read_text(encoding="utf-8"), "Target")
        response = self.apply(self.root, {"operation": "rename", "path": "/workspace/source.txt", "name": "renamed.txt"})
        self.assertEqual(response["path"], "/workspace/renamed.txt")
        self.assertFalse(source.exists())
        self.apply(self.root, {"operation": "delete", "path": response["path"]})
        self.assertFalse((self.root / "renamed.txt").exists())
        self.assertTrue(target.exists())

    def test_rejects_directories_and_paths_outside_workspace(self) -> None:
        (self.root / "folder").mkdir()
        with self.assertRaises(ValueError):
            self.apply(self.root, {"operation": "delete", "path": "/workspace/folder"})
        with self.assertRaises(ValueError):
            self.apply(self.root, {"operation": "delete", "path": "/workspace/../../outside.txt"})
        self.assertTrue((self.root / "folder").is_dir())

    def test_rejects_binary_text_and_symbolic_links(self) -> None:
        file = self.root / "binary.dat"
        file.write_bytes(b"text\x00binary")
        with self.assertRaises(ValueError):
            self.apply(self.root, {"operation": "read", "path": "/workspace/binary.dat"})
        link = self.root / "link.dat"
        try:
            link.symlink_to(file)
        except OSError:
            self.skipTest("Symlink creation requires permission on Windows")
        with self.assertRaises(ValueError):
            self.apply(self.root, {"operation": "delete", "path": "/workspace/link.dat"})
        self.assertTrue(file.exists())
