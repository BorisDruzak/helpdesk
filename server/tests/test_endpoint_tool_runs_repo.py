from datetime import datetime, timedelta, timezone
from uuid import uuid4
import importlib
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Ticket, Operation, EndpointOperationLink, DiagnosticStep

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.no_db
def test_immutable_run_identity_is_ticket_and_actor_scoped():
    assert importlib.util.find_spec("app.repos.endpoint_tool_runs_repo") is not None
    from app.repos.endpoint_tool_runs_repo import tool_run_id, remote_tool_key
    assert tool_run_id("a", "t", "k") == tool_run_id("a", "t", "k")
    assert tool_run_id("a", "t", "k") != tool_run_id("b", "t", "k")
    assert tool_run_id("a", "t", "k") != tool_run_id("a", "t2", "k")
    run = str(uuid4())
    assert remote_tool_key("diagnostic", run) == f"helpdesk-endpoint-operation:{run}"
    assert remote_tool_key("module", run) != remote_tool_key("context_collection", run)


async def seed(session, device):
    now = datetime.now(timezone.utc)
    ticket = Ticket(ticket_id=str(uuid4()), title="Endpoint tools", description="Persistence",
                    endpoint_device_ref=device, status="in_progress", created_at=now, updated_at=now)
    session.add(ticket)
    await session.flush()
    return ticket.ticket_id


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_changed_device_is_rejected_inside_intent_transaction():
    from app.repos.endpoint_tool_runs_repo import EndpointToolRunsRepo, ToolRunConflict
    from domain_ports.endpoint_tools import ToolRunRequestV1
    session=SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(endpoint_device_ref="changed")))
    with pytest.raises(ToolRunConflict):
        await EndpointToolRunsRepo(session).create_pending(ToolRunRequestV1(kind="diagnostic"),actor_id="actor",
            ticket_id="ticket",device_ref="original",caller_key="key")
    assert session.get.await_count==1


@pytest.mark.asyncio
async def test_same_actor_key_replays_same_request_and_changed_inputs_conflict(test_engine):
    from app.repos.endpoint_tool_runs_repo import EndpointToolRunsRepo, ToolRunConflict
    from domain_ports.endpoint_tools import ToolRunRequestV1
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    request = ToolRunRequestV1(kind="context_collection", profile="inventory_v1")
    async with maker() as session:
        async with session.begin():
            device = str(uuid4())
            ticket = await seed(session, device)
            repo = EndpointToolRunsRepo(session)
            args = dict(actor_id="actor", ticket_id=ticket, device_ref=device, caller_key="key")
            first = await repo.create_pending(request, **args)
            replay = await repo.create_pending(request, **args)
            assert first.run_id == replay.run_id
            assert first.request == replay.request
            assert await session.get(DiagnosticStep, first.run_id) is not None
            with pytest.raises(ToolRunConflict):
                await repo.create_pending(request.model_copy(update={"profile": "network_v1"}), **args)
            assert await repo.get_authorized_run(first.run_id, str(uuid4())) is None


@pytest.mark.asyncio
async def test_only_owned_runs_are_claimed_and_lease_tokens_are_exclusive(test_engine):
    from app.repos.endpoint_tool_runs_repo import EndpointToolRunsRepo, ToolRunProjection
    from domain_ports.endpoint_tools import ToolRunRequestV1
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with maker() as session:
        async with session.begin():
            device = str(uuid4())
            ticket = await seed(session, device)
            repo = EndpointToolRunsRepo(session)
            run = await repo.create_pending(ToolRunRequestV1(kind="diagnostic"), actor_id="actor",
                ticket_id=ticket, device_ref=device, caller_key="key")
            old = Operation(operation_id=str(uuid4()), kind="endpoint_operation", actor_role="system",
                            trace_id=str(uuid4()), status="queued", queued_at=now)
            session.add(old)
            await session.flush()
            session.add(EndpointOperationLink(link_id=str(uuid4()), operation_id=old.operation_id,
                endpoint_device_ref=str(uuid4()), create_idempotency_key="historical",
                capability_code="endpoint.module.recipe", module_key="old.module", module_version="1.0.0",
                remote_status="create_pending", next_attempt_at=now))
    async with maker() as session:
        async with session.begin():
            claims = await EndpointToolRunsRepo(session).claim_ready(owner="one", limit=10, now=now+timedelta(seconds=1))
            assert [c.run.run_id for c in claims] == [run.run_id]
    async with maker() as session:
        async with session.begin():
            repo = EndpointToolRunsRepo(session)
            assert await repo.claim_ready(owner="two", limit=10, now=now+timedelta(seconds=2)) == []
            claim = claims[0]
            stale = type(claim)(run=claim.run, lease_token="wrong")
            assert not await repo.commit_projection(stale, ToolRunProjection(status="failed", error_code="endpoint_unavailable"), now=now)
            assert await repo.commit_projection(claim, ToolRunProjection(status="failed", error_code="endpoint_unavailable"), now=now)
            old_link = (await session.execute(select(EndpointOperationLink).where(EndpointOperationLink.create_idempotency_key == "historical"))).scalar_one()
            assert old_link.remote_status == "create_pending" and old_link.lease_owner is None


@pytest.mark.asyncio
async def test_concurrent_last_children_finalize_parent_session(test_engine):
    from app.repos.endpoint_tool_runs_repo import EndpointToolRunsRepo,ToolRunProjection
    from app.services.endpoint_tool_run_service import collection_requests
    from app.db.models import DiagnosticSession
    maker=async_sessionmaker(test_engine,expire_on_commit=False)
    now=datetime.now(timezone.utc);batch=str(uuid4())
    async with maker() as session:
        async with session.begin():
            device=str(uuid4());ticket=await seed(session,device)
            repo=EndpointToolRunsRepo(session)
            for i,request in enumerate(collection_requests()):
                await repo.create_pending(request,actor_id="actor",ticket_id=ticket,device_ref=device,caller_key=f"child{i}",batch_id=batch)
    async with maker() as session:
        async with session.begin():claims=await EndpointToolRunsRepo(session).claim_ready(owner="batch",limit=6,now=now+timedelta(seconds=1))
    for claim in claims[:4]:
        async with maker() as session:
            async with session.begin():await EndpointToolRunsRepo(session).commit_projection(claim,ToolRunProjection("succeeded",str(uuid4())),now=now)
    both_read=asyncio.Event();reads=0
    class OverlapSession(AsyncSession):
        async def execute(self,statement,*args,**kwargs):
            nonlocal reads
            result=await super().execute(statement,*args,**kwargs)
            if str(statement).startswith("SELECT endpoint_operation_links.remote_status"):
                reads+=1
                if reads==2:both_read.set()
                try:await asyncio.wait_for(both_read.wait(),1)
                except asyncio.TimeoutError:pass  # Correct parent locking serializes the second reader.
            return result
    concurrent=async_sessionmaker(test_engine,class_=OverlapSession,expire_on_commit=False)
    async def finish(claim):
        async with concurrent() as session:
            async with session.begin():await EndpointToolRunsRepo(session).commit_projection(claim,ToolRunProjection("succeeded",str(uuid4())),now=now)
    await asyncio.gather(*(finish(claim) for claim in claims[4:]))
    async with maker() as session:
        parent=await session.get(DiagnosticSession,batch)
        assert parent.status=="completed" and parent.finished_at is not None
