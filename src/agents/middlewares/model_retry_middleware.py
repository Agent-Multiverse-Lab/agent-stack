from langchain.agents.middleware import ModelRetryMiddleware


def create_model_retry_middleware() -> ModelRetryMiddleware:
    """创建模型调用重试中间件。"""

    # TODO 需要根据不同的类型去走不同的retry 规则，是云端的错误或者其他的，云上模型还有可能欠费啥的


    return ModelRetryMiddleware(max_retries=1, on_failure="continue")
