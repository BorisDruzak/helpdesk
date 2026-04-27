from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.db import get_session
from app.db.models import AgentRuntimeAudit
from observer.service import ObserverOverlayService, TraceOverlayFilters


SUPPORT_TOKEN = "test-ui-support-token"


@pytest.mark.asyncio
async def test_repeated_missing_auth_creates_rate_limited_web_auth_trace(test_client, monkeypatch) -> None:
    import auth.middleware as auth_middleware_module

    async def _no_auth(_request):
        return None

    auth_middleware_module._WEB_AUTH_AUDIT_LAST_SEEN.clear()
    monkeypatch.setattr(auth_middleware_module, "extract_auth_context", _no_auth)

    first = await test_client.get("/api/tickets")
    second = await test_client.get("/api/tickets")
    assert first.status == 401
    assert second.status == 401

    async with get_session() as session:
        rows = (
            await session.execute(
                sa.select(AgentRuntimeAudit).where(AgentRuntimeAudit.event_type == "web_auth_failed")
            )
        ).scalars().all()
        assert len(rows) == 1
        trace_id = (await ObserverOverlayService(session)._trace_ids_for_runtime_audits(rows))[0]
        assert trace_id
        trace = await ObserverOverlayService(session).project_trace(trace_id, force=True)
        await session.commit()

    assert trace is not None
    assert trace.root_kind == "web_auth"
    assert trace.status == "warning"

    async with get_session() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(root_kind="web_auth", query="AUTH_REQUIRED", route="/api/tickets"),
            limit=10,
        )

    assert len(traces) == 1
    assert traces[0]["root_kind"] == "web_auth"


@pytest.mark.asyncio
async def test_forbidden_role_creates_searchable_web_auth_signature(test_client) -> None:
    import auth.middleware as auth_middleware_module

    auth_middleware_module._WEB_AUTH_AUDIT_LAST_SEEN.clear()
    response = await test_client.get(
        "/api/web/admin/observer/quick",
        headers={"Authorization": f"Bearer {SUPPORT_TOKEN}"},
    )
    assert response.status == 403

    async with get_session() as session:
        rows = (
            await session.execute(
                sa.select(AgentRuntimeAudit).where(AgentRuntimeAudit.event_type == "web_auth_forbidden")
            )
        ).scalars().all()
        assert rows
        trace_id = (await ObserverOverlayService(session)._trace_ids_for_runtime_audits(rows))[0]
        assert trace_id
        await ObserverOverlayService(session).project_trace(trace_id, force=True)
        await session.commit()

    async with get_session() as session:
        occurrences = (
            await session.execute(
                sa.text(
                    "SELECT component, error_kind, failure_stage, severity "
                    "FROM observer_error_occurrences WHERE error_kind = 'FORBIDDEN'"
                )
            )
        ).mappings().all()
        assert occurrences
        assert occurrences[0]["component"] == "agent_runtime_audit"
        assert occurrences[0]["failure_stage"] == "web_auth_forbidden"
        assert occurrences[0]["severity"] == "warning"
