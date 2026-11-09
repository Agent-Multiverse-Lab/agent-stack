from typing import Any

from server.entities.tool import ToolArgumentItem, ToolCatalogItem, ToolOptionItem
from src.agents.tool_registry import get_registered_tools, get_tool_metadata


def _load_builtin_tools() -> None:
    """导入静态工具模块，触发扩展 ``@tool`` 的注册逻辑。"""

    from src.agents.buildin.leader import present_artifacts as _present_artifacts
    from src.agents.buildin.leader import tools as _leader_tools
    from src.knowledge import tools as _knowledge_tools

    # 保留显式引用，说明这些导入用于模块注册副作用。
    (_present_artifacts, _leader_tools, _knowledge_tools)


def _argument_type(schema: dict[str, Any]) -> str:
    direct_type = schema.get("type")
    if isinstance(direct_type, str):
        return direct_type
    variants = schema.get("anyOf")
    if isinstance(variants, list):
        types = [item.get("type") for item in variants if isinstance(item, dict)]
        return " | ".join(value for value in types if isinstance(value, str))
    return ""


def _tool_arguments(tool_obj) -> list[ToolArgumentItem]:
    schema_model = tool_obj.tool_call_schema
    schema = schema_model.model_json_schema() if schema_model is not None else {}
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    return [
        ToolArgumentItem(
            name=name,
            type=_argument_type(details),
            description=str(details.get("description") or ""),
            required=name in required,
        )
        for name, details in properties.items()
        if isinstance(details, dict)
    ]


def list_tools(category: str | None = None) -> list[ToolCatalogItem]:
    _load_builtin_tools()
    items: list[ToolCatalogItem] = []
    for tool_obj in get_registered_tools():
        extra = get_tool_metadata(tool_obj.name)
        tool_category = extra.category if extra is not None else "builtin"
        if category is not None and tool_category != category:
            continue
        metadata = dict(tool_obj.metadata or {})
        display_name = (
            extra.display_name
            if extra is not None and extra.display_name
            else str(metadata.get("name") or tool_obj.name)
        )
        items.append(
            ToolCatalogItem(
                slug=tool_obj.name,
                name=display_name,
                description=tool_obj.description,
                metadata=metadata,
                args=_tool_arguments(tool_obj),
                category=tool_category,
                tags=list(extra.tags) if extra is not None else [],
                icon=extra.icon if extra is not None else "",
                config_guide=extra.config_guide if extra is not None else "",
            )
        )
    return items


def list_tool_options() -> list[ToolOptionItem]:
    return [ToolOptionItem(label=item.name, value=item.slug) for item in list_tools()]
