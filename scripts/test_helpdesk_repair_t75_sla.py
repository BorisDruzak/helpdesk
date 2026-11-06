from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).parents[1] / 'server'))


def evidence():
    from scripts.helpdesk_repair_t75_sla import TICKET_ID
    start = datetime(2026, 11, 5, 8, 47, tzinfo=timezone.utc)
    stop, close = start+timedelta(hours=4), start+timedelta(days=1)
    row = SimpleNamespace(ticket_id=TICKET_ID, ticket_code='T-000075', status='closed',
        reopen_count=0, sla_paused_at=None, sla_paused_seconds=0, resolution_breached_at=None,
        resolution_at=close, resolved_at=stop, closed_at=close, resolution_due_at=start+timedelta(hours=5),
        custom_fields={'resolution_confirmation': {'pending': False, 'responded_option_id': 'confirm'}})
    events = [
        SimpleNamespace(id=1, event_type='sla_started', created_at=start, payload={'resolution_due_at': row.resolution_due_at.isoformat()}),
        SimpleNamespace(id=2, event_type='sla_resolution_stopped', created_at=stop, payload={'ticket_id': TICKET_ID, 'status': 'resolved', 'trigger': 'status_changed', 'stopped_at': stop.isoformat()}),
        SimpleNamespace(id=3, event_type='status_changed', created_at=stop+timedelta(milliseconds=10), payload={'from_status': 'in_progress', 'to_status': 'resolved'}),
        SimpleNamespace(id=4, event_type='status_changed', created_at=close+timedelta(milliseconds=10), payload={'from_status': 'resolved', 'to_status': 'closed', 'reason': 'requester_confirmed_resolution'}),
    ]
    return row, events


def test_plan_recovers_only_verified_sla_stop_and_is_idempotent():
    from scripts.helpdesk_repair_t75_sla import repair_plan
    row, events = evidence();before = deepcopy(row.__dict__)
    plan = repair_plan(row, events)
    assert plan['resolution_at'] == row.resolved_at.isoformat() and plan['changed']
    assert plan['source_event_id'] == 2 and row.__dict__ == before
    row.resolution_at = row.resolved_at
    assert repair_plan(row, events)['changed'] is False


@pytest.mark.parametrize('field,value', [('ticket_id', 'other'), ('ticket_code', 'T-000076'), ('status', 'resolved'),
    ('reopen_count', 1), ('sla_paused_seconds', 60), ('resolution_breached_at', datetime(2026, 11, 6, tzinfo=timezone.utc))])
def test_plan_rejects_other_tickets_or_changed_history(field, value):
    from scripts.helpdesk_repair_t75_sla import repair_plan
    row, events = evidence();setattr(row, field, value)
    with pytest.raises(ValueError):repair_plan(row, events)


def test_plan_rejects_duplicate_stop_changed_due_or_unconfirmed_close():
    from scripts.helpdesk_repair_t75_sla import repair_plan
    row, events = evidence()
    with pytest.raises(ValueError):repair_plan(row, [*events, deepcopy(events[1])])
    row.resolution_due_at += timedelta(minutes=1)
    with pytest.raises(ValueError):repair_plan(row, events)
    row, events = evidence();row.custom_fields['resolution_confirmation']['pending'] = True
    with pytest.raises(ValueError):repair_plan(row, events)


@pytest.mark.asyncio
async def test_repair_rejects_untrusted_actor_before_database():
    from scripts.helpdesk_repair_t75_sla import repair
    def forbidden():raise AssertionError('Must not open database')
    with pytest.raises(ValueError, match='admin'):
        await repair(forbidden, SimpleNamespace(is_admin=lambda: False, actor_id='x'), apply=True)


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [None, 'stale', 'audit', 'database'])
async def test_repair_transaction_preserves_acceptance_and_rolls_back_on_guards(monkeypatch, failure):
    from scripts.helpdesk_repair_t75_sla import repair
    from app.repos import ticket_events_repo
    row, events = evidence()
    row.device_id = None
    row.closure_feedback = {'rating': 5}
    for obj in [row, *events]:
        obj.__table__ = SimpleNamespace(columns=[SimpleNamespace(name=k) for k in obj.__dict__])
    commits, rollbacks = [], []
    @asynccontextmanager
    async def transaction():
        before = deepcopy(row.__dict__)
        try:
            yield
        except Exception:
            row.__dict__.clear();row.__dict__.update(before);rollbacks.append(True)
            raise
        else:commits.append(True)
    session = SimpleNamespace(begin=transaction, execute=AsyncMock(),
        scalar=AsyncMock(return_value='helpdesk_staging_db'), scalars=AsyncMock(return_value=events))
    @asynccontextmanager
    async def factory():yield session
    async def update(_id, **fields):row.__dict__.update(fields);return True
    repo = SimpleNamespace(get_ticket=AsyncMock(return_value=row), update_ticket=AsyncMock(side_effect=update),
        add_event=AsyncMock(return_value=(100, row.closed_at)))
    monkeypatch.setattr(ticket_events_repo, 'TicketEventsRepo', lambda _: repo)
    auth = SimpleNamespace(is_admin=lambda: True, actor_id='trusted-admin')
    plan = await repair(factory, auth)
    repo.update_ticket.assert_not_awaited();repo.add_event.assert_not_awaited()
    old_close, old_feedback, old_confirmation = row.closed_at, deepcopy(row.closure_feedback), deepcopy(row.custom_fields)
    if failure == 'database':session.scalar.return_value = 'production'
    if failure == 'audit':repo.add_event.return_value = None
    if failure:
        with pytest.raises(ValueError):
            await repair(factory, auth, apply=True, expected_fingerprint='stale' if failure == 'stale' else plan['fingerprint'])
        assert row.resolution_at == old_close and rollbacks
    else:
        applied = await repair(factory, auth, apply=True, expected_fingerprint=plan['fingerprint'])
        assert applied['changed'] and row.resolution_at == row.resolved_at
        repo.get_ticket.assert_awaited_with(row.ticket_id, for_update=True)
        repo.add_event.assert_awaited_once()
        again = await repair(factory, auth)
        assert not (await repair(factory, auth, apply=True, expected_fingerprint=again['fingerprint']))['changed']
        repo.add_event.assert_awaited_once()
    assert row.closed_at == old_close and row.closure_feedback == old_feedback and row.custom_fields == old_confirmation
