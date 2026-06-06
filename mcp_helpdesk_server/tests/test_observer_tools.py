from __future__ import annotations

import pytest

from mcp_helpdesk_server.schemas import redact_and_bound
from mcp_helpdesk_server.tools.observer_tools import observer_debug_bundle, observer_ticket_summary, observer_trace_detail


@pytest.mark.asyncio
async def test_observer_trace_detail_requires_trace_id() -> None:
    payload = await observer_trace_detail({})

    assert payload["status"] == "error"
    assert payload["error_code"] == "TRACE_ID_REQUIRED"


@pytest.mark.asyncio
async def test_observer_ticket_summary_requires_ticket_id() -> None:
    payload = await observer_ticket_summary({})

    assert payload["status"] == "error"
    assert payload["error_code"] == "TICKET_ID_REQUIRED"


@pytest.mark.asyncio
async def test_observer_debug_bundle_requires_locator_input(monkeypatch) -> None:
    async def fake_start() -> dict:
        return {"started": False}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def rollback(self):
            return None

    async def fake_bundle(session, filters):
        return {
            "status": "error",
            "error_code": "LOCATOR_INPUT_REQUIRED",
            "message": "Provide q, trace_id, ticket_id, operation_id, device_id, route, playbook_run_id or step_run_id.",
        }

    monkeypatch.setattr("mcp_helpdesk_server.tools.observer_tools.bootstrap.ensure_db_started", fake_start)
    monkeypatch.setattr("app.db.get_session", lambda: FakeSession())
    monkeypatch.setattr("observer.debug_facade.observer_debug_bundle_v2", fake_bundle)

    payload = await observer_debug_bundle({})

    assert payload["status"] == "error"
    assert payload["error_code"] == "LOCATOR_INPUT_REQUIRED"


def test_redaction_applies_to_nested_attrs() -> None:
    payload = redact_and_bound({"attrs": {"password": "secret", "nested": [{"authorization": "Bearer abc"}]}})

    assert "secret" not in str(payload)
    assert "Bearer abc" not in str(payload)
    assert payload["attrs"]["password"] == "***REDACTED***"


@pytest.mark.asyncio
async def test_include_agent_actions_returns_warning_without_ws_rpc(monkeypatch) -> None:
    from observer import debug_facade

    class FakeService:
        def __init__(self, session):
            self.session = session

        async def get_trace_detail(self, trace_id):
            return {"trace": {"trace_id": trace_id}, "spans": [], "span_links": [], "error_occurrences": []}

    monkeypatch.setattr(debug_facade, "ObserverOverlayService", FakeService)

    payload = await debug_facade.observer_trace_detail(object(), "trace-1", include_agent_actions=True)

    assert payload["status"] == "ok"
    assert "agent actions require live server runtime" in payload["agent_actions_warning"]
