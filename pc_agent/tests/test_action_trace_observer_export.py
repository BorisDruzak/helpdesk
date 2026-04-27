from __future__ import annotations

from pathlib import Path

import pytest

from pc_agent.core.action_trace import ActionTraceRecorder


@pytest.mark.no_db
def test_action_trace_exports_stable_redacted_observer_events(tmp_path: Path) -> None:
    recorder = ActionTraceRecorder(tmp_path)
    context = recorder.context(
        source="ws_agent",
        action="connect",
        category="runtime",
        trace_id="00000000-0000-0000-0000-00000000ac01",
        operation_id="00000000-0000-0000-0000-00000000ac02",
        tool_name="diag.logs.collect",
    )
    recorder.record(
        context,
        stage="handshake",
        status="error",
        summary="handshake failed",
        details={"token": "secret-token-value", "reason": "invalid token"},
    )

    first = recorder.export_observer_events(after_seq=None, limit=10)
    second = recorder.export_observer_events(after_seq=None, limit=10)

    assert len(first) == 1
    assert first == second
    event = first[0]
    assert event["event_type"] == "agent.ws.handshake_sent"
    assert event["root_kind"] == "agent_runtime"
    assert event["severity"] == "error"
    assert event["trace_id"] == "00000000-0000-0000-0000-00000000ac01"
    assert event["operation_id"] == "00000000-0000-0000-0000-00000000ac02"
    assert event["tool_name"] == "diag.logs.collect"
    assert event["attrs_json"]["token"] != "secret-token-value"
    assert event["attrs_json"]["reason"] == "invalid token"


@pytest.mark.no_db
def test_action_trace_export_respects_cursor_and_limit(tmp_path: Path) -> None:
    recorder = ActionTraceRecorder(tmp_path)
    runtime_context = recorder.context(source="ws_agent", action="connect", category="runtime")
    update_context = recorder.context(source="launcher", action="apply_update", category="update")
    module_context = recorder.context(source="module_manager", action="install", category="module")

    first_row = recorder.record(runtime_context, stage="startup", status="ok")
    recorder.record(update_context, stage="apply", status="warning")
    recorder.record(module_context, stage="install_step", status="error")

    after_first_seq = int(first_row["seq"])
    exported = recorder.export_observer_events(after_seq=after_first_seq, limit=1)

    assert len(exported) == 1
    assert exported[0]["event_type"] == "agent.update.apply"
    assert exported[0]["root_kind"] == "agent_update"
    assert int(exported[0]["attrs_json"]["action_trace_seq"]) > after_first_seq
