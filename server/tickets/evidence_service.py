from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Artifact,
    ObserverTrace,
    Operation,
    PlaybookRun,
    Ticket,
    TicketApproval,
    TicketEvent,
    TicketEvidenceItem,
    TicketWorklog,
)
from app.repos.ticket_passport_repo import TicketPassportRepo


TERMINAL_OPERATION_STATUSES = {"succeeded", "failed", "denied", "timed_out", "canceled"}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(value)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _operation_title(operation: Operation) -> str:
    return _clean(operation.tool_name) or _clean(operation.command_name) or _clean(operation.kind) or operation.operation_id


def _operation_summary(operation: Operation) -> str:
    return _clean(operation.result_summary) or _clean(operation.error_message) or _clean(operation.status)


def _artifact_evidence_type(artifact: Artifact) -> str:
    mime = _clean(artifact.mime_type).lower()
    kind = _clean(artifact.kind).lower()
    if mime.startswith("image/") or kind == "screenshot":
        return "screenshot"
    if mime.startswith("video/") or kind in {"video", "screen_recording"}:
        return "video"
    return "file_attachment"


class TicketEvidenceService:
    """Collects and links ticket-scoped evidence sources."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TicketPassportRepo(session)

    async def collect_candidates(self, ticket_id: str) -> list[dict[str, Any]]:
        ticket = await self.session.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError("ticket_not_found")

        existing = await self.repo.list_evidence(ticket_id)
        existing_by_source = {
            (item.source_kind, item.source_id, item.required_fact): item
            for item in existing
            if item.source_kind and item.source_id
        }

        candidates: list[dict[str, Any]] = []
        operations = await self._load_ticket_operations(ticket_id, ticket.device_id)
        for operation in operations:
            if operation.status not in TERMINAL_OPERATION_STATUSES:
                continue
            summary = _operation_summary(operation)
            if not summary:
                continue
            candidates.append(
                {
                    "candidate_id": f"operation:{operation.operation_id}",
                    "source_kind": "operation",
                    "source_id": operation.operation_id,
                    "source_ref": f"operation:{operation.operation_id}",
                    "source_quality": "ticket",
                    "evidence_type": "diagnostic_result" if operation.kind == "tool" else "operation_log",
                    "required_fact": "automated_checks",
                    "section_key": "automated_checks",
                    "title": _operation_title(operation),
                    "summary": summary,
                    "visibility": "internal",
                    "captured_at": _iso(operation.finished_at or operation.started_at or operation.queued_at),
                    "metadata_json": {
                        "operation_status": operation.status,
                        "tool_name": operation.tool_name,
                        "command_name": operation.command_name,
                        "trace_id": operation.trace_id,
                        "playbook_run_id": operation.playbook_run_id,
                    },
                    "existing_evidence_id": self._existing_id(
                        existing_by_source,
                        "operation",
                        operation.operation_id,
                        "automated_checks",
                    ),
                }
            )

        artifacts = await self._load_ticket_artifacts(ticket_id)
        for artifact in artifacts:
            evidence_type = _artifact_evidence_type(artifact)
            required_fact = "evidence"
            candidates.append(
                {
                    "candidate_id": f"artifact:{artifact.artifact_id}",
                    "source_kind": "artifact",
                    "source_id": artifact.artifact_id,
                    "source_ref": f"artifact:{artifact.artifact_id}",
                    "source_quality": "ticket",
                    "evidence_type": evidence_type,
                    "required_fact": required_fact,
                    "section_key": required_fact,
                    "artifact_id": artifact.artifact_id,
                    "title": artifact.original_name,
                    "summary": f"{artifact.mime_type}, {artifact.size_bytes} bytes",
                    "visibility": "internal",
                    "captured_at": _iso(artifact.created_at),
                    "metadata_json": {
                        "mime_type": artifact.mime_type,
                        "size_bytes": artifact.size_bytes,
                        "sha256": artifact.sha256,
                        "kind": artifact.kind,
                    },
                    "existing_evidence_id": self._existing_id(
                        existing_by_source,
                        "artifact",
                        artifact.artifact_id,
                        required_fact,
                    ),
                }
            )

        worklogs = await self._load_ticket_worklogs(ticket_id)
        for worklog in worklogs:
            candidates.append(
                {
                    "candidate_id": f"worklog:{worklog.id}",
                    "source_kind": "worklog",
                    "source_id": str(worklog.id),
                    "source_ref": f"worklog:{worklog.id}",
                    "source_quality": "ticket",
                    "evidence_type": "worklog",
                    "required_fact": "operator_checks",
                    "section_key": "operator_checks",
                    "title": f"Worklog {worklog.spent_minutes} min",
                    "summary": worklog.note or f"{worklog.spent_minutes} min by {worklog.actor_id}",
                    "visibility": "internal",
                    "captured_at": _iso(worklog.created_at),
                    "metadata_json": {
                        "actor_id": worklog.actor_id,
                        "spent_minutes": worklog.spent_minutes,
                    },
                    "existing_evidence_id": self._existing_id(
                        existing_by_source,
                        "worklog",
                        str(worklog.id),
                        "operator_checks",
                    ),
                }
            )

        approvals = await self._load_ticket_approvals(ticket_id)
        for approval in approvals:
            if approval.status not in {"approved", "rejected"}:
                continue
            candidates.append(
                {
                    "candidate_id": f"approval:{approval.id}",
                    "source_kind": "approval",
                    "source_id": str(approval.id),
                    "source_ref": f"approval:{approval.id}",
                    "source_quality": "ticket",
                    "evidence_type": "approval",
                    "required_fact": "approvals",
                    "section_key": "approvals",
                    "title": f"{approval.approval_type}: {approval.status}",
                    "summary": approval.reason or approval.status,
                    "visibility": "internal",
                    "captured_at": _iso(approval.decided_at or approval.requested_at),
                    "metadata_json": {
                        "approval_type": approval.approval_type,
                        "approver_id": approval.approver_id,
                        "status": approval.status,
                        "requested_by": approval.requested_by,
                    },
                    "existing_evidence_id": self._existing_id(
                        existing_by_source,
                        "approval",
                        str(approval.id),
                        "approvals",
                    ),
                }
            )

        chat_events = await self._load_ticket_chat_events(ticket_id)
        for event in chat_events:
            text = _clean(event.payload.get("text") or event.payload.get("message") or event.payload.get("body"))
            if not text:
                continue
            sender_role = _clean(event.payload.get("sender_role") or event.payload.get("from_role")).lower()
            visibility = _clean(event.payload.get("visibility") or "public").lower()
            if sender_role in {"requester", "user", "client", "device"}:
                required_fact = "user_result"
            elif visibility == "internal":
                required_fact = "operator_checks"
            else:
                required_fact = "changes_made"
            candidates.append(
                {
                    "candidate_id": f"chat_message:{event.id}",
                    "source_kind": "chat_message",
                    "source_id": str(event.id),
                    "source_ref": f"event:{event.id}",
                    "source_quality": "ticket",
                    "evidence_type": "chat_message",
                    "required_fact": required_fact,
                    "section_key": required_fact,
                    "title": f"Chat message #{event.id}",
                    "summary": text,
                    "visibility": "internal" if visibility == "internal" else "public",
                    "captured_at": _iso(event.created_at),
                    "metadata_json": {
                        "event_type": event.event_type,
                        "message_id": event.payload.get("message_id"),
                        "sender_role": sender_role,
                        "visibility": visibility,
                    },
                    "existing_evidence_id": self._existing_id(
                        existing_by_source,
                        "chat_message",
                        str(event.id),
                        required_fact,
                    ),
                }
            )

        observer_traces = await self._load_ticket_observer_traces(ticket_id)
        for trace in observer_traces:
            summary = _clean(trace.attrs_json.get("summary") if isinstance(trace.attrs_json, dict) else "")
            if not summary:
                summary = _clean(trace.attrs_json.get("signature") if isinstance(trace.attrs_json, dict) else "") or trace.status
            candidates.append(
                {
                    "candidate_id": f"observer_trace:{trace.trace_id}",
                    "source_kind": "observer_trace",
                    "source_id": trace.trace_id,
                    "source_ref": f"trace:{trace.trace_id}",
                    "source_quality": "ticket",
                    "evidence_type": "observer_trace",
                    "required_fact": "automated_checks",
                    "section_key": "automated_checks",
                    "title": trace.root_kind or "observer_trace",
                    "summary": summary,
                    "visibility": "internal",
                    "captured_at": _iso(trace.finished_at or trace.started_at),
                    "metadata_json": {
                        "root_kind": trace.root_kind,
                        "status": trace.status,
                        "operation_id": trace.operation_id,
                        "duration_ms": trace.duration_ms,
                        "span_count": trace.span_count,
                        "error_count": trace.error_count,
                        "attrs": trace.attrs_json or {},
                    },
                    "existing_evidence_id": self._existing_id(
                        existing_by_source,
                        "observer_trace",
                        trace.trace_id,
                        "automated_checks",
                    ),
                }
            )

        return candidates

    async def link_source(
        self,
        ticket_id: str,
        *,
        source_kind: str,
        source_id: str,
        required_fact: str | None,
        actor_id: str | None,
        visibility: str = "internal",
    ) -> TicketEvidenceItem:
        candidates = await self.collect_candidates(ticket_id)
        candidate = next(
            (
                item
                for item in candidates
                if item.get("source_kind") == source_kind and item.get("source_id") == source_id
            ),
            None,
        )
        if candidate is None:
            raise ValueError("evidence_source_not_found")
        fact = required_fact or str(candidate.get("required_fact") or "evidence")
        section_key = str(candidate.get("section_key") or fact)
        return await self.repo.add_evidence(
            ticket_id=ticket_id,
            passport_id=None,
            evidence_type=str(candidate["evidence_type"]),
            source_ref=str(candidate["source_ref"]),
            source_kind=source_kind,
            source_id=source_id,
            required_fact=fact,
            section_key=section_key,
            artifact_id=candidate.get("artifact_id"),
            title=str(candidate["title"]),
            summary=candidate.get("summary"),
            visibility=visibility if visibility in {"public", "internal"} else "internal",
            verification_status="accepted",
            captured_at=self._parse_candidate_datetime(candidate.get("captured_at")),
            metadata_json=dict(candidate.get("metadata_json") or {}),
            export_visibility="internal",
            created_by=actor_id,
        )

    async def update_evidence(
        self,
        ticket_id: str,
        evidence_id: int,
        *,
        verification_status: str | None,
        actor_id: str | None,
        reason: str | None = None,
        visibility: str | None = None,
        export_visibility: str | None = None,
        public_summary: str | None = None,
        internal_summary: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> TicketEvidenceItem:
        item = await self.session.scalar(
            select(TicketEvidenceItem)
            .where(TicketEvidenceItem.ticket_id == ticket_id, TicketEvidenceItem.id == evidence_id)
            .limit(1)
        )
        if item is None:
            raise ValueError("evidence_not_found")
        if verification_status:
            normalized = verification_status.strip().lower()
            if normalized not in {"accepted", "unverified", "rejected", "archived", "superseded"}:
                raise ValueError("invalid_verification_status")
            item.verification_status = normalized
            item.verified_by = actor_id
            item.verified_at = datetime.now(timezone.utc)
        if visibility:
            item.visibility = visibility if visibility in {"public", "internal"} else item.visibility
        if export_visibility:
            item.export_visibility = export_visibility if export_visibility in {"public", "internal", "hidden"} else item.export_visibility
        if public_summary is not None:
            item.public_summary = public_summary
        if internal_summary is not None:
            item.internal_summary = internal_summary
        metadata = dict(item.metadata_json or {})
        if metadata_json:
            metadata.update(metadata_json)
        if reason:
            metadata["verification_reason"] = reason
        item.metadata_json = metadata
        await self.session.flush()
        return item

    async def _load_ticket_operations(self, ticket_id: str, device_id: str | None) -> list[Operation]:
        playbook_run_ids = (
            select(PlaybookRun.id)
            .where(
                PlaybookRun.device_id == device_id,
                PlaybookRun.context_json["ticket_id"].astext == ticket_id,
            )
            .subquery()
        )
        result = await self.session.execute(
            select(Operation)
            .where(
                or_(
                    Operation.ticket_id == ticket_id,
                    Operation.playbook_run_id.in_(select(playbook_run_ids.c.id)),
                )
            )
            .order_by(Operation.queued_at.asc())
            .limit(100)
        )
        return list(result.scalars().all())

    async def _load_ticket_artifacts(self, ticket_id: str) -> list[Artifact]:
        result = await self.session.execute(
            select(Artifact)
            .where(Artifact.ticket_id == ticket_id)
            .order_by(Artifact.created_at.asc(), Artifact.artifact_id.asc())
            .limit(100)
        )
        return list(result.scalars().all())

    async def _load_ticket_worklogs(self, ticket_id: str) -> list[TicketWorklog]:
        result = await self.session.execute(
            select(TicketWorklog)
            .where(TicketWorklog.ticket_id == ticket_id)
            .order_by(TicketWorklog.created_at.asc(), TicketWorklog.id.asc())
            .limit(100)
        )
        return list(result.scalars().all())

    async def _load_ticket_approvals(self, ticket_id: str) -> list[TicketApproval]:
        result = await self.session.execute(
            select(TicketApproval)
            .where(TicketApproval.ticket_id == ticket_id)
            .order_by(TicketApproval.requested_at.asc(), TicketApproval.id.asc())
            .limit(100)
        )
        return list(result.scalars().all())

    async def _load_ticket_chat_events(self, ticket_id: str) -> list[TicketEvent]:
        result = await self.session.execute(
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "chat_message")
            .order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc())
            .limit(100)
        )
        return list(result.scalars().all())

    async def _load_ticket_observer_traces(self, ticket_id: str) -> list[ObserverTrace]:
        result = await self.session.execute(
            select(ObserverTrace)
            .where(ObserverTrace.ticket_id == ticket_id)
            .order_by(ObserverTrace.started_at.asc(), ObserverTrace.trace_id.asc())
            .limit(100)
        )
        return list(result.scalars().all())

    def _existing_id(
        self,
        existing_by_source: dict[tuple[str | None, str | None, str | None], TicketEvidenceItem],
        source_kind: str,
        source_id: str,
        required_fact: str,
    ) -> int | None:
        existing = existing_by_source.get((source_kind, source_id, required_fact))
        return existing.id if existing is not None else None

    def _parse_candidate_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
