from collections.abc import Mapping


def reslove_thread_id(steam_agent_chunk: object, thread_id:str | None = None) -> str | None:
    
    if not isinstance(steam_agent_chunk, Mapping):
        return thread_id
    
    for source in (
        steam_agent_chunk,
        steam_agent_chunk.get("configurable"),
        steam_agent_chunk.get("metadata"),
        steam_agent_chunk.get("agent_execute_state"),
        steam_agent_chunk.get("meta"),
    ):
        if not isinstance(source, Mapping):
            continue
        thread_id: str = source.get("thread_id")  # ty: ignore[invalid-assignment]
        if isinstance(thread_id, str) and thread_id.strip():
            return thread_id.strip()
    
    return thread_id
