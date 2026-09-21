import unittest
from types import SimpleNamespace

from src.agents.base_context import BaseContext
from src.agents.middlewares.subagent_middlware import SubAgentMiddleware


class SubAgentMiddlewarePromptTest(unittest.TestCase):
    def setUp(self):
        self.middleware = SubAgentMiddleware(
            subagents=[
                SimpleNamespace(
                    name="SearchAgent",
                    description="搜索和整理外部资料",
                )
            ],
            parent_context=BaseContext(),
        )
        self.tools = {tool.name: tool for tool in self.middleware.tools}

    def test_system_prompt_contains_usage_rules_and_available_agents(self):
        prompt = self.middleware._system_prompt()

        self.assertIn("多个互不依赖的子任务可以并行", prompt)
        self.assertIn("subagent_start", prompt)
        self.assertIn("- SearchAgent: 搜索和整理外部资料", prompt)

    def test_task_schema_matches_model_visible_argument_names(self):
        task_tool = self.tools["task"]
        schema = task_tool.args_schema.model_json_schema()

        self.assertEqual(schema["required"], ["description", "subagent_slug"])
        self.assertIn("SearchAgent", task_tool.description)


if __name__ == "__main__":
    unittest.main()
