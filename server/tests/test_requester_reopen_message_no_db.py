from types import SimpleNamespace
from unittest.mock import AsyncMock
from datetime import datetime, timezone
import pytest

from quality import reopen_service

pytestmark = pytest.mark.no_db


@pytest.fixture
def reopen_case(monkeypatch):
    ticket = SimpleNamespace(ticket_id='test-reopen', device_id=None, status='resolved', requester_id='owner',
        reopen_count=0, service_code='it', offering_code='help', custom_fields={})
    rows = []
    session = SimpleNamespace(add=rows.append, flush=AsyncMock())
    repo = SimpleNamespace(get_ticket=AsyncMock(return_value=ticket), add_event=AsyncMock(return_value=(99, datetime.now(timezone.utc))))
    async def transition(**kwargs):
        ticket.status = kwargs['to_status']
        return {'event_payload': {}}
    monkeypatch.setattr(reopen_service, 'TicketEventsRepo', lambda _: repo)
    monkeypatch.setattr(reopen_service, 'TicketWorkflowService', lambda *_: SimpleNamespace(apply_status_transition=transition))
    monkeypatch.setattr(reopen_service, 'QualityReviewService', lambda *_: SimpleNamespace(ensure_review_for_signal=AsyncMock(return_value={'review_id':'review'})))
    return session, repo, rows, ticket


@pytest.mark.asyncio
async def test_requester_reopen_persists_public_reason_and_comment_with_the_same_transaction(reopen_case):
    session, repo, rows, ticket = reopen_case
    service = reopen_service.TicketReopenService(session)
    result = await service.reopen_ticket(ticket.ticket_id, reason_code='unclear_instruction',
        reason_comment='Первый шаг непонятен\nНужен пример', actor_id='owner', actor_role='requester')
    repo.add_event.assert_awaited_once()
    payload = repo.add_event.call_args.kwargs['payload']
    assert payload['visibility']=='public' and payload['sender_role']=='user' and payload['from']=='user'
    assert 'Непонятная инструкция' in payload['text'] and 'Первый шаг непонятен\nНужен пример' in payload['text']
    assert payload['metadata']['reopen_id']==result['reopen_id']
    assert service.public_message_event == ((99, repo.add_event.return_value[1]), payload)
    assert ticket.status=='in_progress' and any(getattr(row,'event_type',None)=='ticket_reopened' for row in rows)


@pytest.mark.asyncio
async def test_missing_message_aborts_reopen_instead_of_silently_succeeding(reopen_case):
    session, repo, _, ticket = reopen_case;repo.add_event.return_value=None
    service = reopen_service.TicketReopenService(session)
    with pytest.raises(ValueError,match='message'):
        await service.reopen_ticket(ticket.ticket_id, reason_code='not_resolved', reason_comment=None,
            actor_id='owner', actor_role='requester')
    assert service.public_message_event is None


@pytest.mark.asyncio
async def test_operator_quality_notes_do_not_automatically_become_public_chat(reopen_case):
    session, repo, _, ticket = reopen_case
    await reopen_service.TicketReopenService(session).reopen_ticket(ticket.ticket_id,
        reason_code='other',reason_comment='Internal operator analysis',actor_id='operator',actor_role='support')
    repo.add_event.assert_not_awaited()


def test_reopen_message_identity_is_stable_and_all_reason_codes_have_labels():
    from quality.reopen_message import reopen_message_payload, REOPEN_REASON_LABELS
    from quality.contracts import REOPEN_REASON_CODES
    assert set(REOPEN_REASON_LABELS)==REOPEN_REASON_CODES
    ticket=SimpleNamespace(ticket_id='ticket',requester_id='owner',custom_fields={})
    first=reopen_message_payload(ticket,reopen_id='reopen',reason_code='not_resolved',reason_comment='  ещё не работает  ')
    assert first==reopen_message_payload(ticket,reopen_id='reopen',reason_code='not_resolved',reason_comment='ещё не работает')
    assert first['message_id']!=reopen_message_payload(ticket,reopen_id='another',reason_code='not_resolved',reason_comment=None)['message_id']


