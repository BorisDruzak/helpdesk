from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Artifact, DiagnosticBundle, DiagnosticEvidence, DiagnosticFinding, DiagnosticSession, Operation, RemoteAccessSession, Ticket, TicketEvent, TicketEvidenceItem
from diagnostics.bundle import DiagnosticBundleService
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.findings import DiagnosticFindingService
from diagnostics.handlers import _result_should_persist_as_evidence
from diagnostics.passport_bridge import DiagnosticPassportBridgeService
from diagnostics.projection import DiagnosticProjectionService
from diagnostics.profile_runner import DiagnosticProfileRunnerService
from diagnostics.service import DiagnosticOverviewService
from diagnostics.sessions import DiagnosticSessionService


pytestmark = pytest.mark.db_cleanup("observer_diagnostics")

SUPPORT_TOKEN = "test-ui-support-token"


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {SUPPORT_TOKEN}"}


def _ticket(ticket_id: str, device_id: str, *, root_trace_id: str | None = None) -> Ticket:
    return Ticket(
        ticket_id=ticket_id,
        device_id=device_id,
        title="Website unavailable",
        description="HTTP checks fail for user",
        status="in_progress",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        updated_at=datetime.now(timezone.utc),
        observer_root_trace_id=root_trace_id,
    )


def test_agent_recipe_waiting_dependency_result_does_not_persist_evidence():
    capability = CapabilityDescriptor(
        id="endpoint.file.exists",
        title="File exists",
        execution_target="agent_recipe",
        evidence={"produces_evidence": True},
    )

    assert _result_should_persist_as_evidence(capability, {"status": "waiting_dependency"}) is False


def test_endpoint_operation_overview_projection_is_strictly_allowlisted():
    from diagnostics.service import _endpoint_operation_overview_projection

    projection = _endpoint_operation_overview_projection(
        SimpleNamespace(operation_id="local-operation-1"),
        SimpleNamespace(remote_status="queued", safe_result_snapshot_json={"processes": []}),
    )

    assert projection == {
        "operation_id": "local-operation-1",
        "status": "queued",
        "result_available": True,
    }
    assert _endpoint_operation_overview_projection(
        SimpleNamespace(operation_id="local-operation-2"),
        SimpleNamespace(remote_status="unexpected", safe_result_snapshot_json=None),
    ) is None


