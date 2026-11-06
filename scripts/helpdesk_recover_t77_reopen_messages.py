"""Explicit staging-only recovery of the two diagnosed requester reopen comments."""
import hashlib
import json
import uuid

TICKET_ID = '6258c8b7-6aa7-41fc-811e-a9708dabddbb'
REOPEN_IDS = {'d6e29ce1-b17c-44b5-9889-588c34356bca', 'ef384fdb-ea83-4309-94cc-81ad8afe598a'}


def recovery_plan(ticket, rows, events):
    from quality.reopen_message import reopen_message_payload
    if not ticket or ticket.ticket_id != TICKET_ID or ticket.ticket_code != 'T-000077':
        raise ValueError('Only the diagnosed staging ticket is permitted')
    if not ticket.observer_root_trace_id:
        raise ValueError('An existing audit trace is required')
    selected = [row for row in rows if row.reopen_id in REOPEN_IDS]
    if {row.reopen_id for row in selected} != REOPEN_IDS or len(selected) != 2:
        raise ValueError('The two original reopen records are required')
    plans = []
    for row in selected:
        facts = [e for e in events if e.event_type == 'ticket_reopened' and e.payload.get('reopen_id') == row.reopen_id]
        if (row.reopened_by_role not in {'requester','user'} or row.reopened_by_actor_id != ticket.requester_id
                or len(facts) != 1 or facts[0].payload.get('actor_role') not in {'requester','user'}
                or facts[0].payload.get('actor_role') != row.reopened_by_role
                or facts[0].payload.get('actor_id') != row.reopened_by_actor_id
                or facts[0].payload.get('reason_code') != row.reason_code
                or facts[0].payload.get('reason_comment') != row.reason_comment):
            raise ValueError('Requester-authored source evidence must match exactly')
        payload = reopen_message_payload(ticket,reopen_id=row.reopen_id,reason_code=row.reason_code,reason_comment=row.reason_comment)
        matches = [e for e in events if e.event_type == 'chat_message' and e.payload.get('message_id') == payload['message_id']]
        if len(matches)>1 or (matches and matches[0].payload != payload):
            raise ValueError('An existing message differs; do not overwrite it')
        plans.append({'reopen_id':row.reopen_id,'source_event_id':facts[0].id,'created_at':facts[0].created_at,
                      'payload':payload,'changed':not matches})
    return plans


async def recover(session_factory, auth, *, apply=False, expected_fingerprint=None):
    from sqlalchemy import select,text
    from app.db.models import TicketEvent,TicketReopenEvent
    from app.repos.ticket_events_repo import TicketEventsRepo
    if not auth.is_admin() or not auth.actor_id:
        raise ValueError('A trusted authenticated admin context is required')
    async with session_factory() as session:
        async with session.begin():
            if not apply:await session.execute(text('SET TRANSACTION READ ONLY'))
            if await session.scalar(text('SELECT current_database()')) != 'helpdesk_staging_db':
                raise ValueError('Only the isolated staging database is permitted')
            await session.execute(text("SET LOCAL lock_timeout='5s'"))
            repo=TicketEventsRepo(session);ticket=await repo.get_ticket(TICKET_ID,for_update=apply)
            rows=list(await session.scalars(select(TicketReopenEvent).where(TicketReopenEvent.ticket_id==TICKET_ID).order_by(TicketReopenEvent.reopen_id)))
            events=list(await session.scalars(select(TicketEvent).where(TicketEvent.ticket_id==TICKET_ID).order_by(TicketEvent.id)))
            plans=recovery_plan(ticket,rows,events)
            def snapshot(row):return {c.name:getattr(row,c.name) for c in row.__table__.columns}
            fingerprint=hashlib.sha256(json.dumps([snapshot(ticket),*map(snapshot,rows),*map(snapshot,events)],sort_keys=True,default=str).encode()).hexdigest()
            if apply and fingerprint != expected_fingerprint:raise ValueError('Inputs changed; obtain a fresh plan')
            changed=[plan for plan in plans if plan['changed']]
            if apply and changed:
                for plan in changed:
                    payload=plan['payload']
                    result=await repo.add_event(ticket_id=TICKET_ID,device_id=ticket.device_id,agent_seq=None,
                        event_type='chat_message',payload=payload,event_id=payload['message_id'])
                    if result is None:raise ValueError('Recovered message was not inserted')
                    # Only the new, uncommitted derived row receives the original fact time.
                    message=await session.get(TicketEvent,result[0]);message.created_at=plan['created_at']
                audit=await repo.add_event(ticket_id=TICKET_ID,device_id=ticket.device_id,agent_seq=None,
                    event_type='requester_reopen_messages_recovered',
                    payload={'visibility':'internal','actor_id':auth.actor_id,'actor_role':'admin',
                        'reopen_ids':[p['reopen_id'] for p in changed],'source_event_ids':[p['source_event_id'] for p in changed]},
                    event_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'helpdesk-staging:t77-reopen-message-recovery-20261106')))
                if audit is None:raise ValueError('Recovery audit missing; rollback required')
            return {'fingerprint':fingerprint,'applied':apply,'changed':len(changed),
                'messages':[{'reopen_id':p['reopen_id'],'message_id':p['payload']['message_id'],
                             'source_event_id':p['source_event_id'],'created_at':p['created_at'].isoformat()} for p in plans]}
