"""图像 Agent 的 MCP 可用性与内嵌图片校验。"""

import asyncio
import base64
from io import BytesIO

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from PIL import Image


class ImageValidationMiddleware(AgentMiddleware):
    """检查实际返回的图片字节；远程引用和内容语义不在本地验证。"""

    @staticmethod
    def validate_mcp_tools(tools, server_names, configured_servers, server_errors):
        for name in server_names:
            if name not in configured_servers:
                raise ValueError(f"图像处理 MCP 服务未配置或未启用：{name}")
            if name in server_errors:
                raise ValueError(f"图像处理 MCP 服务加载失败：{name}")
        if not tools:
            raise ValueError("图像处理 Agent 没有可用的 MCP 工具，请检查服务配置和连接状态")

    async def awrap_tool_call(self, request, handler):
        try:
            result = await handler(request)
        except Exception as exc:
            return ToolMessage(
                content=f"MCP 工具执行失败（{type(exc).__name__}），未获得有效图像处理结果。",
                name=request.tool_call["name"],
                tool_call_id=request.tool_call["id"],
                status="error",
            )
        if not isinstance(result, ToolMessage) or result.status == "error":
            return result
        try:
            checks = await asyncio.to_thread(self._check_images, result.content)
        except (ValueError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            return ToolMessage(
                content=f"MCP 返回的图片未通过文件校验：{exc}",
                name=result.name,
                tool_call_id=result.tool_call_id,
                status="error",
            )
        if not checks:
            checks = ["未获得可校验的图片字节；文本、URL、路径或资产 ID 不代表文件完整性已通过。"]
        content = list(result.content) if isinstance(result.content, list) else [
            {"type": "text", "text": result.content}
        ]
        content.append({"type": "text", "text": "图片校验：" + "；".join(checks)})
        return result.model_copy(update={"content": content})

    @staticmethod
    def _check_images(content):
        checks = []
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict) or block.get("type") != "image":
                continue
            encoded = block.get("base64")
            if encoded is None:
                checks.append("图片仅提供引用，文件内容尚未校验")
                continue
            # 有界解码，避免把大幅遥感原图在 Agent 进程中整幅读入。
            if not isinstance(encoded, str) or len(encoded) > 28_000_000:
                raise ValueError("图片编码类型无效或超过内嵌图片校验大小限制")
            data = base64.b64decode(encoded, validate=True)
            with Image.open(BytesIO(data)) as image:
                if image.width * image.height > 20_000_000:
                    raise ValueError("图片超过 2000 万像素，需使用支持分块读取的远程校验工具")
                if getattr(image, "n_frames", 1) != 1:
                    raise ValueError("多帧图片需要使用支持逐帧检查的远程校验工具")
                image_format = image.format
                size = image.size
                mime = Image.MIME.get(image_format)
                if block.get("mime_type") and block["mime_type"] != mime:
                    raise ValueError("声明的 MIME 类型与实际图片格式不一致")
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
            checks.append(
                f"{image_format} {size[0]}×{size[1]} 文件可完整解码；内容是否符合任务仍需核验"
            )
        return checks
