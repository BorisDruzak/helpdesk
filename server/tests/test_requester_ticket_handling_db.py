from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent, UiUser
from tests.test_requester_workspace_api import _person_for_login, _headers
from tests.conftest import TEST_UI_USER_PREFIX
from tickets.statuses import requester_status_for_internal

pytestmark=[pytest.mark.asyncio,pytest.mark.db_cleanup('web_support')]


async def test_owner_gets_current_specialist_sla_and_public_progress_but_stranger_gets_404(test_client_light,test_engine):
    maker=async_sessionmaker(test_engine,expire_on_commit=False)
    marker=uuid4().hex[:8];owner='chat-owner-'+marker;foreign='chat-other-'+marker
    specialist='specialist-'+marker;now=datetime.now(timezone.utc);tid=str(uuid4())
    async with maker() as session:
        person=await _person_for_login(session,login=owner)
        await _person_for_login(session,login=foreign)
        staff=await _person_for_login(session,login=specialist);staff.full_name='Иван Специалист'
        session.add(UiUser(user_login=specialist,password_hash='unused-test-fixture',actor_role='support',is_active=True))
        row=Ticket(ticket_id=tid,title='Owner-safe handling fixture',description='Synthetic problem',requester_id=owner,
            requester_external_ref=person.person_id,requester_person_id=person.person_id,status='in_progress',
            requester_snapshot_json={'person':{'external_id':person.person_id},'display_name':'Synthetic owner'},
            requester_status=requester_status_for_internal('in_progress'),assignee_id=specialist,
            created_at=now-timedelta(minutes=10),first_response_due_at=now+timedelta(minutes=10),
            first_response_at=now-timedelta(minutes=5),resolution_due_at=now+timedelta(hours=2),
            sla_paused_at=now-timedelta(minutes=1),sla_paused_seconds=600,custom_fields={})
        session.add(row);await session.flush();code=row.ticket_code
        session.add_all([
            TicketEvent(ticket_id=tid,event_type='status_changed',payload={'new_status':'in_progress'}),
            TicketEvent(ticket_id=tid,event_type='chat_message',payload={'sender_role':'admin','visibility':'public','text':'Public reply fixture'}),
            TicketEvent(ticket_id=tid,event_type='chat_message',payload={'sender_role':'support','visibility':'internal','text':'PRIVATE INTERNAL FIXTURE'}),
        ]);await session.commit()
    headers=_headers(TEST_UI_USER_PREFIX+owner)
    response=await test_client_light.get('/api/web/requester/tickets/'+code,headers=headers)
    value=await response.json();assert response.status==200,value
    handling=value['data']['handling']
    assert handling['assignee']=={'assigned':True,'display_name':'Иван Специалист'}
    assert handling['sla']['first_response']['status']=='completed'
    assert handling['sla']['resolution']['status']=='paused'
    assert handling['device']=={'state':'none'}
    assert 'PRIVATE INTERNAL FIXTURE' not in str(value)
    assert 'password_hash' not in str(value) and 'unused-test-fixture' not in str(value)
    assert any(event.get('requester_timeline_text')=='Специалист взял обращение в работу.' for event in value['data']['events'])
    for ref in (tid,code):
        denied=await test_client_light.get('/api/web/requester/tickets/'+ref,headers=_headers(TEST_UI_USER_PREFIX+foreign))
        assert denied.status==404
    async with maker() as session:
        row=await session.get(Ticket,tid);row.status='waiting_on_user';row.requester_status=requester_status_for_internal(row.status);row.next_action_owner='requester';row.assignee_id=None
        await session.commit()
    again=await test_client_light.get('/api/web/requester/tickets/'+tid,headers=headers)
    data=(await again.json())['data']['handling']
    assert data['assignee']['assigned'] is False and data['next_action_owner']=='requester'
    async with maker() as session:
        session.add_all([TicketEvent(ticket_id=tid,event_type='internal_note',created_at=now+timedelta(seconds=index),payload={'text':'PRIVATE WINDOW FIXTURE'}) for index in range(205)])
        session.add(TicketEvent(ticket_id=tid,event_type='chat_message',created_at=now+timedelta(seconds=210),payload={'sender_role':'support','visibility':'public','text':'Latest visible reply after200 events'}))
        await session.commit()
    recent=await test_client_light.get('/api/web/requester/tickets/'+tid,headers=headers)
    payload=await recent.json()
    assert any(message['text']=='Latest visible reply after200 events' for message in payload['data']['messages'])
    assert 'PRIVATE WINDOW FIXTURE' not in str(payload)
    async with maker() as session:
        session.add_all([TicketEvent(ticket_id=tid,event_type='chat_message',created_at=now+timedelta(seconds=300+index),payload={'visibility':'internal','text':'PRIVATE AFTER PUBLIC'}) for index in range(205)])
        await session.commit()
    after_noise=await test_client_light.get('/api/web/requester/tickets/'+tid,headers=headers)
    payload=await after_noise.json()
    assert any(message['text']=='Latest visible reply after200 events' for message in payload['data']['messages'])
    assert 'PRIVATE AFTER PUBLIC' not in str(payload)
