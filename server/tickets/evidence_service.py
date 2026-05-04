from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, Operation, PlaybookRun, Ticket, TicketApproval, TicketEvidenceItem, TicketWorklog
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
