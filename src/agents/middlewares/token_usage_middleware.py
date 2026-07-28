"""Token usage observation middleware."""

from collections.abc import Awaitable, Callable, Mapping
from typing import NotRequired, TypedDict

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
)
from langchain.messages import AIMessage
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.types import Command


class TokenUsageSnapshot(TypedDict):
    """最近一次模型调用的轻量 token 快照。"""

    estimated_input_tokens: int
    message_count: int
    tool_count: int
    model_usage: dict[str, int]


class TokenUsageState(AgentState):
    token_usage: NotRequired[TokenUsageSnapshot]


class TokenUsageMiddleware(AgentMiddleware[TokenUsageState]):
    """调用模型后，把估算输入量和供应商 usage 写入 Agent state。"""

    state_schema = TokenUsageState

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ExtendedModelResponse:
        response = handler(request)
        return self._with_usage(request, response)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ExtendedModelResponse:
        response = await handler(request)
        return self._with_usage(request, response)

    def _with_usage(
        self,
        request: ModelRequest,
        response: ModelResponse,
    ) -> ExtendedModelResponse:
        messages = [request.system_message] if request.system_message else []
        messages.extend(request.messages)
        snapshot: TokenUsageSnapshot = {
            "estimated_input_tokens": count_tokens_approximately(
                messages,
                tools=request.tools,
            ),
            "message_count": len(messages),
            "tool_count": len(request.tools),
            "model_usage": self._model_usage(response),
        }
        return ExtendedModelResponse(
            model_response=response,
            command=Command(update={"token_usage": snapshot}),
        )

    @staticmethod
    def _model_usage(response: ModelResponse) -> dict[str, int]:
        for message in reversed(response.result):
            if not isinstance(message, AIMessage):
                continue
            usage = message.usage_metadata
            if isinstance(usage, Mapping):
                return {
                    str(key): value
                    for key, value in usage.items()
                    if isinstance(value, int)
                }
        return {}


def create_token_usage_middleware() -> TokenUsageMiddleware:
    """创建 token usage 观测 middleware。"""
    return TokenUsageMiddleware()
