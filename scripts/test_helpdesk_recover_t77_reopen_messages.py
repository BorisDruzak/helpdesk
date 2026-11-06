from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
import sys
import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/'server'))


def fixture():
    from scripts.helpdesk_recover_t77_reopen_messages import TICKET_ID,REOPEN_IDS
    ticket=SimpleNamespace(ticket_id=TICKET_ID,ticket_code='T-000077',observer_root_trace_id='trace',requester_id='owner',custom_fields={})
    rows=[SimpleNamespace(reopen_id=rid,reopened_by_role='requester',reopened_by_actor_id='owner',reason_code='unclear_instruction',reason_comment='Поясните шаг') for rid in sorted(REOPEN_IDS)]
    events=[SimpleNamespace(id=i,event_type='ticket_reopened',created_at=datetime(2026,11,6,7,9,i,tzinfo=timezone.utc),payload={'reopen_id':r.reopen_id,'actor_id':'owner','actor_role':'requester','reason_code':r.reason_code,'reason_comment':r.reason_comment}) for i,r in enumerate(rows)]
    return ticket,rows,events


def test_recovery_preserves_original_time_and_is_idempotent():
    from scripts.helpdesk_recover_t77_reopen_messages import recovery_plan
    ticket,rows,events=fixture();plans=recovery_plan(ticket,rows,events)
    assert len(plans)==2 and all(p['changed'] for p in plans)
    assert {p['created_at'] for p in plans}=={e.created_at for e in events}
    events += [SimpleNamespace(event_type='chat_message',payload=p['payload']) for p in plans]
    assert not any(p['changed'] for p in recovery_plan(ticket,rows,events))


@pytest.mark.parametrize('change',['ticket','owner','role','source_role','source_owner','missing_owner','comment','missing','conflicting_message'])
def test_recovery_rejects_unproven_or_changed_source(change):
    from scripts.helpdesk_recover_t77_reopen_messages import recovery_plan
    ticket,rows,events=fixture()
    if change=='ticket':ticket.ticket_id='other'
    if change=='owner':rows[0].reopened_by_actor_id='other'
    if change=='role':rows[0].reopened_by_role='support'
    if change=='source_role':events[0].payload['actor_role']='user'
    if change=='source_owner':events[0].payload['actor_id']='other'
    if change=='missing_owner':events[0].payload.pop('actor_id')
    if change=='comment':events[0].payload['reason_comment']='changed'
    if change=='missing':events.pop()
    if change=='conflicting_message':
        plan=recovery_plan(ticket,rows,events)[0]
        events.append(SimpleNamespace(event_type='chat_message',payload={**plan['payload'],'text':'Different'}))
    with pytest.raises(ValueError):recovery_plan(ticket,rows,events)


@pytest.mark.asyncio
async def test_recovery_rejects_untrusted_actor_before_database():
    from scripts.helpdesk_recover_t77_reopen_messages import recover
    def forbidden():raise AssertionError('Do not open database')
    with pytest.raises(ValueError,match='admin'):
        await recover(forbidden,SimpleNamespace(is_admin=lambda:False,actor_id='x'),apply=True)
