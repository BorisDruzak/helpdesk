import asyncio

from pc_agent.core.registry import ModuleRegistry
from pc_agent.modules.impl.presence import PresenceCollector
from shared.builtin_tool_descriptors import (
    PRESENCE_COLLECT_OUTPUT_CONTRACT,
    PRESENCE_COLLECT_OUTPUT_SCHEMA,
    PRESENCE_COLLECT_PRESENTATION_SCHEMA,
)


def _collect() -> dict:
    return asyncio.run(PresenceCollector().collect())


def test_presence_collect_returns_privacy_safe_shape():
    result = _collect()

    assert result["schema_version"] == "1.0"
    assert result["collected_at"]
    assert result["agent"]["online"] is True
    assert result["agent"]["connection_state"] == "connected"
    assert "current_user" in result["session"]
    assert result["session"]["session_state"] in {"active", "idle", "locked", "logged_out", "unknown"}
    assert isinstance(result["session"]["idle_seconds"], int)
    assert result["today"]["date"]
    assert isinstance(result["warnings"], list)


def test_presence_collect_does_not_expose_prohibited_content_fields():
    result = _collect()
    serialized_keys = repr(result).lower()

    for prohibited in [
        "screenshot",
        "keystroke",
        "mouse_coordinates",
        "browser_history",
        "full_urls",
        "document_contents",
        "clipboard_contents",
        "messages",
        "window_title",
    ]:
        assert prohibited not in serialized_keys


def test_presence_collect_descriptor_contract_and_presentation_schema():
    assert PRESENCE_COLLECT_OUTPUT_SCHEMA["properties"]["session"]["properties"]["idle_seconds"]["type"] == "integer"
    assert PRESENCE_COLLECT_OUTPUT_CONTRACT["kind"] == "device.presence.snapshot"
    assert PRESENCE_COLLECT_OUTPUT_CONTRACT["device_card"]["slots"] == ["presence", "agent", "activity"]
    block_ids = {block.get("id") for block in PRESENCE_COLLECT_PRESENTATION_SCHEMA["blocks"]}
    assert {"presence_current", "presence_today"} <= block_ids
    assert PRESENCE_COLLECT_PRESENTATION_SCHEMA["fallback"]["show_raw_json"] is True


def test_presence_collect_is_registered_with_schemas():
    registry = ModuleRegistry()
    registry.reset()
    try:
        registry.register(PresenceCollector())
        entry = next(item for item in registry.get_tools_flat() if item["tool"] == "presence.collect")
    finally:
        registry.reset()

    spec = entry["spec"]
    assert spec["output_schema"] == PRESENCE_COLLECT_OUTPUT_SCHEMA
    assert spec["output_contract"]["kind"] == "device.presence.snapshot"
    assert spec["presentation_schema"] == PRESENCE_COLLECT_PRESENTATION_SCHEMA
