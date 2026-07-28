from typing import Any, NotRequired

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
)
from langchain.messages import AIMessage, SystemMessage

from src.utils import logger

# TODO 待检测

def _build_prompt_with_attachement(attachements: list[dict]):
    """附件添加形成prompt"""
    if not attachements:
        return None
    valid_attachments = []
    for attachment in attachements:
        attachment_path = attachment.get("path")
        attachment_name = attachment.get("name")
        if not isinstance(attachment_path, str):
            continue
        valid_attachments.append((attachment_name, attachment_path))

    if not valid_attachments:
        return None

    attachment_info = [
        "附件文件如下：",
        *(
            f"- {attachment_name}: {attachment_path}"
            for attachment_name, attachment_path in valid_attachments
        ),
    ]

    return "\n".join(attachment_info)


class AttachmentState(AgentState):
    """附件"""

    attachements: NotRequired[list[dict]]  # 处理附件


class AttachmentMiddleware(AgentMiddleware):
    """附件中间件,将附件路径加入到模型请求中"""

    state_schema = AttachmentState

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler,
    ) -> ModelResponse | AIMessage | Any:
        #    """将附件路径加入到模型请求中"""
        attachement_prompt = _build_prompt_with_attachement(
          attachements=request.state.get("attachement", [])
        )
        if attachement_prompt:
            logger.info(message=f"AttachmentMiddleware注入: {attachement_prompt}")

            # 当前v3版本会把附件信息加入到system_message的content_blocks中, 以便模型可以看到附件信息
            system_prompt_contents_blocks = (
                list(request.system_message.content_blocks)
                if request.system_message
                else []
            )

            existing_text = ""
            for system_prompt_contents_block in system_prompt_contents_blocks:
                if isinstance(system_prompt_contents_block, dict) and system_prompt_contents_block.get("type") == "text":
                    if existing_text:
                        existing_text += "\n"
                    existing_text += system_prompt_contents_block.get("text", "")
            
            system_prompt_merged_content = existing_text + "\n" + attachement_prompt if existing_text else attachement_prompt

            request = request.override(system_message=SystemMessage(content=system_prompt_merged_content))


        return await handler(request)
            
def create_attachment_middleware() -> AttachmentMiddleware:
    return AttachmentMiddleware()
