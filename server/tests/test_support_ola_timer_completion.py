"""Stopped OLA clocks must remain completed after their deadline passes."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from web_api.support_handlers import _build_support_sla_ola_payload

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize("late", [False, True])
def test_completed_ola_timers_do_not_resume_countdown(late):
    started = datetime(2026, 11, 10, tzinfo=timezone.utc)
    due = started + timedelta(minutes=3)
    stopped = due + timedelta(seconds=1 if late else -1)
    ticket = SimpleNamespace(
        created_at=started,
        ola_started_at=started,
        ola_ack_due_at=due,
        ola_processing_due_at=due,
        ola_ack_at=stopped,
        ola_processing_at=stopped,
    )
    result = _build_support_sla_ola_payload(ticket, now=due + timedelta(days=1))
    for timer in (result.ola_ack, result.ola_processing):
        assert timer.status == "completed"
        assert timer.completed_at == stopped.isoformat()
        assert timer.completed_within_target is not late
        assert timer.remaining_seconds is None


def test_assignment_stops_only_acknowledgement_clock():
    started = datetime(2026, 11, 10, tzinfo=timezone.utc)
    ticket = SimpleNamespace(
        created_at=started,
        ola_started_at=started,
        ola_ack_due_at=started + timedelta(minutes=3),
        ola_processing_due_at=started + timedelta(minutes=20),
        ola_ack_at=started + timedelta(minutes=1),
        ola_processing_at=None,
    )
    result = _build_support_sla_ola_payload(ticket, now=started + timedelta(minutes=4))
    assert result.ola_ack.status == "completed"
    assert result.ola_processing.status != "completed"
    assert result.ola_processing.remaining_seconds == 16 * 60
