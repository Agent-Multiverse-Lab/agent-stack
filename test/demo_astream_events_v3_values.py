import asyncio
from pprint import pprint

from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain.tools import tool

from src.model import load_model
from src.configs import config


@tool
def add_numbers(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


async def main() -> None:
    agent = create_agent(
        model=load_model(config.default_model),
        tools=[add_numbers],
        system_prompt="当需要计算式调用add_numbers工具.",
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
        version="v3",
    )

    async with stream:
        async for event in stream:
            print(f"\nmethod:{event["method"]}")
            print(f"\npayload (event['params']为):{event["params"]}")
            print("-" * 80)


if __name__ == "__main__":
    asyncio.run(main())
