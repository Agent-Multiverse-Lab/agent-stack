"""Agent model/tool call limit middleware configuration."""

from typing import Any

from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)


def create_call_limit_middleware() -> list[Any]:
    """创建一组仅限制单次 Agent Run 的 middleware。"""
    return [
        ModelCallLimitMiddleware(run_limit=5, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=8, exit_behavior="continue"),
        ToolCallLimitMiddleware(
            tool_name="web_search_parallel",
            run_limit=2,
            exit_behavior="continue",
        ),
    ]
