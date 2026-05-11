from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, DiagnosticEvidence, Operation, RemoteAccessSession, Ticket
from app.repos.diagnostics_repo import DiagnosticRepo


def _status_from_operation(status: str | None) -> str:
    if status == "succeeded":
        return "ok"
    if status in {"failed", "timed_out"}:
        return "error"
    if status in {"denied", "canceled", "cancel_requested"}:
        return "warning"
    if status in {"queued", "sent", "accepted", "running", "waiting_consent"}:
        return "info"
    return "unknown"


def _operation_metadata(tool_name: str | None) -> dict[str, Any]:
    tool = (tool_name or "").strip()
    mapping = {
        "diag.logs.collect": {
            "kind": "logs.bundle",
            "domain": "logs",
            "perspective": "endpoint",
            "title": "Diagnostic logs collected",
            "passport_eligible": True,
        },
        "screen.collect": {
            "kind": "screen.capture",
            "domain": "endpoint",
            "perspective": "endpoint",
            "title": "Screen capture",
            "passport_eligible": True,
        },
        "screen.record": {
            "kind": "screen.recording",
            "domain": "endpoint",
            "perspective": "endpoint",
            "title": "Screen recording",
            "passport_eligible": True,
        },
        "endpoint.http.request": {
            "kind": "network.http",
            "domain": "network",
            "perspective": "endpoint",
            "title": "Endpoint HTTP check",
            "passport_eligible": True,
        },
        "server.http.request": {
            "kind": "network.http",
            "domain": "network",
            "perspective": "server",
            "title": "Server HTTP check",
            "passport_eligible": True,
        },
        "endpoint.dns.resolve": {
            "kind": "network.dns",
            "domain": "network",
            "perspective": "endpoint",
            "title": "Endpoint DNS check",
            "passport_eligible": True,
        },
    }
    return mapping.get(
        tool,
        {
            "kind": tool or "operation.result",
            "domain": "diagnostic",
            "perspective": "endpoint",
            "title": tool or "Operation result",
            "passport_eligible": False,
        },
    )


def _remote_status(status: str | None) -> str:
    if status in {"ended", "completed"}:
        return "ok"
    if status in {"denied", "expired", "canceled"}:
        return "warning"
    if status == "failed":
        return "error"
    if status in {"requested", "approved", "active"}:
        return "info"
    return "unknown"


