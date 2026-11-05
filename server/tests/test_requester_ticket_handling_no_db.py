from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from domain_ports.endpoint import EndpointDevicePresenceProjection, EndpointDeviceRef
from domain_ports.registry_contracts import DeviceContextProjection, DeviceRef

import pytest

from requester.ticket_handling import build_ticket_handling, requester_device, sla_timer
from tickets.timer_projection import project_ticket_timer

pytestmark=pytest.mark.no_db
NOW=datetime(2026,11,5,8,tzinfo=timezone.utc)


def ticket(**changes):
    return SimpleNamespace(**(dict(status='in_progress',assignee_id=None,queue_id=None,device_id=None,
        endpoint_device_ref=None,endpoint_device_snapshot_json=None,custom_fields={},
        created_at=NOW-timedelta(minutes=10),first_response_due_at=NOW+timedelta(minutes=20),
        resolution_due_at=NOW+timedelta(hours=3),sla_paused_at=None,sla_paused_seconds=0)|changes))


def timer(row,now=NOW):
    return project_ticket_timer(row,due_attr='first_response_due_at',completed_attr='first_response_at',
        paused_attr='sla_paused_at',paused_seconds_attr='sla_paused_seconds',now=now)


def test_paused_and_completed_sla_are_not_live_overdue_countdowns():
    row=ticket(sla_paused_at=NOW-timedelta(minutes=2),sla_paused_seconds=600)
    assert timer(row)['status']=='paused'
    assert timer(row)['remaining_seconds']==timer(row,NOW+timedelta(days=1))['remaining_seconds']
    row.first_response_at=NOW-timedelta(minutes=1)
    assert timer(row)['status']=='completed' and timer(row)['remaining_seconds'] is None


def test_terminal_ticket_has_no_live_first_response_countdown_or_canceled_sla():
    row=ticket(status='closed');payload={'first_response_due_at':row.first_response_due_at}
    assert sla_timer(row,payload,now=NOW)['status']=='stopped'
    row.status='canceled'
    assert sla_timer(row,payload,resolution=True,now=NOW)['status']=='canceled'


@pytest.mark.asyncio
async def test_owner_handling_uses_safe_payload_and_respects_hidden_sections():
    row=ticket(custom_fields={'request_template':{'visibility_policy':{'hide_from_requester':['handling.assignee','handling.device']}}},assignee_id='do-not-expose-login')
    session=SimpleNamespace(get=AsyncMock(),scalar=AsyncMock())
    result=await build_ticket_handling(session,row,{'public_status':'in_work','public_status_label':'В работе'},
        resolver=SimpleNamespace(),ports=SimpleNamespace(),actor_id='owner',now=NOW)
    assert result['status_label']=='В работе'
    assert result.get('assignee') is None and result.get('device') is None
    assert result['sla']['first_response']['status']=='unknown'
    assert 'do-not-expose-login' not in str(result)
    session.get.assert_not_called();session.scalar.assert_not_called()


@pytest.mark.asyncio
async def test_no_device_and_lost_ownership_never_call_endpoint():
    endpoint=SimpleNamespace(read_device_presence=AsyncMock())
    registry=SimpleNamespace(device_context=AsyncMock())
    ports=SimpleNamespace(endpoint=endpoint,registry=registry)
    resolver=SimpleNamespace(require_owned_device=AsyncMock(side_effect=PermissionError()))
    assert (await requester_device(ticket(),resolver=resolver,ports=ports,actor_id='owner'))['state']=='none'
    result=await requester_device(ticket(device_id='foreign',endpoint_device_ref=str(uuid4())),resolver=resolver,ports=ports,actor_id='owner')
    assert result['presence']=='unavailable' and not result.get('details_path')
    endpoint.read_device_presence.assert_not_called();registry.device_context.assert_not_called()


@pytest.mark.asyncio
async def test_current_presence_requires_exact_owned_registry_and_provider_references():
    ref=str(uuid4());wrong=str(uuid4())
    registry=SimpleNamespace(device_context=AsyncMock(return_value=DeviceContextProjection(device=DeviceRef(external_id='owned'),
        endpoint_device_ref=ref,display_name='Owned PC',asset_type='computer',asset_status='active',source='local_authoritative')))
    endpoint=SimpleNamespace(read_device_presence=AsyncMock(return_value=EndpointDevicePresenceProjection(device=EndpointDeviceRef(external_id=wrong),display_name='FOREIGN PRIVATE NAME',retired=False,online=True,last_seen_at=NOW)))
    resolver=SimpleNamespace(require_owned_device=AsyncMock(return_value=(None,None)))
    row=ticket(device_id='owned',endpoint_device_ref=ref)
    ports=SimpleNamespace(registry=registry,endpoint=endpoint)
    result=await requester_device(row,resolver=resolver,ports=ports,actor_id='owner')
    assert result['presence']=='unavailable' and 'FOREIGN PRIVATE NAME' not in str(result)
    endpoint.read_device_presence.return_value=EndpointDevicePresenceProjection(device=EndpointDeviceRef(external_id=ref),display_name='Owned PC',retired=False,online=True,last_seen_at=NOW)
    result=await requester_device(row,resolver=resolver,ports=ports,actor_id='owner')
    assert result['presence']=='online' and result['last_seen_at']==NOW.isoformat()
    endpoint.read_device_presence.side_effect=RuntimeError('DO NOT ECHO PROVIDER DETAILS')
    result=await requester_device(row,resolver=resolver,ports=ports,actor_id='owner')
    assert result['presence']=='unavailable' and 'DO NOT ECHO' not in str(result)


@pytest.mark.parametrize('positive_feedback',[False,True])
def test_pending_acceptance_can_be_rejected_after_optional_feedback_window_expires(positive_feedback):
    from tickets.requester_policy import requester_ticket_actions
    row=ticket(status='resolved',resolved_at=NOW-timedelta(days=30),
        custom_fields={'resolution_confirmation':{'pending':True}},
        _requester_latest_feedback_reopen_available=not positive_feedback)
    actions=requester_ticket_actions(row,now=NOW)
    assert actions['can_confirm_solution'] and actions['can_reopen']
    assert actions['can_rate_solution'] is False
    row.custom_fields={'resolution_confirmation':{'pending':False}}
    assert requester_ticket_actions(row,now=NOW)['can_reopen'] is False
