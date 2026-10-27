"""把当前会话工作区内已经生成的结果文件登记为交付物，供前端预览和下载。"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Annotated

from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

WORKSPACE_VIRTUAL_ROOT = "/workspace"
ARTIFACTS_VIRTUAL_ROOT = "/workspace/outputs"


class PresentArtifactsInput(BaseModel):
    """声明交付物文件路径。"""

    filepaths: list[str] = Field(description="需要展示给用户的文件绝对路径列表")


PRESENT_ARTIFACTS_DESCRIPTION = """将已经生成好的结果文件展示给用户。

使用场景：
1. 你已经在当前会话工作区（/workspace）中写好了最终结果文件
2. 你希望前端在对话中显示这些结果文件卡片
3. 这些文件需要支持下载或预览

注意事项：
1. 只能传入当前会话 /workspace 内的普通文件，推荐放在 /workspace/outputs/ 下
2. 不要传入目录、符号链接、不存在或工作区之外的文件
3. 不要传入中间过程文件，只有真正需要给用户看的结果文件才调用
4. 可以一次传多个文件，重复路径会自动去重
"""


def _resolve_workspace_root(uid: str, thread_id: str) -> Path:
    """延迟导入宿主工作区映射，避免工具模块加载时引入沙箱依赖。"""
    from src.agents.backends.sandbox.provider_service import workspace_paths

    workspace_root, _ = workspace_paths(uid, thread_id)
    return workspace_root


def normalize_artifact_paths(workspace_root: Path, filepaths: list[str]) -> list[str]:
    """校验并归一化交付物为去重的 /workspace 虚拟路径。"""
    root = Path(workspace_root).resolve()
    normalized = [_normalize_artifact_path(root, filepath) for filepath in filepaths]
    return list(dict.fromkeys(normalized))


def _normalize_artifact_path(root: Path, filepath: str) -> str:
    if not isinstance(filepath, str):
        raise ValueError("filepaths 必须是字符串路径列表")
    raw = filepath.strip()
    if not raw:
        raise ValueError("文件路径不能为空")
    if "\x00" in raw or "\\" in raw:
        raise ValueError(f"非法文件路径: {filepath}")
    if not raw.startswith(f"{WORKSPACE_VIRTUAL_ROOT}/"):
        raise ValueError(f"只接受 /workspace 内的文件: {filepath}")

    relative = PurePosixPath(raw).relative_to(WORKSPACE_VIRTUAL_ROOT)
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"非法文件路径: {filepath}")

    host_path = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"交付物不能是符号链接: {filepath}")
    if not host_path.exists():
        raise ValueError(f"文件不存在: {filepath}")
    if not host_path.is_file():
        raise ValueError(f"交付物必须是普通文件: {filepath}")
    try:
        host_path.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError(f"文件不在当前会话工作区内: {filepath}") from exc
    return PurePosixPath(WORKSPACE_VIRTUAL_ROOT).joinpath(*relative.parts).as_posix()


@tool(
    "present_artifacts",
    description=PRESENT_ARTIFACTS_DESCRIPTION,
    args_schema=PresentArtifactsInput,
)
def present_artifacts(
    filepaths: list[str],
    runtime: ToolRuntime,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """登记当前用户可见的普通文件，使前端展示给用户。"""
    try:
        context = runtime.context
        workspace_root = _resolve_workspace_root(str(context.uid), str(context.thread_id))
        normalized_paths = normalize_artifact_paths(workspace_root, filepaths)
    except (ValueError, OSError, TypeError, AttributeError) as exc:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Error: {exc}",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    return Command(
        update={
            "artifacts": normalized_paths,
            "messages": [
                ToolMessage(content="已将交付物展示给用户", tool_call_id=tool_call_id)
            ],
        }
    )
