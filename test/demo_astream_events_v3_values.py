import asyncio
from pprint import pprint

from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver


@tool
def add_numbers(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


async def main() -> None:
    from src.configs import config
    from src.model import load_model

    run_config = {"configurable": {"thread_id": "astream-events-v3-values-demo"}}
    agent = create_agent(
        model=load_model(config.default_model),
        tools=[add_numbers],
        system_prompt="处理加法计算时必须调用 add_numbers 工具。",
        checkpointer=InMemorySaver(),
    )
    stream = await agent.astream_events(
        {
            "messages": [
                HumanMessage(
                    content="请调用 add_numbers 计算 17 + 25，并告诉我最终答案。"
                )
            ]
        },
        config=run_config,
        version="v3",
    )

    async with stream:
        async for event in stream:
            print(f"\nmethod: {event['method']}")
            pprint(event["params"], sort_dicts=False, width=120)
            print("-" * 80)

    state = await agent.aget_state(run_config)
    messages = state.values.get("messages", [])

    print("\nToolCall ID 核验:")
    for message in messages:
        if message.type == "ai":
            for tool_call in message.tool_calls:
                print(f"AIMessage.tool_calls[].id = {tool_call.get('id')!r}")
        elif message.type == "tool":
            print(f"ToolMessage.tool_call_id = {message.tool_call_id!r}")

    print("\n完整 graph state messages:")
    for index, message in enumerate(messages):
        print(f"[{index}] {type(message).__name__}")
        pprint(message.model_dump() if hasattr(message, "model_dump") else message)
        print("-" * 80)


if __name__ == "__main__":
    asyncio.run(main())
