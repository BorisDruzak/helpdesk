from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import and_, bindparam, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.models import (
    AgentObserverEvent,
    AgentRuntimeAudit,
    Artifact,
    Operation,
    ObserverErrorOccurrence,
    ObserverTrace,
    RemoteAccessEvent,
    RemoteAccessSession,
    Ticket,
    TicketAdminAudit,
    TicketEvent,
)
from config import UPLOAD_DIR


ACTIVE_OPERATION_STATUSES = {
    "queued",
    "sent",
    "accepted",
    "running",
    "waiting_consent",
    "cancel_requested",
}

TERMINAL_REMOTE_ACCESS_STATUSES = {
    "ended",
    "denied",
    "expired",
    "failed",
    "canceled",
}

MAX_PURGE_TICKET_IDS = 500


@dataclass(slots=True)
class ArtifactFileRef:
    artifact_id: str
    storage_path: str


class TicketPurgeBlockedError(Exception):
    def __init__(self, preview: dict[str, Any]) -> None:
        super().__init__("Ticket purge is blocked")
        self.preview = preview


class TicketPurgeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def normalize_ticket_ids(raw_ticket_ids: Any) -> list[str]:
        if not isinstance(raw_ticket_ids, list):
            raise ValueError("ticket_ids must be a list")
        ticket_ids: list[str] = []
        seen: set[str] = set()
        for raw_ticket_id in raw_ticket_ids:
            ticket_id = str(raw_ticket_id or "").strip()
            if not ticket_id or ticket_id in seen:
                continue
            seen.add(ticket_id)
            ticket_ids.append(ticket_id)
        if not ticket_ids:
            raise ValueError("ticket_ids must not be empty")
        if len(ticket_ids) > MAX_PURGE_TICKET_IDS:
            raise ValueError(f"ticket_ids is limited to {MAX_PURGE_TICKET_IDS} items")
        return ticket_ids

    async def preview(self, ticket_ids: list[str]) -> dict[str, Any]:
        existing_ids = await self._existing_ticket_ids(ticket_ids)
        missing_ids = [ticket_id for ticket_id in ticket_ids if ticket_id not in set(existing_ids)]
        blockers = await self._find_blockers(existing_ids)
        affected_counts = await self._affected_counts(existing_ids)
        return {
            "dry_run": True,
            "requested_count": len(ticket_ids),
            "found_count": len(existing_ids),
            "ticket_ids": existing_ids,
            "missing_ticket_ids": missing_ids,
            "can_purge": not blockers,
            "blockers": blockers,
            "affected_counts": affected_counts,
            "purged_ticket_ids": [],
            "artifact_files_deleted": 0,
            "artifact_file_errors": [],
        }

    async def purge(self, ticket_ids: list[str], *, actor_id: str | None = None, reason: str | None = None) -> dict[str, Any]:
        preview = await self.preview(ticket_ids)
        if not preview["can_purge"]:
            raise TicketPurgeBlockedError(preview)
        existing_ids = list(preview["ticket_ids"])
        if not existing_ids:
            result = dict(preview)
            result["dry_run"] = False
            return result

        artifact_refs = await self._artifact_file_refs(existing_ids)
        trace_ids = await self._trace_ids(existing_ids)

        await self._delete_ticket_events_archive(existing_ids)
        await self._delete_ticket_admin_audit_archive(existing_ids)
        await self.session.execute(
            delete(TicketAdminAudit).where(
                TicketAdminAudit.entity_type == "ticket",
                TicketAdminAudit.entity_id.in_(existing_ids),
            )
        )
        await self.session.execute(delete(TicketEvent).where(TicketEvent.ticket_id.in_(existing_ids)))
        await self.session.execute(delete(RemoteAccessEvent).where(RemoteAccessEvent.ticket_id.in_(existing_ids)))
        await self.session.execute(delete(RemoteAccessSession).where(RemoteAccessSession.ticket_id.in_(existing_ids)))

        await self.session.execute(delete(AgentRuntimeAudit).where(AgentRuntimeAudit.ticket_id.in_(existing_ids)))
        await self.session.execute(delete(AgentObserverEvent).where(AgentObserverEvent.ticket_id.in_(existing_ids)))

        occurrence_filter = ObserverErrorOccurrence.ticket_id.in_(existing_ids)
        if trace_ids:
            occurrence_filter = or_(occurrence_filter, ObserverErrorOccurrence.trace_id.in_(trace_ids))
        await self.session.execute(delete(ObserverErrorOccurrence).where(occurrence_filter))
        await self.session.execute(delete(ObserverTrace).where(ObserverTrace.ticket_id.in_(existing_ids)))

        await self.session.execute(delete(Artifact).where(Artifact.ticket_id.in_(existing_ids)))
        await self.session.execute(delete(Operation).where(Operation.ticket_id.in_(existing_ids)))
        await self.session.execute(delete(Ticket).where(Ticket.ticket_id.in_(existing_ids)))
        await self.session.flush()

        file_result = self._delete_artifact_files(artifact_refs)
        result = await self.preview(ticket_ids)
        result.update(
            {
                "dry_run": False,
                "requested_count": preview["requested_count"],
                "found_count": len(existing_ids),
                "ticket_ids": existing_ids,
                "missing_ticket_ids": preview["missing_ticket_ids"],
                "can_purge": True,
                "blockers": [],
                "affected_counts": preview["affected_counts"],
                "purged_ticket_ids": existing_ids,
                "artifact_files_deleted": file_result["deleted"],
                "artifact_file_errors": file_result["errors"],
            }
        )
        logger.info(
            "[ticket_purge] actor_id={} reason={} purged={} counts={} file_errors={}",
            actor_id,
            reason,
            existing_ids,
            preview["affected_counts"],
            len(file_result["errors"]),
        )
        return result

    async def _existing_ticket_ids(self, ticket_ids: list[str]) -> list[str]:
        if not ticket_ids:
            return []
        rows = await self.session.execute(select(Ticket.ticket_id).where(Ticket.ticket_id.in_(ticket_ids)))
        found = set(rows.scalars().all())
        return [ticket_id for ticket_id in ticket_ids if ticket_id in found]

    async def _find_blockers(self, ticket_ids: list[str]) -> list[dict[str, Any]]:
        if not ticket_ids:
            return []
        blockers: list[dict[str, Any]] = []
        ticket_set = set(ticket_ids)

        child_rows = await self.session.execute(
            select(Ticket.parent_ticket_id, Ticket.ticket_id, Ticket.status)
            .where(Ticket.parent_ticket_id.in_(ticket_ids))
            .order_by(Ticket.parent_ticket_id, Ticket.ticket_id)
        )
        for parent_ticket_id, child_ticket_id, status in child_rows.all():
            if child_ticket_id in ticket_set:
                continue
            blockers.append(
                {
                    "type": "child_ticket",
                    "ticket_id": parent_ticket_id,
                    "related_id": child_ticket_id,
                    "status": status,
                }
            )

        operation_rows = await self.session.execute(
            select(Operation.ticket_id, Operation.operation_id, Operation.status)
            .where(and_(Operation.ticket_id.in_(ticket_ids), Operation.status.in_(ACTIVE_OPERATION_STATUSES)))
            .order_by(Operation.ticket_id, Operation.operation_id)
        )
        for ticket_id, operation_id, status in operation_rows.all():
            blockers.append(
                {
                    "type": "active_operation",
                    "ticket_id": ticket_id,
                    "related_id": operation_id,
                    "status": status,
                }
            )

        remote_rows = await self.session.execute(
            select(RemoteAccessSession.ticket_id, RemoteAccessSession.id, RemoteAccessSession.status)
            .where(
                and_(
                    RemoteAccessSession.ticket_id.in_(ticket_ids),
                    RemoteAccessSession.status.notin_(TERMINAL_REMOTE_ACCESS_STATUSES),
                )
            )
            .order_by(RemoteAccessSession.ticket_id, RemoteAccessSession.id)
        )
        for ticket_id, session_id, status in remote_rows.all():
            blockers.append(
                {
                    "type": "active_remote_access",
                    "ticket_id": ticket_id,
                    "related_id": session_id,
                    "status": status,
                }
            )

        return blockers

    async def _affected_counts(self, ticket_ids: list[str]) -> dict[str, int]:
        counts = {name: 0 for name in self._counted_relationship_names()}
        if not ticket_ids:
            return counts

        counts["tickets"] = await self._count_table("tickets", "ticket_id", ticket_ids)
        direct_ticket_tables = [
            "ticket_waits",
            "ticket_resolution_passports",
            "ticket_evidence_items",
            "ticket_action_log",
            "ticket_approvals",
            "ticket_related_objects",
            "ticket_watchers",
            "ticket_kb_links",
            "ticket_knowledge_links",
            "ticket_worklogs",
            "ticket_notifications",
            "ticket_feedback",
            "ticket_reopen_events",
            "ticket_quality_reviews",
            "problem_ticket_links",
            "ticket_change_links",
            "ticket_public_sessions",
            "diagnostic_sessions",
            "diagnostic_steps",
            "diagnostic_session_capabilities",
            "diagnostic_evidence",
            "diagnostic_findings",
            "ticket_events",
            "operations",
            "remote_access_sessions",
            "remote_access_events",
            "artifacts",
            "agent_runtime_audit",
            "agent_observer_events",
            "observer_traces",
            "observer_error_occurrences",
        ]
        for table_name in direct_ticket_tables:
            counts[table_name] = await self._count_table(table_name, "ticket_id", ticket_ids)

        counts["ticket_links"] = await self._count_ticket_links(ticket_ids)
        counts["ticket_events_archive"] = await self._count_ticket_events_archive(ticket_ids)
        counts["ticket_admin_audit"] = await self._count_ticket_admin_audit(ticket_ids)
        counts["ticket_admin_audit_archive"] = await self._count_ticket_admin_audit_archive(ticket_ids)
        return counts

    @staticmethod
    def _counted_relationship_names() -> list[str]:
        return [
            "tickets",
            "ticket_waits",
            "ticket_resolution_passports",
            "ticket_evidence_items",
            "ticket_action_log",
            "ticket_approvals",
            "ticket_related_objects",
            "ticket_watchers",
            "ticket_links",
            "ticket_kb_links",
            "ticket_knowledge_links",
            "ticket_worklogs",
            "ticket_notifications",
            "ticket_feedback",
            "ticket_reopen_events",
            "ticket_quality_reviews",
            "problem_ticket_links",
            "ticket_change_links",
            "ticket_public_sessions",
            "diagnostic_sessions",
            "diagnostic_steps",
            "diagnostic_session_capabilities",
            "diagnostic_evidence",
            "diagnostic_findings",
            "ticket_events",
            "ticket_events_archive",
            "operations",
            "remote_access_sessions",
            "remote_access_events",
            "artifacts",
            "agent_runtime_audit",
            "agent_observer_events",
            "observer_traces",
            "observer_error_occurrences",
            "ticket_admin_audit",
            "ticket_admin_audit_archive",
        ]

    async def _count_table(self, table_name: str, column_name: str, values: list[str]) -> int:
        table = Base.metadata.tables.get(table_name)
        if table is None or column_name not in table.c:
            return 0
        result = await self.session.scalar(select(func.count()).select_from(table).where(table.c[column_name].in_(values)))
        return int(result or 0)

    async def _count_ticket_links(self, ticket_ids: list[str]) -> int:
        table = Base.metadata.tables.get("ticket_links")
        if table is None:
            return 0
        result = await self.session.scalar(
            select(func.count())
            .select_from(table)
            .where(or_(table.c.src_ticket_id.in_(ticket_ids), table.c.dst_ticket_id.in_(ticket_ids)))
        )
        return int(result or 0)

    async def _trace_ids(self, ticket_ids: list[str]) -> list[str]:
        result = await self.session.execute(select(ObserverTrace.trace_id).where(ObserverTrace.ticket_id.in_(ticket_ids)))
        return list(result.scalars().all())

    async def _artifact_file_refs(self, ticket_ids: list[str]) -> list[ArtifactFileRef]:
        result = await self.session.execute(
            select(Artifact.artifact_id, Artifact.storage_path).where(Artifact.ticket_id.in_(ticket_ids))
        )
        return [ArtifactFileRef(artifact_id=row[0], storage_path=row[1]) for row in result.all()]

    def _delete_artifact_files(self, refs: list[ArtifactFileRef]) -> dict[str, Any]:
        deleted = 0
        errors: list[dict[str, str]] = []
        upload_root = Path(UPLOAD_DIR).resolve()
        for ref in refs:
            try:
                file_path = (upload_root / ref.storage_path).resolve()
                file_path.relative_to(upload_root)
                if file_path.exists() and file_path.is_file():
                    file_path.unlink()
                    deleted += 1
            except Exception as exc:
                errors.append(
                    {
                        "artifact_id": ref.artifact_id,
                        "storage_path": ref.storage_path,
                        "error": str(exc),
                    }
                )
        return {"deleted": deleted, "errors": errors}

    async def _count_ticket_events_archive(self, ticket_ids: list[str]) -> int:
        stmt = text("SELECT count(*) FROM ticket_events_archive WHERE ticket_id IN :ticket_ids").bindparams(
            bindparam("ticket_ids", expanding=True)
        )
        result = await self.session.scalar(stmt, {"ticket_ids": ticket_ids})
        return int(result or 0)

    async def _delete_ticket_events_archive(self, ticket_ids: list[str]) -> None:
        stmt = text("DELETE FROM ticket_events_archive WHERE ticket_id IN :ticket_ids").bindparams(
            bindparam("ticket_ids", expanding=True)
        )
        await self.session.execute(stmt, {"ticket_ids": ticket_ids})

    async def _count_ticket_admin_audit(self, ticket_ids: list[str]) -> int:
        result = await self.session.scalar(
            select(func.count())
            .select_from(TicketAdminAudit)
            .where(TicketAdminAudit.entity_type == "ticket", TicketAdminAudit.entity_id.in_(ticket_ids))
        )
        return int(result or 0)

    async def _count_ticket_admin_audit_archive(self, ticket_ids: list[str]) -> int:
        stmt = text(
            "SELECT count(*) FROM ticket_admin_audit_archive "
            "WHERE entity_type = 'ticket' AND entity_id IN :ticket_ids"
        ).bindparams(bindparam("ticket_ids", expanding=True))
        result = await self.session.scalar(stmt, {"ticket_ids": ticket_ids})
        return int(result or 0)

    async def _delete_ticket_admin_audit_archive(self, ticket_ids: list[str]) -> None:
        stmt = text(
            "DELETE FROM ticket_admin_audit_archive "
            "WHERE entity_type = 'ticket' AND entity_id IN :ticket_ids"
        ).bindparams(bindparam("ticket_ids", expanding=True))
        await self.session.execute(stmt, {"ticket_ids": ticket_ids})