def test_same_reopen_chat_is_readable_by_requester_and_support_message_serializers():
    from quality.reopen_message import reopen_message_payload
    from app.db.models import TicketEvent
    from web_api.support_handlers import _build_timeline_message
    from web_api.requester_handlers import _serialize_message_for_requester
    ticket=SimpleNamespace(ticket_id='ticket',requester_id='owner',custom_fields={})
    payload=reopen_message_payload(ticket,reopen_id='reopen',reason_code='unclear_instruction',reason_comment='Поясните первый шаг')
    event=TicketEvent(id=10,ticket_id='ticket',event_type='chat_message',payload=payload,created_at=datetime.now(timezone.utc))
    staff=_build_timeline_message(event,ticket=ticket)
    requester=_serialize_message_for_requester(event,ticket=ticket)
    assert staff.text==payload['text']
    # The existing requester-safe serializer collapses display whitespace.
    assert requester['text']==' '.join(payload['text'].split())
    assert staff.visibility=='public' and staff.event_category=='message'


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [None, 'business', 'conflict', 'denied'])
async def test_web_reopen_broadcasts_only_after_commit_and_rolls_back_failures(monkeypatch, failure):
    from contextlib import asynccontextmanager
    from auth.context import AuthContext, AuthType
    from web_api import requester_handlers as handlers
    from tickets.workflow_service import WorkflowTransitionConflict
    order=[]
    session=SimpleNamespace(commit=AsyncMock(side_effect=lambda:order.append('commit')),rollback=AsyncMock())
    @asynccontextmanager
    async def transaction():yield session
    monkeypatch.setattr(handlers,'get_session',transaction)
    ticket=SimpleNamespace(ticket_id='ticket',requester_id='owner',status='resolved')
    monkeypatch.setattr(handlers,'RequesterIdentityResolver',lambda *args,**kwargs:object())
    monkeypatch.setattr(handlers,'_get_locked_requester_ticket',AsyncMock(return_value=None if failure=='denied' else ticket))
    monkeypatch.setattr(handlers,'requester_ticket_actions',lambda _: {'can_reopen':True})
    event=((5,datetime.now(timezone.utc)),{'text':'Public reason','visibility':'public'})
    service=SimpleNamespace(public_message_event=event,reopen_ticket=AsyncMock(return_value={'ticket_id':'ticket','status':'in_progress','reopen_id':'reopen'}))
    if failure in {'business','conflict'}:service.reopen_ticket.side_effect=ValueError('failed') if failure=='business' else WorkflowTransitionConflict()
    from unittest.mock import Mock
    constructor=Mock(side_effect=lambda _:service)
    monkeypatch.setattr(handlers,'TicketReopenService',constructor)
    monkeypatch.setattr(handlers,'_write_requester_web_observer_event',AsyncMock())
    pushed=AsyncMock(side_effect=lambda *args,**kwargs:order.append('push'))
    monkeypatch.setattr(handlers,'_push_ticket_event',pushed)
    class Request(dict):pass
    request=Request(auth_context=AuthContext(actor_id='owner',actor_role='user',auth_type=AuthType.SYSTEM))
    request.match_info={'ticket_id':'ticket'};request.app={};request.json=AsyncMock(return_value={'reason_code':'unclear_instruction','reason_comment':'Please explain'})
    response=await handlers.handle_web_requester_ticket_reopen(request)
    assert response.status == (200 if failure is None else 400 if failure=='business' else 409 if failure=='conflict' else 404)
    if failure is None:
        assert order==['commit','push']
        session.rollback.assert_not_awaited()
        pushed.assert_awaited_once_with(request,'ticket',event[0],'chat_message',event[1])
    else:
        pushed.assert_not_awaited();session.commit.assert_not_awaited()
        if failure=='denied':constructor.assert_not_called()
        else:session.rollback.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('public',[False,True])
@pytest.mark.parametrize('failure',[None,'commit'])
async def test_legacy_reopen_delivers_only_durable_messages(monkeypatch,public,failure):
    from contextlib import asynccontextmanager
    from auth.context import AuthContext,AuthType
    from web_api import quality_handlers as handlers
    from tickets import handlers as tickets
    order=[]
    async def commit():
        if failure:raise RuntimeError('commit failed')
        order.append('commit')
    session=SimpleNamespace(commit=commit,rollback=AsyncMock())
    @asynccontextmanager
    async def transaction():
        try:yield session
        except Exception:await session.rollback();raise
    monkeypatch.setattr(handlers,'get_session',transaction)
    monkeypatch.setattr(handlers,'_quality_actor_for_ticket',AsyncMock(return_value=('owner','user',None)))
    monkeypatch.setattr(handlers,'_public_auth_context',AsyncMock(return_value=AuthContext(actor_id='owner',actor_role='user',auth_type=AuthType.SYSTEM)))
    service=SimpleNamespace(public_message_event=((1,datetime.now(timezone.utc)),{'text':'Reason'}),
        reopen_ticket=AsyncMock(return_value={'ticket_id':'ticket','status':'in_progress','reopen_id':'reopen'}))
    monkeypatch.setattr(handlers,'TicketReopenService',lambda _:service)
    pushed=AsyncMock(side_effect=lambda *args,**kwargs:order.append('push'))
    monkeypatch.setattr(tickets,'_push_ticket_event',pushed)
    class Request(dict):pass
    request=Request();request.match_info={'ticket_id':'ticket'};request.json=AsyncMock(return_value={'reason_code':'not_resolved'})
    handler=handlers.handle_public_ticket_reopen if public else handlers.handle_ticket_reopen
    if failure:
        with pytest.raises(RuntimeError,match='commit failed'):await handler(request)
        session.rollback.assert_awaited_once();pushed.assert_not_awaited()
    else:
        assert (await handler(request)).status==200 and order==['commit','push']
