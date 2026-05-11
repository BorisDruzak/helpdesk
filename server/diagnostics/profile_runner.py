from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiagnosticEvidence
from app.repos.diagnostics_repo import DiagnosticRepo
from diagnostics.findings import DiagnosticFindingService
from diagnostics.profiles import get_profile, resolve_ticket_profile
from diagnostics.projection import DiagnosticProjectionService
from diagnostics.serialization import evidence_to_dict, finding_to_dict, session_to_dict, step_to_dict
from diagnostics.sessions import DiagnosticSessionService


class DiagnosticProfileRunnerService:
    """MVP profile runner that creates a diagnostic session and planned steps.

    It does not replace playbook execution. For now it projects already available
    ticket sources, records recommended capability/playbook steps, evaluates
    findings and optionally preselects passport-eligible evidence.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DiagnosticRepo(session)

    async def run_profile(
        self,
        *,
        ticket_id: str,
        profile_id: str | None,
        params: dict[str, Any] | None,
        auto_select_evidence: bool,
        actor: Any,
    ) -> dict[str, Any]:
        from app.db.models import Ticket

        ticket = await self.session.get(Ticket, ticket_id)
        if ticket is None:
            raise KeyError("ticket not found")
        profile = get_profile(profile_id) if profile_id else None
        if profile is None:
            profile = resolve_ticket_profile(ticket)
        session_service = DiagnosticSessionService(self.session)
        diagnostic_session = await session_service.create_session(
            ticket_id=ticket_id,
            profile_id=profile["id"],
            trigger_source="diagnostic_profile",
            actor=actor,
            profile_version=profile.get("version"),
        )
        steps = []
        for capability_id in profile.get("recommended_capabilities") or []:
            target = "server_capability"
            if str(capability_id).startswith("observer."):
                target = "observer_query"
            elif str(capability_id).startswith("zabbix."):
                target = "server_connector"
            elif str(capability_id).startswith("remote_assist."):
                target = "remote_assist"
            elif str(capability_id).startswith("manual."):
                target = "manual_check"
            elif str(capability_id).startswith("endpoint.") or str(capability_id).startswith("diag."):
                target = "agent_tool"
            steps.append(
                await session_service.add_step(
                    session_id=diagnostic_session.id,
                    ticket_id=ticket_id,
                    step_type=target,
                    capability_id=str(capability_id),
                    status="pending",
                    result_summary="Recommended by diagnostic profile",
                )
            )
        for playbook_id in profile.get("recommended_playbooks") or []:
            steps.append(
                await session_service.add_step(
                    session_id=diagnostic_session.id,
                    ticket_id=ticket_id,
                    step_type="playbook",
                    capability_id=str(playbook_id),
                    status="pending",
                    result_summary="Recommended by diagnostic profile",
                )
            )
        await DiagnosticProjectionService(self.session).project_ticket_sources(ticket_id)
        evidence = await self.repo.list_evidence(ticket_id)
        required = set(profile.get("required_evidence_kinds") or [])
        optional = set(profile.get("optional_evidence_kinds") or [])
        selected_count = 0
        if auto_select_evidence:
            for item in evidence:
                if item.passport_eligible and (item.kind in required or item.kind in optional or not required):
                    item.selected_for_passport = True
                    selected_count += 1
        findings = await DiagnosticFindingService(self.session).evaluate_ticket(ticket_id, session_id=diagnostic_session.id)
        completed = await session_service.complete_session(
            diagnostic_session.id,
            summary=f"Diagnostic profile {profile['id']} prepared {len(steps)} step(s).",
            confidence=0.5 if evidence else None,
        )
        diagnostic_session = completed or diagnostic_session
        await self.session.flush()
        evidence = await self.repo.list_evidence(ticket_id)
        selected_count = len([item for item in evidence if item.selected_for_passport])
        return {
            "ticket_id": ticket_id,
            "profile_id": profile["id"],
            "params": params or {},
            "session": session_to_dict(diagnostic_session),
            "steps": [step_to_dict(item) for item in steps],
            "evidence_count": len(evidence),
            "selected_for_passport_count": selected_count,
            "latest_evidence": [evidence_to_dict(item) for item in evidence[:8]],
            "findings": [finding_to_dict(item) for item in findings],
        }
