from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiagnosticEvidence, TicketEvidenceItem
from app.repos.diagnostics_repo import DiagnosticRepo
from app.repos.ticket_passport_repo import TicketPassportRepo


def _actor_id(actor: Any) -> str | None:
    if actor is None:
        return None
    value = getattr(actor, "actor_id", None)
    if value:
        return str(value)
    return str(actor)


def _first_artifact_id(evidence: DiagnosticEvidence) -> str | None:
    refs = evidence.artifact_refs or []
    for ref in refs:
        if isinstance(ref, dict) and ref.get("artifact_id"):
            return str(ref["artifact_id"])
        if isinstance(ref, str) and ref:
            return ref
    return None


class DiagnosticPassportBridgeService:
    """Bridge selected diagnostic evidence into existing passport evidence rows."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.diagnostics = DiagnosticRepo(session)
        self.passports = TicketPassportRepo(session)

    async def attach_selected_diagnostic_evidence_to_passport(
        self,
        *,
        ticket_id: str,
        actor: Any,
        passport_id: int | None = None,
    ) -> list[TicketEvidenceItem]:
        selected = [
            item
            for item in await self.diagnostics.list_evidence(ticket_id, selected_only=True)
            if item.passport_eligible
        ]
        attached: list[TicketEvidenceItem] = []
        for item in selected:
            attached.append(
                await self.passports.add_evidence(
                    ticket_id=ticket_id,
                    passport_id=passport_id,
                    evidence_type="diagnostic_result",
                    source_ref=f"diagnostic_evidence:{item.id}",
                    source_kind="diagnostic_evidence",
                    source_id=item.id,
                    required_fact="evidence",
                    section_key="evidence",
                    artifact_id=_first_artifact_id(item),
                    title=item.title,
                    summary=item.summary,
                    visibility="support",
                    verification_status="accepted",
                    captured_at=item.observed_at,
                    public_summary=None,
                    internal_summary=item.summary,
                    metadata_json={
                        "diagnostic_evidence_id": item.id,
                        "diagnostic_kind": item.kind,
                        "domain": item.domain,
                        "perspective": item.perspective,
                        "status": item.status,
                        "severity": item.severity,
                        "confidence": float(item.confidence) if item.confidence is not None else None,
                        "provider_id": item.provider_id,
                        "capability_id": item.capability_id,
                        "source_type": item.source_type,
                        "source_id": item.source_id,
                        "artifact_refs": item.artifact_refs or [],
                        "trace_id": item.trace_id,
                    },
                    export_visibility="internal",
                    created_by=_actor_id(actor),
                )
            )
        return attached
