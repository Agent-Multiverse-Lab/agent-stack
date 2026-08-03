from server.service.agent_run_service import (
    _build_agent_run_event,
    _decode_event_fields,
    agent_run_cancel_key,
    agent_run_event_stream_key,
)


def test_agent_run_keys_and_event_payload():
    assert agent_run_event_stream_key("r1") == "run:events:r1"
    assert agent_run_cancel_key("r1") == "run:cancel:r1"

    payload = _build_agent_run_event("r1", {"type": "status"})

    assert payload["scope"] == "agent_run"
    assert payload["run_id"] == "r1"
    assert payload["type"] == "status"
    assert "created_at" in payload


def test_decode_event_fields_from_redis_bytes():
    payload = _decode_event_fields({b"event": b'{"type":"done"}'})

    assert payload == {"type": "done"}
