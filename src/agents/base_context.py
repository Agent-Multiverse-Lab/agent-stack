import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(kw_only=True)
class BaseContext:
    """
    基础上下文
    """

    system_prompt: str = field(default="", metadata={"description": "系统提示词"})

    uid: str = field(
        default=lambda: str(uuid.uuid4()), metadata={"description": "用户id"}
    )  # ty:ignore[invalid-assignment]
    
    thread_id: str = field(
            default=lambda: str(uuid.uuid4()), metadata={"description": "对话id"}
        )  # ty:ignore[invalid-assignment]

    run_id: str = field(default="", metadata={"description": "当前 Agent Run ID"})

    request_id: str = field(default="", metadata={"description": "当前请求 ID"})
    
    tools: list = field(default_factory=list, metadata={"description": "工具集合"})

    model: str = field(default="", metadata={"description": "agent使用的模型"})

    skill_root: str | Path | None = field(
        default=None, metadata={"description": "agent技能目录"}
    )
    
    mcps: list[str] = field(
        default_factory=list,
        metadata={
            "description": "本次运行启用的 MCP Server 名称；为空时使用全部已配置服务"
        },
    )
    
    style_profolio: dict = field(default_factory=dict, metadata={"description": "素材，算是吧"})
    
    def update_context(self, context:dict):
        "更新前端覆盖的参数"
        for k, v in context.items():
            if hasattr(self, k):
                setattr(self, k, v)
