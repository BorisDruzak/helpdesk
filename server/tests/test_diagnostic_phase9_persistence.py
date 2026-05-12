from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Artifact,
    DiagnosticArtifactLink,
    DiagnosticEvidence,
    DiagnosticSessionCapability,
    Ticket,
    TicketEvidenceItem,
)
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.evidence import normalize_tool_result_to_evidence_values
from diagnostics.passport_bridge import DiagnosticPassportBridgeService
from diagnostics.projection import DiagnosticEvidenceRetentionPolicy, DiagnosticProjectionService
from diagnostics.sessions import DiagnosticSessionService


def _ticket(ticket_id: str, device_id: str) -> Ticket:
    return Ticket(
        ticket_id=ticket_id,
        device_id=device_id,
        title="Phase 9 diagnostics",
        description="Capability evidence persistence",
        status="in_progress",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _capability() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id="server.http.request",
        title="Server HTTP request",
        provider_id="server_builtin",
        provider_type="server_builtin",
        execution_target="server_builtin",
        evidence={
            "produces_evidence": True,
            "kind": "network.http",
            "domain": "network",
            "perspective": "server",
            "passport_eligible": True,
        },
        artifacts={"may_produce_artifacts": True, "artifact_kinds": ["http_report"]},
        output_contract={"kind": "server.http_result", "version": "1.0.0"},
        source="server_builtin",
    )


@pytest.mark.no_db
def test_capability_result_mapper_builds_persistent_evidence_values_with_provenance():
    capability = _capability()
    values = normalize_tool_result_to_evidence_values(
        operation={
            "operation_id": "operation-1",
            "status": "succeeded",
            "trace_id": "11111111-1111-1111-1111-111111111111",
            "actor_id": "support-1",
        },
        capability_descriptor=capability,
        result={
            "status": "success",
            "summary": "HTTP GET https://example.local: 200",
            "output": {"status_code": 200, "url": "https://example.local"},
            "artifacts": [{"artifact_id": "artifact-1", "kind": "http_report"}],
            "raw_ref": "operation:operation-1",
            "redaction_level": "support",
            "tags": ["network", "server"],
        },
    )

    assert values["source_type"] == "operation"
    assert values["source_id"] == "operation-1"
    assert values["provider_id"] == "server_builtin"
    assert values["provider_type"] == "server_builtin"
    assert values["capability_id"] == "server.http.request"
    assert values["capability_version"] == "1.0.0"
    assert values["kind"] == "network.http"
    assert values["domain"] == "network"
    assert values["perspective"] == "server"
    assert values["status"] == "ok"
    assert values["artifact_refs"] == [{"artifact_id": "artifact-1", "kind": "http_report"}]
    assert values["trace_id"] == "11111111-1111-1111-1111-111111111111"
    assert values["raw_ref"] == "operation:operation-1"
    assert values["redaction_level"] == "support"
    assert values["tags"] == ["network", "server"]
    assert values["passport_eligible"] is True
    assert values["normalized_payload"]["capability"]["execution_target"] == "server_builtin"
    assert values["normalized_payload"]["result"]["output"]["status_code"] == 200


