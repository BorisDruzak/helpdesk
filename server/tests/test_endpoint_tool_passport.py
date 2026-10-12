from datetime import datetime,timezone
import importlib.util
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest

pytestmark=pytest.mark.db_cleanup("full")


def run_fixture(status="failed",safe=True):
    from domain_ports.endpoint_tools import ToolRunRequestV1
    return SimpleNamespace(run_id=str(uuid4()),ticket_id=str(uuid4()),device_ref=str(uuid4()),remote_ref=str(uuid4()),
        request=ToolRunRequestV1(kind="diagnostic"),status=status,
        safe_result={"profile":"diagnostic_v1","collected_at":datetime.now(timezone.utc).isoformat(),
            "reason":"Диагностика по обращению","warnings":[],"processes":[],"log_excerpt":None} if safe else None)


@pytest.mark.no_db
def test_failed_safe_result_keeps_failure_status_and_immutable_provenance():
    assert importlib.util.find_spec("diagnostics.endpoint_tool_evidence") is not None
    from diagnostics.endpoint_tool_evidence import materialize_tool_evidence
    run=run_fixture()
    draft=materialize_tool_evidence(run,0)
    assert draft.status=="failed" and draft.source_type=="endpoint_platform"
    assert draft.normalized_payload["provenance"]["device_ref"]==run.device_ref
    assert len(draft.normalized_payload["digest_sha256"])==64
    run.safe_result["warnings"].append("later_change")
    assert draft.normalized_payload["result"]["warnings"]==[]


@pytest.mark.parametrize("status,safe",[("queued",True),("succeeded",False),("expired",False)])
@pytest.mark.no_db
def test_unfinished_or_missing_results_are_not_passport_evidence(status,safe):
    from diagnostics.endpoint_tool_evidence import materialize_tool_evidence
    with pytest.raises(ValueError): materialize_tool_evidence(run_fixture(status,safe),0)


@pytest.mark.no_db
def test_snapshot_digest_is_deterministic_and_step_identity_is_distinct():
    from diagnostics.endpoint_tool_evidence import materialize_tool_evidence
    run=run_fixture("succeeded")
    a,b=materialize_tool_evidence(run,0),materialize_tool_evidence(run,0)
    assert a.evidence_id==b.evidence_id and a.normalized_payload==b.normalized_payload
    with pytest.raises(ValueError): materialize_tool_evidence(run,1)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_retained_attachment_replay_does_not_require_expired_remote_result(monkeypatch):
    from app.db.models import Ticket,DiagnosticEvidence
    from app.repos.endpoint_tool_runs_repo import EndpointToolRunsRepo
    from diagnostics.endpoint_tool_evidence import materialize_tool_evidence
    from diagnostics.passport_bridge import DiagnosticPassportBridgeService
    run=run_fixture("succeeded"); draft=materialize_tool_evidence(run,0); run.safe_result=None
    retained=SimpleNamespace(id=draft.evidence_id,ticket_id=run.ticket_id,source_type="endpoint_platform",kind="endpoint_tool_result",
        source_id=draft.source_id,normalized_payload=draft.normalized_payload,selected_for_passport=True)
    async def get(model,_id,**kwargs):
        return SimpleNamespace(endpoint_device_ref=run.device_ref) if model is Ticket else retained if model is DiagnosticEvidence else None
    session=SimpleNamespace(get=AsyncMock(side_effect=get),flush=AsyncMock())
    monkeypatch.setattr(EndpointToolRunsRepo,"get_authorized_run",AsyncMock(return_value=run))
    bridge=DiagnosticPassportBridgeService(session)
    bridge.passports.get_latest_passport=AsyncMock(return_value=None)
    bridge.attach_selected_diagnostic_evidence_to_passport=AsyncMock(return_value=[SimpleNamespace(id=123)])
    item=await bridge.attach_endpoint_tool_result(ticket_id=run.ticket_id,run_id=run.run_id,step_sequence=0,actor=SimpleNamespace(actor_id="admin"))
    assert item.id==123


@pytest.mark.asyncio
async def test_attach_same_evidence_is_idempotent_and_survives_provider_expiry(test_engine):
    from sqlalchemy import select,func
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.db.models import Ticket,TicketEvidenceItem,EndpointOperationLink
    from app.repos.endpoint_tool_runs_repo import EndpointToolRunsRepo,ToolRunProjection
    from domain_ports.endpoint_tools import ToolRunRequestV1
    from diagnostics.passport_bridge import DiagnosticPassportBridgeService
    ticket,device=str(uuid4()),str(uuid4()); now=datetime.now(timezone.utc)
    maker=async_sessionmaker(test_engine,expire_on_commit=False)
    result=run_fixture("succeeded").safe_result
    async with maker() as session:
        async with session.begin():
            session.add(Ticket(ticket_id=ticket,title="Passport",description="Fixture",status="in_progress",endpoint_device_ref=device))
            await session.flush()
            repo=EndpointToolRunsRepo(session)
            run=await repo.create_pending(ToolRunRequestV1(kind="diagnostic"),actor_id="admin",actor_role="admin",ticket_id=ticket,device_ref=device,caller_key="passport")
            claims=await repo.claim_ready(owner="test",limit=1,now=now.replace(year=now.year+1))
            await repo.commit_projection(claims[0],ToolRunProjection("succeeded",str(uuid4()),result),now=now)
            bridge=DiagnosticPassportBridgeService(session)
            first=await bridge.attach_endpoint_tool_result(ticket_id=ticket,run_id=run.run_id,step_sequence=0,actor=SimpleNamespace(actor_id="admin"))
            replay=await bridge.attach_endpoint_tool_result(ticket_id=ticket,run_id=run.run_id,step_sequence=0,actor=SimpleNamespace(actor_id="admin"))
            assert first.id==replay.id
            assert await session.scalar(select(func.count()).select_from(TicketEvidenceItem).where(TicketEvidenceItem.ticket_id==ticket))==1
            snapshot=first.metadata_json["endpoint_tool_snapshot"]
            link=(await session.execute(select(EndpointOperationLink).where(EndpointOperationLink.operation_id==run.run_id))).scalar_one()
            link.safe_result_snapshot_json=None
            await session.flush()
            assert snapshot["result"]["profile"]=="diagnostic_v1"
            replay_after_expiry=await bridge.attach_endpoint_tool_result(ticket_id=ticket,run_id=run.run_id,step_sequence=0,actor=SimpleNamespace(actor_id="admin"))
            assert replay_after_expiry.id==first.id
    async with maker() as session:
        stored=(await session.execute(select(TicketEvidenceItem).where(TicketEvidenceItem.ticket_id==ticket))).scalar_one()
        assert stored.metadata_json["endpoint_tool_snapshot"]==snapshot
