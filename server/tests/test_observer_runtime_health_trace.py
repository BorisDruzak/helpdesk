from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.db import get_session
from app.db.models import AgentRuntimeAudit
from observer.runtime import ObserverRefreshRuntime
from observer.service import ObserverOverlayService


pytestmark = pytest.mark.db_cleanup("observer_diagnostics")

@pytest.mark.asyncio
async def test_observer_runtime_degraded_health_emits_trace_visible_audit() -> None:
    runtime = ObserverRefreshRuntime(max_batch=1)
    runtime._stats.last_error = "projection failed in test"
    runtime._stats.consecutive_failures = 2

    trace_id = await runtime._emit_self_health_if_degraded()
    assert trace_id

    async with get_session() as session:
        rows = (
            await session.execute(
                sa.select(AgentRuntimeAudit).where(AgentRuntimeAudit.event_type == "observer_runtime_degraded")
            )
        ).scalars().all()
        assert len(rows) == 1
        trace = await ObserverOverlayService(session).project_trace(trace_id, force=True)
        await session.commit()

    assert trace is not None
    assert trace.root_kind == "observer_runtime"
    assert trace.status == "error"

    async with get_session() as session:
        occurrences = (
            await session.execute(
                sa.text(
                    "SELECT error_kind, failure_stage, severity "
                    "FROM observer_error_occurrences WHERE trace_id = :trace_id"
                ),
                {"trace_id": trace_id},
            )
        ).mappings().all()

    assert occurrences
    assert occurrences[0]["error_kind"] == "observer_runtime_degraded"
    assert occurrences[0]["severity"] == "error"


@pytest.mark.asyncio
async def test_observer_runtime_self_health_audit_is_bounded_by_issue_key() -> None:
    runtime = ObserverRefreshRuntime(max_batch=1)
    runtime._stats.pending_trace_count = 100

    first_trace_id = await runtime._emit_self_health_if_degraded()
    second_trace_id = await runtime._emit_self_health_if_degraded()
    assert first_trace_id
    assert second_trace_id is None

    async with get_session() as session:
        count = await session.scalar(
            sa.select(sa.func.count()).select_from(AgentRuntimeAudit).where(
                AgentRuntimeAudit.event_type == "observer_runtime_degraded"
            )
        )

    assert count == 1
