"""Owner-only handling summary; no internal notes, diagnostics or foreign presence."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import quote
from uuid import UUID

from app.db.models import TicketQueue, UiUser
from app.services.endpoint_device_reference_service import EndpointDeviceSnapshotV1
from app.services.user_display_names import ui_user_display_names
from domain_ports.endpoint import EndpointDevicePresenceProjection, EndpointDeviceRef
from domain_ports.registry_contracts import DeviceContextProjection, DeviceRef
from tickets.timer_projection import project_ticket_timer
from tickets.visibility_policy import get_template_visibility_policy


def display(value):
    text=str(value or '').strip()[:160]
    if not text:return None
    try:UUID(text)
    except ValueError:return text
    return None


async def assignee_name(session,login):
    if not login:return None
    user=await session.get(UiUser,login)
    if user is None or user.actor_role not in {'support','admin'}:return 'Специалист поддержки'
    names=await ui_user_display_names(session,[user.user_login])
    return display(names[user.user_login]) or 'Специалист поддержки'


async def requester_device(ticket,*,resolver,ports,actor_id):
    local_id=getattr(ticket,'device_id',None);external_id=getattr(ticket,'endpoint_device_ref',None)
    if not local_id and not external_id:return {'state':'none'}
    result={'state':'linked','display_name':None,'presence':'unavailable','last_seen_at':None,'details_path':None}
    try:
        snapshot=EndpointDeviceSnapshotV1.model_validate(getattr(ticket,'endpoint_device_snapshot_json',None))
        if snapshot.device_ref==external_id:result['display_name']=display(snapshot.display_name)
    except (ValueError,TypeError):pass
    # Historical ticket access alone does not authorize current foreign-device reads.
    if not local_id:return result
    try:await resolver.require_owned_device(actor_id=actor_id,device_id=local_id)
    except PermissionError:return result
    try:context=await ports.registry.device_context(DeviceRef(external_id=local_id))
    except Exception:return result
    if not isinstance(context,DeviceContextProjection) or context.device.external_id!=local_id:return result
    result['display_name']=display(context.display_name) or result['display_name']
    result['details_path']='/app/requester/devices/'+quote(str(local_id),safe='')
    if not external_id or context.endpoint_device_ref!=external_id:return result
    try:
        ref=EndpointDeviceRef(external_id=external_id)
        presence=await ports.endpoint.read_device_presence(ref)
        if not isinstance(presence,EndpointDevicePresenceProjection) or presence.device!=ref:return result
        result.update(display_name=display(presence.display_name) or result['display_name'],
            presence='retired' if presence.retired else 'online' if presence.online else 'offline',
            last_seen_at=presence.last_seen_at.isoformat() if presence.last_seen_at else None)
    except Exception:pass  # A provider outage must not remove the conversation.
    return result


def sla_timer(ticket,payload,*,resolution=False,now=None,hidden=()):
    prefix='resolution' if resolution else 'first_response'
    names=['created_at',prefix+'_due_at',prefix+'_at','resolved_at','closed_at','canceled_at']
    values={name:getattr(ticket,name,None) if name in payload and name not in hidden else None for name in names}
    values.update(sla_paused_at=getattr(ticket,'sla_paused_at',None) if 'sla_paused_at' not in hidden else None,
        sla_paused_seconds=getattr(ticket,'sla_paused_seconds',None) if 'sla_paused_seconds' not in hidden else 0,
        breached_at=getattr(ticket,prefix+'_breached_at',None))
    completed='first_response_at'
    if resolution:
        completed=('resolution_at' if values['resolution_at'] is not None else 'resolved_at' if values['resolved_at'] is not None else 'closed_at') if getattr(ticket,'status',None) in {'resolved','closed'} else None
    view=SimpleNamespace(**values)
    result=project_ticket_timer(view,due_attr=prefix+'_due_at',breached_attr='breached_at',
        completed_attr=completed,paused_attr='sla_paused_at',paused_seconds_attr='sla_paused_seconds',now=now)
    if getattr(ticket,'status',None) in {'canceled','archived'}:
        result.update(status='canceled' if ticket.status=='canceled' else 'stopped',remaining_seconds=None)
    elif getattr(ticket,'status',None) in {'resolved','closed'} and not resolution and values['first_response_at'] is None:
        result.update(status='stopped',remaining_seconds=None)
    due=values[prefix+'_due_at']
    result['effective_due_at']=(due+timedelta(seconds=max(0,int(values['sla_paused_seconds'] or 0)))).isoformat() if due else None
    return result


async def build_ticket_handling(session,ticket,payload,*,resolver,ports,actor_id,now=None):
    now=now or datetime.now(timezone.utc)
    policy=get_template_visibility_policy(ticket)
    hidden=set(policy.get('hide_from_requester') or [])
    if 'handling' in hidden:return None
    result={'status':payload.get('public_status') or payload.get('requester_status'),
        'status_label':payload.get('public_status_label') or payload.get('requester_status_label') or payload.get('status_label'),
        'next_action_owner':payload.get('next_action_owner'),'updated_at':payload.get('updated_at'),
        'created_at':payload.get('created_at'),'as_of':now.isoformat()}
    if getattr(ticket,'status',None) in {'resolved','closed','canceled','archived'}:result['next_action_owner']=None
    if not hidden.intersection({'handling.assignee','assignee','assignee_id'}):
        result['assignee']={'assigned':bool(getattr(ticket,'assignee_id',None)),
            'display_name':await assignee_name(session,getattr(ticket,'assignee_id',None))}
    if getattr(ticket,'queue_id',None) and not hidden.intersection({'handling.team','queue_code','queue_id'}):
        queue=await session.get(TicketQueue,ticket.queue_id)
        result['team']=display(getattr(queue,'name',None))
    if not hidden.intersection({'handling.sla','sla'}):
        result['sla']={'first_response':sla_timer(ticket,payload,now=now,hidden=hidden),
            'resolution':sla_timer(ticket,payload,resolution=True,now=now,hidden=hidden)}
    if not hidden.intersection({'handling.device','device','device_id'}):
        result['device']=await requester_device(ticket,resolver=resolver,ports=ports,actor_id=actor_id)
    for path in hidden:
        if not isinstance(path,str) or not path.startswith('handling.'):continue
        parts=path.split('.')[1:];target=result
        for part in parts[:-1]:
            target=target.get(part) if isinstance(target,dict) else None
        if isinstance(target,dict):target.pop(parts[-1],None)
    return result
