from dataclasses import dataclass, field

from src.agents.base_context import BaseContext
from src.configs import config as sys_config


@dataclass(kw_only=True)
class ImageProcessingAgentContext(BaseContext):
    """图像处理运行配置；通过继承的 mcps 选择 MCP 服务。"""

    model: str = field(default=sys_config.default_model)