@pytest.mark.asyncio
async def test_capability_projection_persists_evidence_links_and_session_snapshot(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        await session.flush()
        session.add(
            Artifact(
                artifact_id=artifact_id,
                storage_path="diagnostics/http-report.json",
                original_name="http-report.json",
                mime_type="application/json",
                size_bytes=256,
                sha256="c" * 64,
                kind="http_report",
                device_id=device_id,
                ticket_id=ticket_id,
            )
        )
        diagnostic_session = await DiagnosticSessionService(session).create_session(
            ticket_id=ticket_id,
            profile_id="website_unavailable",
            trigger_source="manual",
            actor="support-1",
        )
        capability = _capability()
        projection = DiagnosticProjectionService(session)
        evidence = await projection.project_capability_result(
            ticket_id=ticket_id,
            capability_descriptor=capability,
            result={
                "status": "success",
                "operation_id": "operation-1",
                "summary": "HTTP GET https://example.local: 200",
                "output": {"status_code": 200, "url": "https://example.local"},
                "artifacts": [{"artifact_id": artifact_id, "kind": "http_report"}],
                "trace_id": str(uuid.uuid4()),
                "tags": ["network"],
            },
            actor="support-1",
            session_id=diagnostic_session.id,
            readiness={
                "readiness": "available",
                "reason_code": None,
                "reason": None,
                "actions": ["run"],
            },
            params={"url": "https://example.local"},
        )
        await session.commit()

    async with session_maker() as session:
        stored_evidence = await session.get(DiagnosticEvidence, evidence.id)
        capability_rows = (
            await session.execute(
                select(DiagnosticSessionCapability).where(
                    DiagnosticSessionCapability.session_id == diagnostic_session.id
                )
            )
        ).scalars().all()
        artifact_links = (
            await session.execute(
                select(DiagnosticArtifactLink).where(DiagnosticArtifactLink.evidence_id == evidence.id)
            )
        ).scalars().all()

    assert stored_evidence is not None
    assert stored_evidence.provider_id == "server_builtin"
    assert stored_evidence.capability_id == "server.http.request"
    assert stored_evidence.status == "ok"
    assert stored_evidence.normalized_payload["provenance"]["actor_id"] == "support-1"
    assert stored_evidence.normalized_payload["capability"]["provider_type"] == "server_builtin"
    assert len(capability_rows) == 1
    assert capability_rows[0].capability_id == "server.http.request"
    assert capability_rows[0].readiness_status == "available"
    assert capability_rows[0].evidence_id == evidence.id
    assert capability_rows[0].params_snapshot == {"url": "https://example.local"}
    assert len(artifact_links) == 1
    assert artifact_links[0].artifact_id == artifact_id
    assert artifact_links[0].artifact_kind == "http_report"
    assert artifact_links[0].capability_id == "server.http.request"


@pytest.mark.asyncio
async def test_capability_projection_is_idempotent_and_passport_bridge_uses_artifact_link(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    capability = _capability()

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        session.add(
            Artifact(
                artifact_id=artifact_id,
                storage_path="diagnostics/http-report.json",
                original_name="http-report.json",
                mime_type="application/json",
                size_bytes=256,
                sha256="d" * 64,
                kind="http_report",
                device_id=device_id,
                ticket_id=ticket_id,
            )
        )
        projection = DiagnosticProjectionService(session)
        first = await projection.project_capability_result(
            ticket_id=ticket_id,
            capability_descriptor=capability,
            result={
                "status": "success",
                "operation_id": "operation-2",
                "summary": "HTTP 200",
                "output": {"status_code": 200},
                "artifacts": [{"artifact_id": artifact_id, "kind": "http_report"}],
            },
            actor="support-1",
        )
        second = await projection.project_capability_result(
            ticket_id=ticket_id,
            capability_descriptor=capability,
            result={
                "status": "success",
                "operation_id": "operation-2",
                "summary": "HTTP 204",
                "output": {"status_code": 204},
                "artifacts": [{"artifact_id": artifact_id, "kind": "http_report"}],
            },
            actor="support-1",
        )
        second.selected_for_passport = True
        attached = await DiagnosticPassportBridgeService(session).attach_selected_diagnostic_evidence_to_passport(
            ticket_id=ticket_id,
            actor="support-1",
        )
        await session.commit()

    assert first.id == second.id
    assert second.summary == "HTTP 204"
    assert len(attached) == 1
    assert attached[0].artifact_id == artifact_id

    async with session_maker() as session:
        evidence_count = await session.scalar(select(func.count(DiagnosticEvidence.id)).where(DiagnosticEvidence.ticket_id == ticket_id))
        link_count = await session.scalar(select(func.count(DiagnosticArtifactLink.id)).where(DiagnosticArtifactLink.ticket_id == ticket_id))
        passport_rows = (
            await session.execute(select(TicketEvidenceItem).where(TicketEvidenceItem.ticket_id == ticket_id))
        ).scalars().all()

    assert evidence_count == 1
    assert link_count == 1
    assert len(passport_rows) == 1


@pytest.mark.asyncio
async def test_diagnostic_retention_keeps_selected_evidence_and_removes_old_unselected(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        projection = DiagnosticProjectionService(session)
        old_unselected = await projection.create_manual_evidence(
            ticket_id=ticket_id,
            title="Old unselected",
            summary="Old transient evidence",
            status="info",
            kind="manual.visual_check",
            domain="manual",
            perspective="manual",
            source_id="old-unselected",
        )
        old_unselected.observed_at = now - timedelta(days=400)
        old_selected = await projection.create_manual_evidence(
            ticket_id=ticket_id,
            title="Old selected",
            summary="Old passport evidence",
            status="ok",
            kind="manual.visual_check",
            domain="manual",
            perspective="manual",
            source_id="old-selected",
            selected_for_passport=True,
        )
        old_selected.observed_at = now - timedelta(days=400)
        recent = await projection.create_manual_evidence(
            ticket_id=ticket_id,
            title="Recent",
            summary="Recent transient evidence",
            status="info",
            kind="manual.visual_check",
            domain="manual",
            perspective="manual",
            source_id="recent",
        )
        recent.observed_at = now - timedelta(days=3)
        deleted_count = await DiagnosticEvidenceRetentionPolicy(session, retention_days=365).cleanup_unselected_evidence(now=now)
        await session.commit()

    assert deleted_count == 1

    async with session_maker() as session:
        rows = (await session.execute(select(DiagnosticEvidence).where(DiagnosticEvidence.ticket_id == ticket_id))).scalars().all()
    assert {row.source_id for row in rows} == {"old-selected", "recent"}
