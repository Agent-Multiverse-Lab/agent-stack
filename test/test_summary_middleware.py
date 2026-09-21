import unittest
from types import SimpleNamespace
from unittest.mock import patch

from deepagents.backends import CompositeBackend, FilesystemBackend
from langgraph.constants import TAG_NOSTREAM

from src.agents.base_context import BaseContext
from src.agents.middlewares.summary_middleware import (
    DEFAULT_SUMMARY_PROMPT,
    S2CSummarizationMiddleware,
    create_summary_middleware,
    create_summary_middleware_from_context,
)
from src.configs import config as sys_config


class _DummyModel:
    _llm_type = "test-chat"
    profile = {"max_input_tokens": 128_000}

    def _get_ls_params(self):
        return {"ls_provider": "test"}

    def with_retry(self, **_kwargs):
        return self

    def invoke(self, _prompt, config=None):
        return SimpleNamespace(text="summary")

    async def ainvoke(self, prompt, config=None):
        return self.invoke(prompt, config=config)


def _backend():
    return CompositeBackend(
        default=FilesystemBackend(root_dir=".", virtual_mode=True),
        routes={},
        artifacts_root="/workspace/outputs",
    )


class SummaryMiddlewareTest(unittest.TestCase):
    def test_factory_uses_workspace_output_paths_and_disables_streaming(self):
        middleware = create_summary_middleware(
            model=_DummyModel(),
            backend=_backend(),
            trigger=("tokens", 100 * 1024),
            keep=("messages", 10),
            summary_prompt=DEFAULT_SUMMARY_PROMPT,
            trim_tokens_to_summarize=100 * 1024,
        )

        self.assertIsInstance(middleware, S2CSummarizationMiddleware)
        self.assertEqual(
            middleware._history_path_prefix,
            "/workspace/outputs/conversation_history",
        )
        self.assertEqual(
            middleware._large_tool_results_prefix,
            "/workspace/outputs/large_tool_results",
        )
        self.assertIn(TAG_NOSTREAM, middleware._SUMMARY_INVOKE_CONFIG["tags"])

    def test_context_factory_maps_summary_configuration(self):
        context = BaseContext(
            summary_threshold=64,
            summary_keep_messages=8,
            summary_tool_result_token_limit=256,
        )
        model = _DummyModel()

        with patch(
            "src.agents.middlewares.summary_middleware.load_model",
            return_value=model,
        ) as load_model:
            middleware = create_summary_middleware_from_context(
                context,
                backend=_backend(),
            )

        load_model.assert_called_once_with(sys_config.default_model)
        self.assertEqual(middleware._lc_helper.trigger, ("tokens", 64 * 1024))
        self.assertEqual(middleware._lc_helper.keep, ("messages", 8))
        self.assertEqual(middleware.tool_result_offload_token_limit, 256)


if __name__ == "__main__":
    unittest.main()
