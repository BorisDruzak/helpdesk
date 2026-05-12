from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, DiagnosticEvidence, Operation, RemoteAccessSession, Ticket
from app.repos.diagnostics_repo import DiagnosticRepo
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.evidence import normalize_tool_result_to_evidence_values


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

    async def project_capability_result(
        self,
        *,
        ticket_id: str,
        capability_descriptor: CapabilityDescriptor,
        result: dict[str, Any],
        actor: Any = None,
        session_id: str | None = None,
        step_id: str | None = None,
        readiness: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> DiagnosticEvidence:
        operation = {
            "operation_id": result.get("operation_id"),
            "session_id": result.get("session_id"),
            "query_id": result.get("query_id"),
            "status": result.get("status"),
            "trace_id": result.get("trace_id"),
            "actor_id": _actor_id(actor),
        }
        values = normalize_tool_result_to_evidence_values(operation, capability_descriptor, result)
        provider_type = values.pop("provider_type", None)
        capability_version = values.pop("capability_version", None)
        values.update(
            {
                "ticket_id": ticket_id,
                "session_id": session_id,
                "step_id": step_id,
                "created_by": _created_by(actor),
                "selected_for_passport": bool(result.get("selected_for_passport") and values.get("passport_eligible")),
            }
        )
        evidence = await self.repo.upsert_evidence(**values)
        await self._persist_artifact_links(evidence)
        if session_id:
            operation_id = await self._existing_operation_id(result.get("operation_id"))
            await self.repo.upsert_session_capability(
                session_id=session_id,
                ticket_id=ticket_id,
                provider_id=capability_descriptor.provider_id,
                provider_type=provider_type or capability_descriptor.provider_type,
                capability_id=capability_descriptor.id,
                capability_version=capability_version,
                execution_target=capability_descriptor.execution_target,
                readiness_status=(readiness or {}).get("readiness"),
                readiness_reason_code=(readiness or {}).get("reason_code"),
                readiness_reason=(readiness or {}).get("reason"),
                readiness_actions=list((readiness or {}).get("actions") or []),
                params_snapshot=dict(params or {}),
                result_snapshot=_result_snapshot(result),
                evidence_id=evidence.id,
                operation_id=operation_id,
                session_ref=result.get("session_id"),
                query_ref=result.get("query_id"),
                status=evidence.status,
            )
        return evidence

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
        evidence = await self.repo.upsert_evidence(
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
        await self._persist_artifact_links(evidence)
        return evidence

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
        evidence = await self.repo.upsert_evidence(
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
        await self._persist_artifact_links(evidence)
        return evidence

    async def project_observer_summary(self, ticket: Ticket) -> DiagnosticEvidence | None:
        if not ticket.observer_root_trace_id:
            return None
        evidence = await self.repo.upsert_evidence(
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
        await self._persist_artifact_links(evidence)
        return evidence

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
        source_id: str | None = None,
        capability_id: str = "manual.visual_check",
        severity: str | None = None,
        confidence: float | None = None,
        normalized_payload: dict[str, Any] | None = None,
        raw_ref: str | None = None,
        artifact_refs: list[dict[str, Any]] | None = None,
        redaction_level: str | None = None,
        tags: list[str] | None = None,
        passport_eligible: bool = True,
        selected_for_passport: bool = False,
    ) -> DiagnosticEvidence:
        normalized_status = str(status or "info").strip().lower() or "info"
        evidence = await self.repo.upsert_evidence(
            ticket_id=ticket_id,
            session_id=session_id,
            step_id=step_id,
            source_type="manual",
            source_id=source_id,
            provider_id="manual",
            capability_id=capability_id,
            kind=kind,
            domain=domain,
            perspective=perspective,
            title=title,
            summary=summary,
            status=normalized_status,
            severity=severity or ("none" if normalized_status == "ok" else ("medium" if normalized_status == "error" else "low")),
            confidence=confidence,
            normalized_payload=normalized_payload or {},
            raw_ref=raw_ref,
            artifact_refs=artifact_refs or [],
            redaction_level=redaction_level,
            tags=tags or [],
            passport_eligible=passport_eligible,
            selected_for_passport=bool(selected_for_passport and passport_eligible),
            created_by=created_by,
        )
        await self._persist_artifact_links(evidence)
        return evidence

    async def _persist_artifact_links(self, evidence: DiagnosticEvidence) -> None:
        for ref in evidence.artifact_refs or []:
            normalized = _artifact_link_ref(ref)
            if not normalized:
                continue
            artifact_id = normalized.get("artifact_id")
            if artifact_id:
                artifact = await self.session.get(Artifact, artifact_id)
                if artifact is None:
                    artifact_id = None
            await self.repo.upsert_artifact_link(
                ticket_id=evidence.ticket_id,
                session_id=evidence.session_id,
                step_id=evidence.step_id,
                evidence_id=evidence.id,
                artifact_id=artifact_id,
                artifact_kind=normalized.get("kind"),
                source_type=evidence.source_type,
                source_id=evidence.source_id,
                provider_id=evidence.provider_id,
                capability_id=evidence.capability_id,
                trace_id=evidence.trace_id,
                metadata_json={"artifact_ref": ref},
            )

    async def _existing_operation_id(self, operation_id: Any) -> str | None:
        value = str(operation_id or "").strip()
        if not value:
            return None
        operation = await self.session.get(Operation, value)
        return value if operation is not None else None


class DiagnosticEvidenceRetentionPolicy:
    """Retention cleanup for transient diagnostic evidence."""

    def __init__(self, session: AsyncSession, *, retention_days: int = 365):
        self.session = session
        self.retention_days = max(1, int(retention_days))
        self.repo = DiagnosticRepo(session)

    async def cleanup_unselected_evidence(self, *, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        cutoff = current - timedelta(days=self.retention_days)
        return await self.repo.cleanup_unselected_evidence_before(cutoff)


def _actor_id(actor: Any) -> str | None:
    if actor is None:
        return None
    value = getattr(actor, "actor_id", None)
    if value:
        return str(value)
    return str(actor)


def _created_by(actor: Any) -> str:
    if actor is None:
        return "system"
    role = getattr(actor, "actor_role", None)
    if role:
        return str(role)
    return "support"


def _result_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "operation_id": result.get("operation_id"),
        "session_id": result.get("session_id"),
        "query_id": result.get("query_id"),
        "summary": result.get("summary") or result.get("message"),
        "error_code": result.get("error_code"),
        "error_message": result.get("error_message"),
        "output": result.get("output") if isinstance(result.get("output"), dict) else {},
        "evidence_preview": result.get("evidence_preview") if isinstance(result.get("evidence_preview"), dict) else None,
    }


def _artifact_link_ref(ref: Any) -> dict[str, Any] | None:
    if isinstance(ref, dict):
        artifact_id = ref.get("artifact_id") or ref.get("id")
        kind = ref.get("kind") or ref.get("artifact_kind")
        path = ref.get("path")
        if not artifact_id and not kind and not path:
            return None
        return {
            "artifact_id": str(artifact_id) if artifact_id else None,
            "kind": str(kind) if kind else None,
            "path": str(path) if path else None,
        }
    if isinstance(ref, str) and ref:
        return {"artifact_id": ref, "kind": None, "path": None}
    return None
