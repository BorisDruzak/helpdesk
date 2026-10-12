from __future__ import annotations

from typing import Any
import json
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiagnosticEvidence, TicketEvidenceItem, Ticket
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
        evidence_ids: set[str] | None = None,
    ) -> list[TicketEvidenceItem]:
        await self.session.get(Ticket,ticket_id,with_for_update=True)
        selected = [
            item
            for item in await self.diagnostics.list_evidence(ticket_id, selected_only=True)
            if item.passport_eligible
            and (evidence_ids is None or item.id in evidence_ids)
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
                        **({"endpoint_tool_snapshot":json.loads(json.dumps(item.normalized_payload))}
                            if item.source_type=="endpoint_platform" and item.kind=="endpoint_tool_result" else {}),
                    },
                    export_visibility="internal",
                    created_by=_actor_id(actor),
                )
            )
        return attached

    async def attach_endpoint_tool_result(self,*,ticket_id,run_id,step_sequence,actor):
        from app.repos.endpoint_tool_runs_repo import EndpointToolRunsRepo
        from diagnostics.endpoint_tool_evidence import materialize_tool_evidence
        ticket=await self.session.get(Ticket,ticket_id,with_for_update=True)
        run=await EndpointToolRunsRepo(self.session).get_authorized_run(run_id,ticket_id)
        if ticket is None or run is None: raise LookupError("run not found")
        if ticket.endpoint_device_ref!=run.device_ref: raise ValueError("ticket device changed")
        draft=materialize_tool_evidence(run,step_sequence)
        existing=await self.session.get(DiagnosticEvidence,draft.evidence_id)
        if existing is not None:
            if existing.ticket_id!=ticket_id or existing.normalized_payload!=draft.normalized_payload:
                raise ValueError("immutable evidence conflicts")
            existing.selected_for_passport=True
        else:
            self.session.add(DiagnosticEvidence(id=draft.evidence_id,ticket_id=ticket_id,source_type=draft.source_type,
                source_id=draft.source_id,provider_id="endpoint_platform",capability_id=draft.capability_id,
                kind="endpoint_tool_result",domain="endpoint",perspective="device",title=draft.title,
                summary="Проверка завершена" if draft.status=="succeeded" else "Проверка завершена с ошибкой",
                status=draft.status,observed_at=draft.observed_at,normalized_payload=draft.normalized_payload,
                passport_eligible=True,selected_for_passport=True,created_by="support",redaction_level="safe_projection"))
        await self.session.flush()
        passport=await self.passports.get_latest_passport(ticket_id)
        items=await self.attach_selected_diagnostic_evidence_to_passport(ticket_id=ticket_id,actor=actor,
            passport_id=passport.id if passport else None,evidence_ids={draft.evidence_id})
        return items[0]
