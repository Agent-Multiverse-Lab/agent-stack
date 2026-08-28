from langchain_core.tools import tool
from langgraph.types import interrupt


# FIXEME: 第一版只支持由模型生成 question/options 的单选 ask_user。
@tool
def ask_user(question: str, options: list[str]) -> str:
    """当继续执行必须由用户从明确选项中选择时，暂停并向用户提问。"""

    return str(
        interrupt(
            {
                "kind": "ask_user",
                "question": question,
                "options": options,
            }
        )
    )
