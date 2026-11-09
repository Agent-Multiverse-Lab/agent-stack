import unittest

from src.agents.base_context import BaseContext
from src.agents.middlewares.subagent_middlware import SubAgentMiddleware


class SubAgentMiddlewarePromptTest(unittest.TestCase):
    def setUp(self):
        self.middleware = SubAgentMiddleware(
            subagents=[
                {"slug": "search_agent", "name": "资料检索", "description": "搜索和整理外部资料"}
            ],
            parent_context=BaseContext(),
        )
        self.tools = {tool.name: tool for tool in self.middleware.tools}

    def test_system_prompt_contains_usage_rules_and_available_agents(self):
        prompt = self.middleware._system_prompt()

        self.assertIn("使用 `subagent_start` 启动子智能体任务", prompt)
        self.assertIn("subagent_start", prompt)
        self.assertIn("- search_agent (资料检索): 搜索和整理外部资料", prompt)

    def test_start_schema_matches_model_visible_argument_names(self):
        self.assertNotIn("task", self.tools)
        start_tool = self.tools["subagent_start"]
        schema = start_tool.args_schema.model_json_schema()

        self.assertEqual(schema["required"], ["description", "subagent_slug"])
        self.assertIn("search_agent", start_tool.description)


if __name__ == "__main__":
    unittest.main()
