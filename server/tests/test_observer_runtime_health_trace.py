from __future__ import annotations

from unittest.mock import Mock

import pytest

from observer.runtime import ObserverRefreshRuntime


pytestmark = pytest.mark.db_cleanup("observer_diagnostics")

@pytest.mark.asyncio
async def test_observer_runtime_degraded_health_stays_local_after_agent_audit_retirement() -> None:
    runtime = ObserverRefreshRuntime(max_batch=1)
    runtime._stats.last_error = "projection failed in test"
    runtime._stats.consecutive_failures = 2

    assert await runtime._emit_self_health_if_degraded() is None
    assert runtime._last_self_health_key == "last_error"


@pytest.mark.asyncio
async def test_observer_runtime_self_health_log_is_bounded_by_issue_key(monkeypatch) -> None:
    runtime = ObserverRefreshRuntime(max_batch=1)
    runtime._stats.pending_trace_count = 100
    warnings = Mock()
    monkeypatch.setattr("observer.runtime.logger", warnings)

    first_trace_id = await runtime._emit_self_health_if_degraded()
    second_trace_id = await runtime._emit_self_health_if_degraded()
    assert first_trace_id is None
    assert second_trace_id is None
    warnings.warning.assert_called_once_with("[observer_refresh] degraded: pending_backlog")
