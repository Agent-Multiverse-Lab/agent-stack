from typing import Any

from langchain_tavily import TavilySearch

from src.agents.tool_registry import ToolMetadata, register, register_tool
from src.configs import config as sys_config
from src.knowledge import KnowledgeFactory, KnowledgeSearch
from src.knowledge.store.milvus.config import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TOP_K,
)


def _build_tavily_tool(max_results: int = 5) -> TavilySearch:
    return TavilySearch(
        name="web_search",
        max_results=max_results,
        tavily_api_key=sys_config.tavily_api_key or None,
    )


web_search = register_tool(
    _build_tavily_tool(max_results=5),
    ToolMetadata(
        category="knowledge",
        tags=["搜索"],
        display_name="网络搜索",
        config_guide="在服务端配置 TAVILY_API_KEY。",
    ),
)


@register(
    description="Search the local Milvus knowledge base with a dense vector.",
    category="knowledge",
    tags=["知识库"],
    display_name="知识库检索",
)
async def knowledge_search(
    vector: list[float],
    collection_name: str = DEFAULT_COLLECTION_NAME,
    limit: int = DEFAULT_TOP_K,
    similarity_threshold: float | None = DEFAULT_SIMILARITY_THRESHOLD,
) -> dict[str, Any]:
    knowledge = KnowledgeFactory.create("milvus")
    result = await knowledge.search(
        KnowledgeSearch(
            vector=vector,
            limit=limit,
            options={
                "collection_name": collection_name,
                "similarity_threshold": similarity_threshold,
            },
        )
    )
    return {
        "reference_context": {
            "project_history": [],
            "material_refs": [],
            "knowledge_refs": [
                {
                    "collection_name": collection_name,
                    "vector_dimension": len(vector),
                    "content": result,
                }
            ],
            "web_refs": [],
            "local_file_refs": [],
        },
        "recommended_usage": {
            "must_follow": [],
            "can_use": ["Use knowledge_refs as local Milvus reference context."],
            "avoid": [],
        },
        "search_notes": [],
    }
