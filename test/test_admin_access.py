"""部署配置拥有的模型管理管理员权限测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from server.utils.auth import get_current_admin_user, is_admin_user
from src.configs import config


class AdminAccessTest(unittest.IsolatedAsyncioTestCase):
    async def test_admin_email_matching_is_trimmed_and_case_insensitive(self):
        user = SimpleNamespace(email="Admin@Example.com")
        with patch.object(
            config,
            "admin_emails",
            " owner@example.com, admin@example.com ",
        ):
            self.assertTrue(is_admin_user(user))
            self.assertIs(user, await get_current_admin_user(user))

    async def test_non_admin_is_forbidden(self):
        user = SimpleNamespace(email="member@example.com")
        with patch.object(config, "admin_emails", "admin@example.com"):
            self.assertFalse(is_admin_user(user))
            with self.assertRaises(HTTPException) as error:
                await get_current_admin_user(user)
        self.assertEqual(error.exception.status_code, 403)
