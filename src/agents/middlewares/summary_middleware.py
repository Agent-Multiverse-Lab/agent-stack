"""Conversation summarization middleware."""

from deepagents.middleware.summarization import Command, ContextOverflowError, SummarizationMiddleware
from langchain.agents.middleware.summarization import _DEFAULT_MESSAGES_TO_KEEP, _DEFAULT_TRIM_TOKEN_LIMIT, DEFAULT_SUMMARY_PROMPT, ContextSize
from langchain.chat_models import BaseChatModel
from langchain_core.messages.utils import count_tokens_approximately

# TODO 需要重建，使用中出现流式信息被广播的问题
# TODO 同时，需要考虑压缩的边界，需要看下deepagent怎么做的


# class CustomSummarizationMiddleware(SummarizationMiddleware):
#     def __init__(self, model, *):
#         super().__init__()
    

# def create_summary_middleware(
#     model: str | BaseChatModel,
#     *,
#     trigger: ContextSize | list[ContextSize] = ("messages", 12),
#     keep: ContextSize = ("messages", 6),
# ) -> SummarizationMiddleware:
#     """创建对话摘要 middleware。"""
#     return SummarizationMiddleware(
#         model=model,
#         trigger=trigger,
#         keep=keep,
#     )

