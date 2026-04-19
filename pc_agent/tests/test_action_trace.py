from __future__ import annotations

from pathlib import Path

from pc_agent.core.action_trace import (
    ActionTraceRecorder,
    record_external_action_trace,
    resolve_action_trace_text_filter,
)


def test_action_trace_recorder_writes_and_filters(tmp_path: Path) -> None:
    recorder = ActionTraceRecorder(tmp_path)
    context = recorder.context(
        source="gui_automation",
        action="ticket.tool.run",
        category="tool",
        action_id="action-1",
        ticket_id="ticket-1",
        tool_name="screen.collect",
    )
    recorder.record(context, stage="start", status="started", summary="tool start", details={"step": 1})
    recorder.record(context, stage="finish", status="ok", summary="tool done", details={"operation_id": "op-1"})

    rows = recorder.search(limit=10, action_id="action-1")
    assert len(rows) == 2
    assert rows[0]["status"] == "ok"
    assert rows[1]["status"] == "started"

    tool_rows = recorder.search(limit=10, ticket_id="ticket-1", tool_name="screen.collect")
    assert len(tool_rows) == 2
    assert all(row["ticket_id"] == "ticket-1" for row in tool_rows)


def test_action_trace_text_filter_matches_serialized_details(tmp_path: Path) -> None:
    recorder = ActionTraceRecorder(tmp_path)
    context = recorder.context(
        source="orchestrator",
        action="consent.decision",
        category="consent",
        consent_token="consent-1",
    )
    recorder.record(context, stage="response", status="denied", summary="consent denied", details={"reason": "ROLE_NOT_ALLOWED"})

    rows = recorder.search(limit=5, text="role_not_allowed")
    assert len(rows) == 1
    assert rows[0]["consent_token"] == "***REDACTED***"


def test_resolve_action_trace_text_filter_prefers_structured_ids_over_trace_id() -> None:
    assert (
        resolve_action_trace_text_filter(
            text=None,
            trace_id="trace-1",
            operation_id="op-1",
        )
        is None
    )
    assert (
        resolve_action_trace_text_filter(
            text=None,
            trace_id="trace-1",
            ticket_id="ticket-1",
        )
        is None
    )


def test_resolve_action_trace_text_filter_falls_back_to_trace_id_without_structured_ids() -> None:
    assert resolve_action_trace_text_filter(text=None, trace_id="trace-1") == "trace-1"
    assert resolve_action_trace_text_filter(text="explicit", trace_id="trace-1") == "explicit"


def test_record_external_action_trace_appends_launcher_compatible_entry(tmp_path: Path) -> None:
    payload = record_external_action_trace(
        data_root=tmp_path,
        source="launcher",
        action="agent.update.apply",
        category="update",
        operation_id="op-update-1",
        tool_name="update",
        stage="finish",
        status="ok",
        summary="update applied",
        details={"version": "3.1.18"},
    )

    assert payload["operation_id"] == "op-update-1"
    recorder = ActionTraceRecorder(tmp_path)
    rows = recorder.search(limit=10, operation_id="op-update-1", source="launcher")
    assert len(rows) == 1
    assert rows[0]["action"] == "agent.update.apply"
    assert rows[0]["summary"] == "update applied"


def test_action_trace_redacts_sensitive_details_and_context(tmp_path: Path) -> None:
    recorder = ActionTraceRecorder(tmp_path)
    context = recorder.context(
        source="orchestrator",
        action="consent.decision",
        category="consent",
        operation_id="op-redact-1",
        consent_token="consent-secret-token",
    )
    recorder.record(
        context,
        stage="finish",
        status="error",
        summary="denied",
        details={
            "access_token": "super-secret",
            "nested": {"password": "pw123"},
            "token_hash_prefix": "abc123",
        },
    )

    rows = recorder.search(limit=5, operation_id="op-redact-1")
    assert len(rows) == 1
    assert rows[0]["consent_token"] == "***REDACTED***"
    assert rows[0]["details"]["access_token"] == "***REDACTED***"
    assert rows[0]["details"]["nested"]["password"] == "***REDACTED***"
    assert rows[0]["details"]["token_hash_prefix"] == "abc123"