@pytest.mark.asyncio
async def test_empty_diagnostics_overview_is_unknown(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        await session.commit()

    async with session_maker() as session:
        overview = await DiagnosticOverviewService(session).get_ticket_diagnostics_overview(ticket_id, actor=None)

    assert overview["ticket_id"] == ticket_id
    assert overview["status"] == "unknown"
    assert overview["evidence_counts"] == {"ok": 0, "warning": 0, "error": 0, "info": 0, "unknown": 0}
    assert overview["latest_evidence"] == []
    assert overview["recommended_actions"]


@pytest.mark.asyncio
async def test_operation_and_diag_logs_artifact_project_to_evidence(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="diag.logs.collect",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc) - timedelta(minutes=5),
                started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
                finished_at=datetime.now(timezone.utc) - timedelta(minutes=4),
                result_summary="Collected diagnostic logs",
            )
        )
        session.add(
            Artifact(
                artifact_id=artifact_id,
                storage_path="diagnostics/logs.zip",
                original_name="logs.zip",
                mime_type="application/zip",
                size_bytes=1024,
                sha256="a" * 64,
                kind="logs_zip",
                device_id=device_id,
                ticket_id=ticket_id,
                operation_id=operation_id,
            )
        )
        await session.commit()

    async with session_maker() as session:
        evidence = await DiagnosticProjectionService(session).project_operation_result(operation_id)
        await session.commit()

    assert evidence.kind == "logs.bundle"
    assert evidence.domain == "logs"
    assert evidence.perspective == "endpoint"
    assert evidence.status == "ok"
    assert evidence.passport_eligible is True
    assert evidence.artifact_refs == [{"artifact_id": artifact_id, "kind": "logs_zip"}]

    async with session_maker() as session:
        rows = (await session.execute(select(DiagnosticEvidence).where(DiagnosticEvidence.ticket_id == ticket_id))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_remote_assist_session_projects_to_passport_eligible_evidence(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    remote_session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        session.add(
            RemoteAccessSession(
                id=remote_session_id,
                ticket_id=ticket_id,
                device_id=device_id,
                operator_id="support-test",
                mode="view_only",
                status="ended",
                consent_required=True,
                consent_status="approved",
                requested_at=now - timedelta(minutes=10),
                approved_at=now - timedelta(minutes=9),
                started_at=now - timedelta(minutes=8),
                ended_at=now - timedelta(minutes=6),
                expires_at=now + timedelta(minutes=5),
                close_reason="completed",
            )
        )
        await session.commit()

    async with session_maker() as session:
        evidence = await DiagnosticProjectionService(session).project_remote_assist_session(remote_session_id)
        await session.commit()

    assert evidence.kind == "remote_assist.session"
    assert evidence.domain == "remote_assist"
    assert evidence.perspective == "remote_assist"
    assert evidence.status == "ok"
    assert evidence.passport_eligible is True
    assert evidence.normalized_payload["consent_status"] == "approved"
    assert evidence.normalized_payload["duration_seconds"] == 120


@pytest.mark.asyncio
async def test_session_lifecycle_findings_selection_and_bundle(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        await session.commit()

    async with session_maker() as session:
        session_service = DiagnosticSessionService(session)
        diagnostic_session = await session_service.create_session(
            ticket_id=ticket_id,
            profile_id="website_unavailable",
            trigger_source="manual",
            actor="support-test",
        )
        step = await session_service.add_step(
            session_id=diagnostic_session.id,
            ticket_id=ticket_id,
            step_type="manual_check",
            status="ok",
            result_summary="Manual check completed",
        )
        endpoint_evidence = await DiagnosticProjectionService(session).create_manual_evidence(
            ticket_id=ticket_id,
            session_id=diagnostic_session.id,
            step_id=step.id,
            title="Endpoint HTTP failed",
            summary="Endpoint received HTTP 502",
            status="error",
            kind="network.http",
            domain="network",
            perspective="endpoint",
            created_by="support",
        )
        server_evidence = await DiagnosticProjectionService(session).create_manual_evidence(
            ticket_id=ticket_id,
            session_id=diagnostic_session.id,
            title="Server HTTP failed",
            summary="Server-side HTTP check also failed",
            status="error",
            kind="network.http",
            domain="network",
            perspective="server",
            created_by="support",
        )
        await session.flush()
        findings = await DiagnosticFindingService(session).evaluate_ticket(ticket_id, session_id=diagnostic_session.id)
        endpoint_evidence.selected_for_passport = True
        bundle = await DiagnosticBundleService(session).build_bundle(
            ticket_id=ticket_id,
            session_id=diagnostic_session.id,
            actor="support-test",
            include_agent_actions=True,
        )
        await session.commit()

    assert diagnostic_session.status == "draft"
    assert step.session_id == diagnostic_session.id
    assert {item.root_cause_code for item in findings} == {"server_side_problem"}
    assert {server_evidence.id, endpoint_evidence.id}.issuperset(set(findings[0].evidence_ids))
    assert bundle.status == "ready"
    assert endpoint_evidence.id in bundle.evidence_ids
    assert bundle.payload["ticket_id"] == ticket_id

    async with session_maker() as session:
        stored_bundle = await session.get(DiagnosticBundle, bundle.id)
        stored_finding = (await session.execute(select(DiagnosticFinding).where(DiagnosticFinding.ticket_id == ticket_id))).scalar_one()
        stored_session = await session.get(DiagnosticSession, diagnostic_session.id)
    assert stored_bundle is not None
    assert stored_finding.status == "suspected"
    assert stored_session is not None


@pytest.mark.asyncio
async def test_diagnostics_overview_api_projects_existing_sources(test_client):
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())
    root_trace_id = str(uuid.uuid4())

    from app.db import get_session

    async with get_session() as session:
        session.add(_ticket(ticket_id, device_id, root_trace_id=root_trace_id))
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="endpoint.http.request",
                actor_role="support",
                trace_id=root_trace_id,
                status="failed",
                queued_at=datetime.now(timezone.utc) - timedelta(minutes=5),
                finished_at=datetime.now(timezone.utc) - timedelta(minutes=4),
                error_code="HTTP_502",
                error_message="Bad gateway",
            )
        )
        await session.commit()

    response = await test_client.get(f"/api/tickets/{ticket_id}/diagnostics/overview", headers=_auth())
    assert response.status == 200
    payload = await response.json()

    assert payload["ticket_id"] == ticket_id
    assert payload["status"] == "error"
    assert payload["evidence_counts"]["error"] >= 1
    assert payload["observer"]["root_trace_id"] == root_trace_id
    assert payload["latest_operations"][0]["operation_id"] == operation_id

    web_response = await test_client.get(f"/api/web/support/tickets/{ticket_id}/diagnostics/overview", headers=_auth())
    assert web_response.status == 200
    web_payload = await web_response.json()
    assert web_payload["status"] == "success"
    assert web_payload["data"]["ticket_id"] == ticket_id

    for suffix, key in (
        ("capabilities", "capabilities"),
        ("evidence", "evidence"),
        ("sessions", "sessions"),
        ("findings", "findings"),
    ):
        alias_response = await test_client.get(
            f"/api/web/support/tickets/{ticket_id}/diagnostics/{suffix}",
            headers=_auth(),
        )
        assert alias_response.status == 200
        alias_payload = await alias_response.json()
        assert alias_payload["status"] == "ok"
        assert key in alias_payload

    capabilities_response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/diagnostics/capabilities",
        headers=_auth(),
    )
    capabilities_payload = await capabilities_response.json()
    capabilities_by_id = {item["id"]: item for item in capabilities_payload["capabilities"]}
    assert capabilities_by_id["server.http.request"]["params_schema"]["required"] == ["url"]
    assert "url" in capabilities_by_id["server.http.request"]["params_schema"]["properties"]
    assert capabilities_by_id["server.http.request"]["output_contract"]


