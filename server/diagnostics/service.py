from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, DiagnosticEvidence, EndpointOperationLink, Operation, PlaybookRun, RemoteAccessSession, Ticket
from app.repos.diagnostics_repo import DiagnosticRepo
from diagnostics.findings import DiagnosticFindingService
from diagnostics.profiles import resolve_ticket_profile
from diagnostics.projection import DiagnosticProjectionService
from diagnostics.serialization import evidence_to_dict, finding_to_dict, operation_to_dict, remote_session_to_dict, iso


EVIDENCE_STATUSES = ("ok", "warning", "error", "info", "unknown")
PERSPECTIVES = ("endpoint", "server", "monitoring", "observer", "remote_assist", "manual", "hybrid")
_ENDPOINT_OPERATION_STATUSES = frozenset(
    {"create_pending", "queued", "delivered", "acknowledged", "running", "succeeded", "failed", "canceled", "expired"}
)


def _endpoint_operation_overview_projection(operation: Operation, link: EndpointOperationLink) -> dict[str, Any] | None:
    """Return only the support-safe state required by the diagnostics workspace."""

    if link.remote_status not in _ENDPOINT_OPERATION_STATUSES:
        return None
    return {
        "operation_id": operation.operation_id,
        "status": link.remote_status,
        "result_available": link.safe_result_snapshot_json is not None,
    }


def _overview_status(evidence: list[DiagnosticEvidence]) -> str:
    if not evidence:
        return "unknown"
    statuses = {item.status for item in evidence}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    if statuses <= {"info", "unknown"}:
        return "unknown"
    return "ok"


def _summary(status: str, evidence: list[DiagnosticEvidence]) -> str:
    if not evidence:
        return "No diagnostic evidence collected yet."
    counts = Counter(item.status for item in evidence)
    if status == "error":
        return f"Found {counts.get('error', 0)} error evidence item(s)."
    if status == "warning":
        return f"Found {counts.get('warning', 0)} warning evidence item(s)."
    return f"Collected {len(evidence)} diagnostic evidence item(s)."


def _counts(evidence: list[DiagnosticEvidence]) -> dict[str, int]:
    counts = Counter(item.status for item in evidence)
    return {status: int(counts.get(status, 0)) for status in EVIDENCE_STATUSES}


def _perspectives(evidence: list[DiagnosticEvidence]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[DiagnosticEvidence]] = defaultdict(list)
    for item in evidence:
        groups[item.perspective].append(item)
    result = {}
    for perspective in PERSPECTIVES:
        items = groups.get(perspective, [])
        result[perspective] = {
            "count": len(items),
            "status": _overview_status(items),
            "latest": evidence_to_dict(items[0]) if items else None,
        }
    return result


def _recommended_actions(ticket: Ticket | None, evidence: list[DiagnosticEvidence]) -> list[dict[str, Any]]:
    kinds = {item.kind for item in evidence}
    actions: list[dict[str, Any]] = []
    if not evidence:
        actions.append({"id": "run_basic_diagnostics", "title": "Run basic diagnostics", "kind": "capability"})
    if "logs.bundle" not in kinds and ticket is not None and ticket.device_id:
        actions.append({"id": "collect_logs", "title": "Collect diagnostic logs", "capability_id": "diag.logs.collect"})
    if "observer.summary" not in kinds:
        actions.append({"id": "review_observer", "title": "Review observer trace", "capability_id": "observer.ticket.summary"})
    if not any(item.perspective == "remote_assist" for item in evidence):
        actions.append({"id": "consider_remote_assist", "title": "Request remote assist if endpoint context is unclear"})
    return actions[:5]


class DiagnosticOverviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DiagnosticRepo(session)

    async def get_ticket_diagnostics_overview(self, ticket_id: str, actor: Any) -> dict[str, Any]:
        ticket = await self.session.get(Ticket, ticket_id)
        if ticket is None:
            raise KeyError("ticket not found")
        await DiagnosticProjectionService(self.session).project_ticket_sources(ticket_id)
        findings = await DiagnosticFindingService(self.session).evaluate_ticket(ticket_id)
        evidence = await self.repo.list_evidence(ticket_id)
        operations = list(
            (
                await self.session.execute(
                    select(Operation).where(Operation.ticket_id == ticket_id).order_by(Operation.queued_at.desc()).limit(10)
                )
            ).scalars()
        )
        endpoint_operation_rows = list(
            (
                await self.session.execute(
                    select(Operation, EndpointOperationLink)
                    .join(EndpointOperationLink, EndpointOperationLink.operation_id == Operation.operation_id)
                    .where(Operation.ticket_id == ticket_id)
                    .order_by(Operation.queued_at.desc())
                    .limit(10)
                )
            ).all()
        )
        playbooks = list(
            (
                await self.session.execute(
                    select(PlaybookRun)
                    .where(PlaybookRun.context_json["ticket_id"].astext == ticket_id)
                    .order_by(PlaybookRun.scheduled_at.desc())
                    .limit(10)
                )
            ).scalars()
        )
        remote_sessions = list(
            (
                await self.session.execute(
                    select(RemoteAccessSession)
                    .where(RemoteAccessSession.ticket_id == ticket_id)
                    .order_by(RemoteAccessSession.created_at.desc())
                    .limit(10)
                )
            ).scalars()
        )
        artifacts = list(
            (
                await self.session.execute(
                    select(Artifact).where(Artifact.ticket_id == ticket_id).order_by(Artifact.created_at.desc()).limit(10)
                )
            ).scalars()
        )
        status = _overview_status(evidence)
        profile = resolve_ticket_profile(ticket)
        return {
            "ticket_id": ticket_id,
            "device_id": ticket.device_id,
            "status": status,
            "summary": _summary(status, evidence),
            "profile": profile,
            "evidence_counts": _counts(evidence),
            "perspectives": _perspectives(evidence),
            "latest_evidence": [evidence_to_dict(item) for item in evidence[:8]],
            "latest_operations": [operation_to_dict(item) for item in operations],
            "endpoint_operations": [
                projection
                for operation, link in endpoint_operation_rows
                if (projection := _endpoint_operation_overview_projection(operation, link)) is not None
            ],
            "latest_playbooks": [
                {
                    "id": item.id,
                    "status": item.status,
                    "device_id": item.device_id,
                    "trigger_type": item.trigger_type,
                    "scheduled_at": iso(item.scheduled_at),
                    "started_at": iso(item.started_at),
                    "finished_at": iso(item.finished_at),
                    "error_code": item.error_code,
                    "error_message": item.error_message,
                }
                for item in playbooks
            ],
            "remote_assist": {
                "count": len(remote_sessions),
                "latest": remote_session_to_dict(remote_sessions[0]) if remote_sessions else None,
            },
            "observer": {
                "root_trace_id": ticket.observer_root_trace_id,
                "available": bool(ticket.observer_root_trace_id),
            },
            "artifacts": {
                "count": len(artifacts),
                "items": [
                    {
                        "artifact_id": item.artifact_id,
                        "kind": item.kind,
                        "operation_id": item.operation_id,
                        "created_at": iso(item.created_at),
                    }
                    for item in artifacts
                ],
            },
            "findings": [finding_to_dict(item) for item in findings],
            "recommended_actions": _recommended_actions(ticket, evidence),
        }
