from dataclasses import dataclass, field
from typing import Any

from langchain.messages import HumanMessage


@dataclass(frozen=True)
class AgentInputMsg:
    """Agent 单次执行使用的输入消息。"""

    content: str
    msg_type: str
    image_content: str | None
    msg_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def langchain_msg(self) -> HumanMessage:
        message_kwargs = {
            "additional_kwargs": dict(self.msg_metadata),
        }
        if not self.image_content:
            return HumanMessage(content=self.content, **message_kwargs)

        content = []
        if self.content:
            content.append({"type": "text", "text": self.content})
        content.append(
            {"type": "image_url", "image_url": {"url": self.image_content}}
        )
        return HumanMessage(content=content, **message_kwargs)


def build_agent_input_msg(
    *,
    query: str = "",
    image_content: str | None = None,
    msg_type: str | None = None,
    msg_metadata: dict[str, Any] | None = None,
) -> AgentInputMsg:
    """集中构建 Agent 输入消息，并保留已持久化的消息类型。"""
    metadata = dict(msg_metadata or {})
    file_ids = metadata.get("attachment_file_ids", [])
    if file_ids is None:
        file_ids = []
    if not isinstance(file_ids, list):
        raise ValueError("msg_metadata.attachment_file_ids 必须是列表")
    if not query and not image_content and not file_ids:
        raise ValueError("Agent 输入不能为空")

    if msg_type is None:
        msg_type = "text"
        if file_ids:
            msg_type = "multimodal" if query or image_content else "attachment"
        elif image_content:
            msg_type = "multimodal" if query else "image"

    return AgentInputMsg(
        content=query,
        msg_type=msg_type,
        image_content=image_content,
        msg_metadata=metadata,
    )


__all__ = [
    "AgentInputMsg",
    "build_agent_input_msg",
]
