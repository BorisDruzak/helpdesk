"""Explicit, fingerprinted staging-only repair of the diagnosed T-000075 overwrite."""
from datetime import datetime, timedelta
import hashlib
import json
import uuid

TICKET_ID = 'ce1eeb5b-daed-41d5-bc31-1532749f5698'


def repair_plan(ticket, events):
    if not ticket or ticket.ticket_id != TICKET_ID or ticket.ticket_code != 'T-000075':
        raise ValueError('Only the diagnosed staging ticket is permitted')
    if (ticket.status != 'closed' or ticket.reopen_count or ticket.sla_paused_at
            or ticket.sla_paused_seconds or ticket.resolution_breached_at):
        raise ValueError('Lifecycle or SLA history no longer matches the diagnosed case')
    confirmation = (ticket.custom_fields or {}).get('resolution_confirmation') or {}
    if confirmation.get('pending') is not False or confirmation.get('responded_option_id') != 'confirm':
        raise ValueError('Requester confirmation must remain recorded')
    stops = [e for e in events if e.event_type == 'sla_resolution_stopped']
    starts = [e for e in events if e.event_type == 'sla_started']
    resolved = [e for e in events if e.event_type == 'status_changed' and e.payload.get('to_status') == 'resolved']
    closed = [e for e in events if e.event_type == 'status_changed' and e.payload.get('to_status') == 'closed']
    if any(len(rows) != 1 for rows in [stops, starts, resolved, closed]):
        raise ValueError('Expected one unambiguous resolution cycle')
    stop, start, resolution, closure = stops[0], starts[0], resolved[0], closed[0]
    stopped_at = datetime.fromisoformat(stop.payload['stopped_at'])
    original_due = datetime.fromisoformat(start.payload['resolution_due_at'])
    if (stop.payload.get('ticket_id') != TICKET_ID or stop.payload.get('status') != 'resolved'
            or stop.payload.get('trigger') != 'status_changed'
            or closure.payload.get('from_status') != 'resolved'
            or closure.payload.get('reason') != 'requester_confirmed_resolution'
            or not ticket.resolved_at or not ticket.closed_at or not ticket.resolution_due_at
            or original_due != ticket.resolution_due_at
            or not ticket.resolved_at <= stopped_at <= resolution.created_at <= ticket.closed_at <= closure.created_at
            or resolution.created_at-ticket.resolved_at > timedelta(seconds=1)
            or closure.created_at-ticket.closed_at > timedelta(seconds=1)
            or stopped_at > original_due
            or ticket.resolution_at not in {ticket.closed_at, stopped_at}):
        raise ValueError('Timestamp evidence does not prove the diagnosed overwrite')
    return {'ticket_id': TICKET_ID, 'ticket_code': ticket.ticket_code, 'source_event_id': stop.id,
            'previous_resolution_at': ticket.resolution_at.isoformat(), 'resolution_at': stopped_at.isoformat(),
            'changed': ticket.resolution_at != stopped_at}


async def repair(session_factory, auth, *, apply=False, expected_fingerprint=None):
    from sqlalchemy import select, text
    from app.db.models import TicketEvent
    from app.repos.ticket_events_repo import TicketEventsRepo

    if not auth.is_admin() or not auth.actor_id:
        raise ValueError('A trusted authenticated admin context is required')
    async with session_factory() as session:
        async with session.begin():
            if not apply:
                await session.execute(text('SET TRANSACTION READ ONLY'))
            if await session.scalar(text('SELECT current_database()')) != 'helpdesk_staging_db':
                raise ValueError('Only the isolated staging database is permitted')
            await session.execute(text("SET LOCAL lock_timeout='5s'"))
            repo = TicketEventsRepo(session)
            ticket = await repo.get_ticket(TICKET_ID, for_update=apply)
            events = list(await session.scalars(select(TicketEvent).where(TicketEvent.ticket_id == TICKET_ID).order_by(TicketEvent.id)))
            plan = repair_plan(ticket, events)
            def snapshot(row):
                return {column.name: getattr(row, column.name) for column in row.__table__.columns}
            fingerprint = hashlib.sha256(json.dumps([snapshot(ticket), *map(snapshot, events)],
                sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()
            if apply and fingerprint != expected_fingerprint:
                raise ValueError('Repair inputs changed; obtain a fresh plan')
            if apply and plan['changed']:
                await repo.update_ticket(TICKET_ID, resolution_at=datetime.fromisoformat(plan['resolution_at']))
                result = await repo.add_event(TICKET_ID, ticket.device_id, None, 'sla_resolution_timestamp_repaired',
                    {'visibility': 'internal', 'actor_id': auth.actor_id, 'actor_role': 'admin',
                     'reason': 'preserve_sla_stop_on_requester_confirmation', 'source_event_id': plan['source_event_id'],
                     'previous_resolution_at': plan['previous_resolution_at'], 'resolution_at': plan['resolution_at']},
                    event_id=str(uuid.uuid5(uuid.NAMESPACE_URL, 'helpdesk-staging:t75-resolution-sla-repair-20261106')))
                if result is None:
                    raise ValueError('Audit event was not inserted; repair rolled back')
            return {**plan, 'fingerprint': fingerprint, 'applied': apply}