@pytest.mark.asyncio
async def test_selected_diagnostic_evidence_attaches_to_passport_idempotently(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        session.add(
            Artifact(
                artifact_id="artifact-1",
                storage_path="diagnostics/logs.zip",
                original_name="logs.zip",
                mime_type="application/zip",
                size_bytes=1024,
                sha256="b" * 64,
                kind="logs_zip",
                device_id=device_id,
                ticket_id=ticket_id,
            )
        )
        await session.flush()
        evidence = await DiagnosticProjectionService(session).create_manual_evidence(
            ticket_id=ticket_id,
            title="Logs available",
            summary="Collected diagnostic logs are attached",
            status="ok",
            kind="logs.bundle",
            domain="logs",
            perspective="endpoint",
            created_by="support",
            artifact_refs=[{"artifact_id": "artifact-1", "kind": "logs_zip"}],
            passport_eligible=True,
        )
        evidence.selected_for_passport = True
        first = await DiagnosticPassportBridgeService(session).attach_selected_diagnostic_evidence_to_passport(
            ticket_id=ticket_id,
            actor="support-test",
        )
        second = await DiagnosticPassportBridgeService(session).attach_selected_diagnostic_evidence_to_passport(
            ticket_id=ticket_id,
            actor="support-test",
        )
        await session.commit()

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id == second[0].id
    assert first[0].evidence_type == "diagnostic_result"
    assert first[0].source_ref == f"diagnostic_evidence:{evidence.id}"
    assert first[0].source_kind == "diagnostic_evidence"
    assert first[0].source_id == evidence.id
    assert first[0].required_fact == "evidence"
    assert first[0].section_key == "evidence"
    assert first[0].verification_status == "accepted"
    assert first[0].artifact_id == "artifact-1"
    assert first[0].metadata_json["diagnostic_kind"] == "logs.bundle"

    async with session_maker() as session:
        rows = (await session.execute(select(TicketEvidenceItem).where(TicketEvidenceItem.ticket_id == ticket_id))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_run_profile_creates_session_steps_projects_sources_and_selects_evidence(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="endpoint.http.request",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="failed",
                queued_at=datetime.now(timezone.utc) - timedelta(minutes=5),
                finished_at=datetime.now(timezone.utc) - timedelta(minutes=4),
                error_code="HTTP_502",
                error_message="Bad gateway",
            )
        )
        result = await DiagnosticProfileRunnerService(session).run_profile(
            ticket_id=ticket_id,
            profile_id="website_unavailable",
            params={"url": "https://example.invalid"},
            auto_select_evidence=True,
            actor="support-test",
        )
        await session.commit()

    assert result["session"]["profile_id"] == "website_unavailable"
    assert result["session"]["status"] == "completed"
    assert any(step["step_type"] == "server_capability" for step in result["steps"])
    assert any(step["capability_id"] == "endpoint.http.request" for step in result["steps"])
    assert result["evidence_count"] >= 1
    assert result["selected_for_passport_count"] >= 1

    async with session_maker() as session:
        evidence = (await session.execute(select(DiagnosticEvidence).where(DiagnosticEvidence.ticket_id == ticket_id))).scalars().all()
        diagnostic_session = (await session.execute(select(DiagnosticSession).where(DiagnosticSession.ticket_id == ticket_id))).scalar_one()

    assert diagnostic_session.status == "completed"
    assert any(item.selected_for_passport for item in evidence)


@pytest.mark.asyncio
async def test_run_profile_and_attach_selected_api(test_client):
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    from app.db import get_session

    async with get_session() as session:
        session.add(_ticket(ticket_id, device_id))
        await session.commit()

    run_response = await test_client.post(
        f"/api/tickets/{ticket_id}/diagnostics/run-profile",
        headers=_auth(),
        json={"profile_id": "generic", "params": {}, "auto_select_evidence": True},
    )
    assert run_response.status == 201
    run_payload = await run_response.json()
    assert run_payload["status"] == "ok"
    assert run_payload["profile_id"] == "generic"
    assert run_payload["session"]["status"] == "completed"

    manual_response = await test_client.post(
        f"/api/tickets/{ticket_id}/diagnostics/evidence/manual",
        headers=_auth(),
        json={
            "title": "Manual vendor response",
            "summary": "Vendor confirmed outage",
            "status": "warning",
            "kind": "manual.vendor_response",
            "domain": "manual",
            "perspective": "manual",
            "passport_eligible": True,
        },
    )
    assert manual_response.status == 201
    evidence_payload = await manual_response.json()
    evidence_id = evidence_payload["evidence"]["id"]
    assert evidence_payload["evidence"]["kind"] == "manual.vendor_response"
    patch_response = await test_client.patch(
        f"/api/tickets/{ticket_id}/diagnostics/evidence/{evidence_id}",
        headers=_auth(),
        json={"selected_for_passport": True},
    )
    assert patch_response.status == 200

    attach_response = await test_client.post(
        f"/api/tickets/{ticket_id}/diagnostics/passport/attach-selected",
        headers=_auth(),
        json={},
    )
    assert attach_response.status == 200
    attach_payload = await attach_response.json()
    assert attach_payload["status"] == "ok"
    assert attach_payload["attached_count"] == 1
    assert attach_payload["evidence"][0]["source_id"] == evidence_id


@pytest.mark.asyncio
async def test_manual_capability_run_creates_diagnostic_evidence_event_and_passport_candidate(test_client):
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    from app.db import get_session

    async with get_session() as session:
        session.add(_ticket(ticket_id, device_id))
        await session.commit()

    response = await test_client.post(
        f"/api/tickets/{ticket_id}/diagnostics/capabilities/manual.operator_note/run",
        headers=_auth(),
        json={
            "params": {
                "title": "Operator note",
                "summary": "Operator confirmed the printer display shows an offline warning",
                "status": "warning",
                "tags": ["printer", "onsite"],
                "selected_for_passport": True,
            }
        },
    )

    assert response.status == 200
    payload = await response.json()
    assert payload["status"] == "created"
    assert payload["execution_target"] == "manual"
    assert payload["execution_kind"] == "manual_evidence"
    assert payload["output"]["selected_for_passport"] is True
    assert payload["evidence_preview"]["kind"] == "manual.operator_note"

    async with get_session() as session:
        evidence = (
            await session.execute(
                select(DiagnosticEvidence).where(
                    DiagnosticEvidence.ticket_id == ticket_id,
                    DiagnosticEvidence.capability_id == "manual.operator_note",
                )
            )
        ).scalar_one()
        event = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.event_type == "diagnostic_manual_evidence_created",
                )
            )
        ).scalar_one()

    assert evidence.kind == "manual.operator_note"
    assert evidence.source_type == "manual"
    assert evidence.selected_for_passport is True
    assert evidence.created_by == "support-test"
    assert evidence.tags == ["printer", "onsite"]
    assert event.payload["evidence_id"] == evidence.id
    assert event.payload["capability_id"] == "manual.operator_note"
