"""Provider 连接到 LangChain ChatModel 的纯运行时适配测试。"""

import unittest
from unittest.mock import patch

from pydantic import SecretStr

from src.model.runtime import ModelConnection, create_chat_model


class ModelRuntimeTest(unittest.TestCase):
    def test_openai_compatible_connection_is_forwarded_without_mutation(self):
        connection = ModelConnection(
            provider_id="custom",
            model_id="org/chat-model",
            model_type="chatgpt",
            protocol="openai_compatible",
            base_url="https://models.example/v1",
            api_key=SecretStr("private-key"),
            extra_headers={"X-Tenant": SecretStr("tenant-1")},
            body_overrides={"temperature": 0.2, "metadata": {"mode": "fast"}},
        )

        with patch("src.model.runtime.ChatOpenAI", return_value=object()) as chat:
            result = create_chat_model(connection)

        self.assertIs(result, chat.return_value)
        chat.assert_called_once_with(
            model="org/chat-model",
            api_key="private-key",
            base_url="https://models.example/v1",
            default_headers={"X-Tenant": "tenant-1"},
            extra_body={"temperature": 0.2, "metadata": {"mode": "fast"}},
        )
        chat.call_args.kwargs["extra_body"]["metadata"]["mode"] = "changed"
        self.assertEqual(connection.body_overrides["metadata"]["mode"], "fast")
        self.assertNotIn("private-key", repr(connection))
