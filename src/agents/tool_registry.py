from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool


@dataclass(frozen=True, slots=True)
class ToolMetadata:
    """工具添加附加信息"""

    category: str = ""
    tags: list[str] = field(default_factory=list)
    display_name: str = ""
    icon: str = ""
    config_guide: str = ""


_tool_metadata: dict[str, ToolMetadata] = {}
_tool_instances: dict[str, BaseTool] = {}


def register_tool(tool_obj: BaseTool, metadata: ToolMetadata | None = None) -> BaseTool:
    """注册工具并附加元数据"""
    _tool_instances[tool_obj.name] = tool_obj
    _tool_metadata[tool_obj.name] = deepcopy(metadata or ToolMetadata())
    return tool_obj


def get_tool_metadata(tool_name: str) -> ToolMetadata | None:
    metadata = _tool_metadata.get(tool_name)
    return deepcopy(metadata) if metadata is not None else None


def get_registered_tools() -> list[BaseTool]:
    return list(_tool_instances.values())


def register(
    name_or_callable: str | Callable[..., Any] | None = None,
    *,
    description: str | None = None,
    args_schema: type | None = None,
    return_direct: bool = False,
    category: str = "",
    tags: list[str] | None = None,
    display_name: str = "",
    icon: str = "",
    config_guide: str = "",
):
    """基于 LangChain ``@tool`` 创建工具，并登记项目附加元数据。"""

    from langchain.tools import tool as langchain_tool

    decorator = langchain_tool(
        name_or_callable=name_or_callable,
        description=description,
        args_schema=args_schema,
        return_direct=return_direct,
    )

    def wrapper(func: Callable[..., Any]) -> BaseTool:
        tool_obj = decorator(func)
        return register_tool(
            tool_obj,
            ToolMetadata(
                category=category,
                tags=list(tags or []),
                display_name=display_name,
                icon=icon,
                config_guide=config_guide,
            ),
        )

    return wrapper
