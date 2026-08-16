import json
from typing import Any


def format_agent_run_sse(event_id: str, envelope: dict[str, Any]) -> str:
    """把 Agent Run Redis envelope 格式化为 SSE frame。"""

    event_type = str(envelope.get("event_type") or "message")
    payload = envelope.get("payload")
    data = dict(payload) if isinstance(payload, dict) else {"payload": payload}
    data.update(
        scope="agent_run",
        type=event_type,
        run_id=envelope.get("run_id"),
        thread_id=envelope.get("thread_id"),
        created_at=envelope.get("created_at"),
    )
    return (
        f"id: {event_id}\n"
        f"event: {event_type}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )
