from langchain.agents.middleware import ModelRetryMiddleware


def create_model_retry_middleware() -> ModelRetryMiddleware:
    """创建模型调用重试中间件。"""

    return ModelRetryMiddleware(max_retries=1, on_failure="continue")
