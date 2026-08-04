"""Agent 输入消息 metadata 透传测试。"""

import unittest

from server.service.input_message_service import build_agent_input_msg

FILE_ID = "759b114e-90d6-42d2-a052-bdccaa40c7b6"


class InputMessageServiceTest(unittest.TestCase):
    def test_file_ids_are_forwarded_without_content_expansion(self):
        message = build_agent_input_msg(
            query="请分析",
            msg_metadata={"file_ids": [FILE_ID], "source": "web"},
        )

        self.assertEqual("请分析", message.langchain_msg.content)
        self.assertEqual(
            {"file_ids": [FILE_ID], "source": "web"},
            message.langchain_msg.additional_kwargs,
        )

    def test_file_only_input_is_valid(self):
        message = build_agent_input_msg(
            msg_metadata={"file_ids": [FILE_ID]},
        )

        self.assertEqual("attachment", message.msg_type)
        self.assertEqual("", message.langchain_msg.content)
        self.assertEqual(
            [FILE_ID],
            message.langchain_msg.additional_kwargs["file_ids"],
        )

    def test_file_ids_must_be_a_list(self):
        with self.assertRaisesRegex(ValueError, "必须是列表"):
            build_agent_input_msg(msg_metadata={"file_ids": FILE_ID})

    def test_empty_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Agent 输入不能为空"):
            build_agent_input_msg(msg_metadata={})


if __name__ == "__main__":
    unittest.main()
