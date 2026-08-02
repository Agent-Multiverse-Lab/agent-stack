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
        if not self.image_content:
            return HumanMessage(content=self.content)

        content = []
        if self.content:
            content.append({"type": "text", "text": self.content})
        content.append(
            {"type": "image_url", "image_url": {"url": self.image_content}}
        )
        return HumanMessage(content=content)


def build_agent_input_msg(
    *,
    query: str = "",
    image_content: str | None = None,
    msg_type: str | None = None,
) -> AgentInputMsg:
    """集中构建 Agent 输入消息，并保留已持久化的消息类型。"""
    if not query and not image_content:
        raise ValueError("Agent 输入不能为空")

    if msg_type is None:
        msg_type = "text"
        if image_content:
            msg_type = "multimodal" if query else "image"

    return AgentInputMsg(
        content=query,
        msg_type=msg_type,
        image_content=image_content,
    )


__all__ = ["AgentInputMsg", "build_agent_input_msg"]
