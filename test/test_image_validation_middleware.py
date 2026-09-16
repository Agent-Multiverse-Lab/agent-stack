import asyncio
import base64
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

from langchain_core.messages import ToolMessage
from PIL import Image

from src.agents.subagents.imageprocessingagent.middlewares import ImageValidationMiddleware


class ImageValidationMiddlewareTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.middleware = ImageValidationMiddleware()
        self.request = SimpleNamespace(tool_call={"name": "images_process", "id": "call-1"})

    def image_block(self):
        output = BytesIO()
        Image.new("RGB", (8, 6)).save(output, format="PNG")
        return {
            "type": "image",
            "base64": base64.b64encode(output.getvalue()).decode(),
            "mime_type": "image/png",
        }

    async def run_result(self, content, **kwargs):
        result = ToolMessage(content=content, tool_call_id="call-1", **kwargs)
        return await self.middleware.awrap_tool_call(
            self.request, AsyncMock(return_value=result)
        )

    async def test_valid_image_preserves_content_and_artifact(self):
        block = self.image_block()
        artifact = {"structured_content": {"asset_id": "output-1"}}
        result = await self.run_result([block], artifact=artifact)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.content[0], block)
        self.assertEqual(result.artifact, artifact)
        self.assertIn("8×6", result.content[-1]["text"])

    async def test_corrupt_and_mislabeled_images_are_errors(self):
        corrupt = self.image_block()
        raw = base64.b64decode(corrupt["base64"])
        corrupt["base64"] = base64.b64encode(raw[:45]).decode()
        mismatch = self.image_block()
        mismatch["mime_type"] = "image/jpeg"
        invalid = self.image_block()
        invalid["base64"] = "not base64!"
        for block in (corrupt, mismatch, invalid):
            with self.subTest(block=block):
                result = await self.run_result([block])
                self.assertEqual(result.status, "error")
                self.assertEqual(result.tool_call_id, "call-1")

    async def test_reference_is_not_reported_as_verified(self):
        result = await self.run_result([{"type": "image", "url": "https://example.org/a.png"}])
        self.assertIn("尚未校验", result.content[-1]["text"])

    async def test_text_and_structured_results_are_preserved_but_not_verified(self):
        artifact = {"structured_content": {"width": 8}}
        result = await self.run_result("done", artifact=artifact)
        self.assertEqual(result.artifact, artifact)
        self.assertIn("未获得可校验", result.content[-1]["text"])

    async def test_tool_error_and_cancellation(self):
        result = await self.middleware.awrap_tool_call(
            self.request, AsyncMock(side_effect=TimeoutError("private endpoint"))
        )
        self.assertEqual(result.status, "error")
        self.assertIn("TimeoutError", result.content)
        self.assertNotIn("private endpoint", result.content)
        with self.assertRaises(asyncio.CancelledError):
            await self.middleware.awrap_tool_call(
                self.request, AsyncMock(side_effect=asyncio.CancelledError())
            )
        error = ToolMessage(content="MCP rejected input", tool_call_id="call-1", status="error")
        self.assertIs(
            await self.middleware.awrap_tool_call(self.request, AsyncMock(return_value=error)),
            error,
        )

    def test_mcp_availability(self):
        check = self.middleware.validate_mcp_tools
        check([object()], ["images"], ["images"], {})
        for tools, selected, configured, errors in (
            ([], [], [], {}),
            ([object()], ["missing"], ["images"], {}),
            ([object()], ["broken"], ["broken"], {"broken": "timeout"}),
        ):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                check(tools, selected, configured, errors)


if __name__ == "__main__":
    unittest.main()
