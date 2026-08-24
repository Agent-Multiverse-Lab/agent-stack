import asyncio
from pprint import pprint

from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from src.configs import config
from src.model import load_model


@tool
def add_numbers(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


async def main() -> None:
    run_config = {"configurable": {"thread_id": "astream-events-v3-values-demo"}}
    agent = create_agent(
        model=load_model(config.default_model),
        tools=[add_numbers],
        system_prompt="当需要计算式调用add_numbers工具.",
        checkpointer=InMemorySaver(),
    )

    stream = await agent.astream_events(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "调用计算工具add_numbers计算下 17 + 25, "
                        "计算完成后直接输出结果."
                    )
                )
            ]
        },
        config=run_config,
        version="v3",
    )

    async with stream:
        async for event in stream:
            print(f"\nmethod:{event["method"]}")
            print(f"\npayload (event['params']为):{event["params"]}")
            print("-" * 80)

    state = await agent.aget_state(run_config)
    messages = state.values.get("messages", [])

    print("\n运行完成后的 graph state messages:")
    print("=" * 80)
    for index, message in enumerate(messages):
        print(f"[{index}] {type(message).__name__}")
        pprint(message.model_dump() if hasattr(message, "model_dump") else message)
        print("-" * 80)


if __name__ == "__main__":
    asyncio.run(main())
