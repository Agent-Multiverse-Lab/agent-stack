import asyncio
from typing import Any

from langchain.tools import tool
from langchain_tavily import TavilySearch

from src.configs import config as sys_config
from src.knowledge import KnowledgeFactory, KnowledgeSearch
from src.knowledge.store.milvus.config import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TOP_K,
)


def _build_tavily_tool(max_results: int = 5) -> TavilySearch:
    return TavilySearch(
        max_results=max_results,
        tavily_api_key=sys_config.tavily_api_key or None,
    )


@tool(description="Run one focused web search query.")
async def web_search_one(query: str) -> Any:
    search_tool = _build_tavily_tool(max_results=5)
    return await search_tool.ainvoke({"query": query})


@tool(description="Run multiple focused web search queries concurrently.")
async def web_search_parallel(queries: list[str]) -> list[dict[str, Any]]:
    tasks = [web_search_one.ainvoke({"query": query}) for query in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid_results = []
    for query, result in zip(queries, results, strict=False):
        if isinstance(result, Exception):
            valid_results.append(
                {
                    "query": query,
                    "error": str(result),
                    "results": [],
                }
            )
        else:
            valid_results.append(
                {
                    "query": query,
                    "result": result,
                }
            )

    return valid_results


@tool(description="Search the local Milvus knowledge base with a dense vector.")
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
