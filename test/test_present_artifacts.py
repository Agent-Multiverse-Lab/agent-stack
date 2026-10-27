"""验证交付物工具的工作区路径校验、状态合并与 Command 返回值。"""

import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = runpy.run_path(str(PROJECT_ROOT / "src/agents/buildin/leader/present_artifacts.py"))
present_artifacts = NAMESPACE["present_artifacts"]
normalize_artifact_paths = NAMESPACE["normalize_artifact_paths"]
merge_artifacts = runpy.run_path(
    str(PROJECT_ROOT / "src/agents/base_state.py")
)["merge_artifacts"]


class MergeArtifactsTest(unittest.TestCase):
    def test_merge_keeps_order_and_deduplicates(self) -> None:
        self.assertEqual(
            merge_artifacts(["/workspace/b.md"], ["/workspace/a.md", "/workspace/b.md"]),
            ["/workspace/b.md", "/workspace/a.md"],
        )
        self.assertEqual(merge_artifacts(None, ["/workspace/a.md"]), ["/workspace/a.md"])
        self.assertEqual(merge_artifacts(["/workspace/a.md"], None), ["/workspace/a.md"])


class NormalizeArtifactPathsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "outputs").mkdir()
        (self.root / "outputs" / "report.md").write_text("# report", encoding="utf-8")
        (self.root / "outputs" / "图表.png").write_bytes(b"png")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_valid_file_is_normalized_to_workspace_path(self) -> None:
        self.assertEqual(
            normalize_artifact_paths(self.root, ["/workspace/outputs/report.md"]),
            ["/workspace/outputs/report.md"],
        )
        self.assertEqual(
            normalize_artifact_paths(self.root, ["/workspace/outputs//./report.md"]),
            ["/workspace/outputs/report.md"],
        )

    def test_duplicates_are_removed_in_order(self) -> None:
        self.assertEqual(
            normalize_artifact_paths(
                self.root,
                ["/workspace/outputs/report.md", "/workspace/outputs/report.md"],
            ),
            ["/workspace/outputs/report.md"],
        )

    def test_rejects_paths_outside_workspace_or_traversal(self) -> None:
        for path in (
            "/etc/passwd",
            "outputs/report.md",
            "/workspace/../etc/passwd",
            "/workspace",
            "/workspace/outputs/../../etc/passwd",
            "",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                normalize_artifact_paths(self.root, [path])

    def test_rejects_directories_missing_files_and_symlinks(self) -> None:
        (self.root / "outputs" / "nested").mkdir()
        (self.root / "outputs" / "link.md").symlink_to(self.root / "outputs" / "report.md")
        for path in (
            "/workspace/outputs",
            "/workspace/outputs/",
            "/workspace/outputs/missing.md",
            "/workspace/outputs/nested",
            "/workspace/outputs/link.md",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                normalize_artifact_paths(self.root, [path])

    def _runtime(self) -> SimpleNamespace:
        return SimpleNamespace(context=SimpleNamespace(uid="uid", thread_id="thread"))

    def test_tool_returns_command_with_artifacts_and_tool_message(self) -> None:
        globals_dict = present_artifacts.func.__globals__
        previous = globals_dict["_resolve_workspace_root"]
        globals_dict["_resolve_workspace_root"] = lambda uid, thread_id: self.root
        try:
            result = present_artifacts.func(
                filepaths=["/workspace/outputs/report.md"],
                runtime=self._runtime(),
                tool_call_id="call-1",
            )
        finally:
            globals_dict["_resolve_workspace_root"] = previous
        self.assertEqual(result.update["artifacts"], ["/workspace/outputs/report.md"])
        message = result.update["messages"][0]
        self.assertEqual(message.tool_call_id, "call-1")
        self.assertEqual(message.status, "success")

    def test_tool_returns_error_tool_message_for_invalid_path(self) -> None:
        globals_dict = present_artifacts.func.__globals__
        previous = globals_dict["_resolve_workspace_root"]
        globals_dict["_resolve_workspace_root"] = lambda uid, thread_id: self.root
        try:
            result = present_artifacts.func(
                filepaths=["/workspace/outputs/missing.md"],
                runtime=self._runtime(),
                tool_call_id="call-2",
            )
        finally:
            globals_dict["_resolve_workspace_root"] = previous
        self.assertNotIn("artifacts", result.update)
        message = result.update["messages"][0]
        self.assertEqual(message.status, "error")
        self.assertIn("missing.md", str(message.content))


if __name__ == "__main__":
    unittest.main()
