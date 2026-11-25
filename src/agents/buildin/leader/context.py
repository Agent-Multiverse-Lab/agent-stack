from dataclasses import dataclass, field

from src.agents.base_context import BaseContext
from src.configs.config import config as sys_config


@dataclass
class LeaderAgentContext(BaseContext):
    """LeaderAgent 的创作编排上下文。"""

    system_prompt: str = field(default="")
    sub_model: str = field(default="dashscope:qwen3.5-plus")
    image_model: str = field(
        default=sys_config.image_model,
        metadata={"description": "图片生成模型名称"},
    )
