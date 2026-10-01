from datetime import datetime, timezone
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
