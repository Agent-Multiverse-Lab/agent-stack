from langchain.agents import AgentState


class ImageProcessingAgentState(AgentState):
    """保存图像处理任务的消息和 MCP 工具结果。"""
