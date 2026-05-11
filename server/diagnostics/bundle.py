from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiagnosticBundle, Operation, RemoteAccessSession, Ticket
from app.repos.diagnostics_repo import DiagnosticRepo
from diagnostics.serialization import evidence_to_dict, operation_to_dict, remote_session_to_dict


class DiagnosticBundleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DiagnosticRepo(session)

    async def build_bundle(
        self,
        *,
        ticket_id: str,
        session_id: str | None,
        actor: Any,
        include_agent_actions: bool = False,
        include_observer: bool = True,
        include_artifacts: bool = True,
        include_remote_assist: bool = True,
        include_monitoring: bool = True,
    ) -> DiagnosticBundle:
        ticket = await self.session.get(Ticket, ticket_id)
        selected = await self.repo.list_evidence(ticket_id, session_id=session_id, selected_only=True)
        evidence = selected or await self.repo.list_evidence(ticket_id, session_id=session_id)
        artifact_refs: list[dict[str, Any]] = []
        for item in evidence:
            if include_artifacts:
                artifact_refs.extend(item.artifact_refs or [])
        observer_trace_ids = []
        if include_observer and ticket is not None and ticket.observer_root_trace_id:
            observer_trace_ids.append(ticket.observer_root_trace_id)
        remote_sessions = []
        if include_remote_assist:
            remote_sessions = list(
                (
                    await self.session.execute(
                        select(RemoteAccessSession)
                        .where(RemoteAccessSession.ticket_id == ticket_id)
                        .order_by(RemoteAccessSession.created_at.desc())
                        .limit(20)
                    )
                ).scalars()
            )
        operations = []
        if include_agent_actions:
            operations = list(
                (
                    await self.session.execute(
                        select(Operation).where(Operation.ticket_id == ticket_id).order_by(Operation.queued_at.desc()).limit(20)
                    )
                ).scalars()
            )
        payload = {
            "ticket_id": ticket_id,
            "session_id": session_id,
            "ticket": {
                "ticket_id": getattr(ticket, "ticket_id", ticket_id),
                "title": getattr(ticket, "title", None),
                "status": getattr(ticket, "status", None),
                "device_id": getattr(ticket, "device_id", None),
            },
            "evidence": [evidence_to_dict(item) for item in evidence],
            "operations": [operation_to_dict(item) for item in operations],
            "remote_assist": [remote_session_to_dict(item) for item in remote_sessions],
            "include_monitoring": include_monitoring,
        }
        actor_id = getattr(actor, "actor_id", None) if actor is not None else actor
        return await self.repo.create_bundle(
            ticket_id=ticket_id,
            session_id=session_id,
            created_by_user_id=str(actor_id) if actor_id else None,
            status="ready",
            summary=f"Diagnostic bundle with {len(evidence)} evidence item(s)",
            evidence_ids=[item.id for item in evidence],
            artifact_refs=artifact_refs,
            observer_trace_ids=observer_trace_ids,
            remote_assist_session_ids=[item.id for item in remote_sessions],
            payload=payload,
        )

    async def get_bundle(self, bundle_id: str) -> DiagnosticBundle | None:
        return await self.repo.get_bundle(bundle_id)