class DiagnosticProjectionService:
    """Project existing runtime entities into normalized diagnostic evidence."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DiagnosticRepo(session)

    async def project_operation_result(self, operation_id: str) -> DiagnosticEvidence:
        operation = await self.session.get(Operation, operation_id)
        if operation is None or not operation.ticket_id:
            raise ValueError("operation not found or not linked to ticket")
        metadata = _operation_metadata(operation.tool_name)
        artifacts = list(
            (
                await self.session.execute(
                    select(Artifact).where(
                        Artifact.ticket_id == operation.ticket_id,
                        Artifact.operation_id == operation.operation_id,
                    )
                )
            ).scalars()
        )
        artifact_refs = [{"artifact_id": item.artifact_id, "kind": item.kind} for item in artifacts]
        payload = {
            "operation_id": operation.operation_id,
            "tool_name": operation.tool_name,
            "operation_status": operation.status,
            "error_code": operation.error_code,
            "error_message": operation.error_message,
            "artifact_count": len(artifact_refs),
        }
        summary = operation.result_summary or operation.error_message or operation.error_code or operation.status
        return await self.repo.upsert_evidence(
            ticket_id=operation.ticket_id,
            source_type="operation",
            source_id=operation.operation_id,
            provider_id=operation.tool_name.split(".", 1)[0] if operation.tool_name and "." in operation.tool_name else None,
            capability_id=operation.tool_name,
            kind=metadata["kind"],
            domain=metadata["domain"],
            perspective=metadata["perspective"],
            title=metadata["title"],
            summary=summary,
            status=_status_from_operation(operation.status),
            severity="none" if operation.status == "succeeded" else ("medium" if operation.status in {"failed", "timed_out"} else "low"),
            observed_at=operation.finished_at or operation.started_at or operation.queued_at or datetime.now(timezone.utc),
            normalized_payload=payload,
            artifact_refs=artifact_refs,
            trace_id=operation.trace_id,
            passport_eligible=bool(metadata.get("passport_eligible")),
            created_by="system",
        )

    async def project_remote_assist_session(self, session_id: str) -> DiagnosticEvidence:
        remote = await self.session.get(RemoteAccessSession, session_id)
        if remote is None:
            raise ValueError("remote assist session not found")
        duration_seconds = None
        if remote.started_at and remote.ended_at:
            duration_seconds = max(0, int((remote.ended_at - remote.started_at).total_seconds()))
        summary = f"Remote assist {remote.mode}: {remote.status}"
        if duration_seconds is not None:
            summary = f"{summary}, {duration_seconds}s"
        payload = {
            "mode": remote.mode,
            "status": remote.status,
            "consent_required": remote.consent_required,
            "consent_status": remote.consent_status,
            "operator_id": remote.operator_id,
            "duration_seconds": duration_seconds,
            "close_reason": remote.close_reason,
        }
        return await self.repo.upsert_evidence(
            ticket_id=remote.ticket_id,
            source_type="remote_assist",
            source_id=remote.id,
            provider_id="remote_assist",
            capability_id="remote_assist.session.summary",
            kind="remote_assist.session",
            domain="remote_assist",
            perspective="remote_assist",
            title="Remote assist session",
            summary=summary,
            status=_remote_status(remote.status),
            severity="none" if _remote_status(remote.status) == "ok" else "low",
            observed_at=remote.ended_at or remote.started_at or remote.requested_at,
            normalized_payload=payload,
            passport_eligible=True,
            created_by="system",
        )

    async def project_observer_summary(self, ticket: Ticket) -> DiagnosticEvidence | None:
        if not ticket.observer_root_trace_id:
            return None
        return await self.repo.upsert_evidence(
            ticket_id=ticket.ticket_id,
            source_type="observer",
            source_id=ticket.observer_root_trace_id,
            provider_id="observer",
            capability_id="observer.ticket.summary",
            kind="observer.summary",
            domain="observer",
            perspective="observer",
            title="Observer ticket trace",
            summary="Observer root trace is linked to the ticket",
            status="info",
            severity="none",
            observed_at=ticket.updated_at or datetime.now(timezone.utc),
            normalized_payload={"root_trace_id": ticket.observer_root_trace_id},
            trace_id=ticket.observer_root_trace_id,
            passport_eligible=True,
            created_by="system",
        )

    async def project_ticket_sources(self, ticket_id: str) -> None:
        ticket = await self.session.get(Ticket, ticket_id)
        if ticket is None:
            return
        operations = list(
            (
                await self.session.execute(
                    select(Operation)
                    .where(Operation.ticket_id == ticket_id)
                    .order_by(Operation.queued_at.desc())
                    .limit(25)
                )
            ).scalars()
        )
        for operation in operations:
            if operation.status in {"succeeded", "failed", "timed_out", "denied", "canceled"}:
                await self.project_operation_result(operation.operation_id)
        remotes = list(
            (
                await self.session.execute(
                    select(RemoteAccessSession)
                    .where(RemoteAccessSession.ticket_id == ticket_id)
                    .order_by(RemoteAccessSession.created_at.desc())
                    .limit(10)
                )
            ).scalars()
        )
        for remote in remotes:
            await self.project_remote_assist_session(remote.id)
        await self.project_observer_summary(ticket)

    async def create_manual_evidence(
        self,
        *,
        ticket_id: str,
        title: str,
        summary: str | None,
        status: str,
        kind: str,
        domain: str,
        perspective: str,
        created_by: str = "support",
        session_id: str | None = None,
        step_id: str | None = None,
        artifact_refs: list[dict[str, Any]] | None = None,
        passport_eligible: bool = True,
    ) -> DiagnosticEvidence:
        return await self.repo.upsert_evidence(
            ticket_id=ticket_id,
            session_id=session_id,
            step_id=step_id,
            source_type="manual",
            source_id=None,
            provider_id="manual",
            capability_id="manual.visual_check",
            kind=kind,
            domain=domain,
            perspective=perspective,
            title=title,
            summary=summary,
            status=status,
            severity="none" if status == "ok" else ("medium" if status == "error" else "low"),
            normalized_payload={},
            artifact_refs=artifact_refs or [],
            passport_eligible=passport_eligible,
            created_by=created_by,
        )
