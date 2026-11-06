from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from tickets import workflow_service

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize("source,target,expected", [
    ("in_progress", "resolved", {"resolved_at"}),
    ("resolved", "closed", {"closed_at", "resolution_at"}),
    ("new", "canceled", {"canceled_at"}),
    ("closed", "new", {"resolved_at", "closed_at", "resolution_at", "resolution_code", "root_cause", "canceled_at"}),
])
def test_transition_timestamps_and_reopen_resets(source, target, expected):
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    updates = workflow_service._build_transition_updates(SimpleNamespace(resolved_at=None), source, target, now, "reason")
    assert expected <= updates.keys()
    for key in expected:
        assert updates[key] == (None if source == "closed" and target == "new" else now)


def test_existing_resolution_time_is_preserved():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    result = workflow_service._build_transition_updates(SimpleNamespace(resolved_at=now), "in_progress", "resolved", now, None)
    assert "resolved_at" not in result


@pytest.mark.parametrize('resolved_late', [False, True])
def test_acceptance_after_deadline_preserves_actual_resolution_and_sla_outcome(resolved_late):
    from requester.ticket_handling import sla_timer
    due = datetime(2026, 11, 5, 13, 47, tzinfo=timezone.utc)
    resolved = due + timedelta(minutes=10) if resolved_late else due - timedelta(minutes=65)
    closed = due + timedelta(hours=15)
    row = SimpleNamespace(status='resolved', created_at=due-timedelta(hours=5),
        resolution_due_at=due, resolved_at=resolved, resolution_at=resolved,
        closed_at=None, canceled_at=None, sla_paused_at=None, sla_paused_seconds=0,
        resolution_breached_at=None)
    updates = workflow_service._build_transition_updates(row, 'resolved', 'closed', closed, None)
    assert updates['closed_at'] == closed
    assert 'resolution_at' not in updates
    row.__dict__.update(updates, status='closed')
    result = sla_timer(row, row.__dict__, resolution=True, now=closed)
    assert result['completed_at'] == resolved.isoformat()
    assert result['completed_within_target'] is (not resolved_late)


def test_close_without_stopped_resolution_uses_close_time_not_resolved_time():
    # A policy may intentionally stop resolution only on close.
    now = datetime(2026, 11, 6, tzinfo=timezone.utc)
    row = SimpleNamespace(resolved_at=now-timedelta(days=1), resolution_at=None)
    updates = workflow_service._build_transition_updates(row, 'resolved', 'closed', now, None)
    assert updates['resolution_at'] == now and updates['closed_at'] == now


def test_reopen_clears_previous_completion_before_new_cycle_closes():
    resolved = datetime(2026, 11, 5, tzinfo=timezone.utc)
    row = SimpleNamespace(resolved_at=resolved, resolution_at=resolved)
    reopened = resolved+timedelta(days=1)
    row.__dict__.update(workflow_service._build_transition_updates(row, 'closed', 'in_progress', reopened, None))
    assert row.resolution_at is None and row.resolved_at is None
    new_close = reopened+timedelta(hours=1)
    updates = workflow_service._build_transition_updates(row, 'in_progress', 'closed', new_close, None)
    assert updates['resolution_at'] == new_close
