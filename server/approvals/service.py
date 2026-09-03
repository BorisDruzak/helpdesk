from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Change, ChangeApproval, Operation, Ticket, TicketApproval
from web_api.dto.approvals import (
    ApprovalConsentAction,
    ApprovalConsentBlocking,
    ApprovalConsentCenterPayload,
    ApprovalConsentContext,
    ApprovalConsentFilters,
    ApprovalConsentItem,
    ApprovalConsentSection,
    ApprovalConsentSummary,
)


PENDING_STATUSES = {"pending", "requested", "waiting", "waiting_consent"}
HIGH_RISKS = {"high", "critical"}


@dataclass(frozen=True)
class ApprovalConsentQuery:
    scope: str = "team"
    kind: str | None = None
    status: str | None = "pending"
    risk: str | None = None
    object_type: str | None = None
    queue: str | None = None
    assignee: str | None = None
    due_window_hours: int | None = None
    limit: int = 50
    offset: int = 0


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _normalize_status(value: str | None) -> str:
    status = (value or "unknown").strip().lower()
    if status in {"requested", "waiting", "waiting_consent"}:
        return "pending"
    if status in {"approved", "rejected", "expired", "canceled", "pending"}:
        return status
    return "unknown"


def _risk_from_priority(priority: str | None) -> str:
    value = (priority or "").strip().lower()
    if value in {"p1", "critical", "crit"}:
        return "critical"
    if value in {"p2", "high"}:
        return "high"
    if value in {"p3", "medium", "normal"}:
        return "medium"
    if value in {"p4", "low"}:
        return "low"
    return "unknown"


def _risk_from_change(value: str | None) -> str:
    risk = (value or "").strip().lower()
    if risk in {"low", "medium", "high", "critical"}:
        return risk
    return "unknown"


def _ticket_title(ticket: Ticket | None) -> str:
    if ticket is None:
        return "Тикет ожидает согласования"
    return ticket.title or ticket.ticket_code or ticket.ticket_id


def _ticket_queue(ticket: Ticket | None) -> str | None:
    if ticket is None or ticket.queue_id is None:
        return None
    return str(ticket.queue_id)


def _kind_matches(kind_filter: str | None, item: ApprovalConsentItem) -> bool:
    if not kind_filter:
        return True
    normalized = kind_filter.strip()
    if normalized == "pending_approval":
        return item.kind in {"ticket_approval", "change_approval", "closure_approval", "policy_override"}
    if normalized == "pending_consent":
        return item.kind == "risky_tool_consent"
    return item.kind == normalized


def _status_matches(status_filter: str | None, item: ApprovalConsentItem) -> bool:
    if not status_filter or status_filter == "pending":
        return item.status == "pending"
    if status_filter == "all":
        return True
    return item.status == status_filter


def _is_overdue(item: ApprovalConsentItem, now: datetime) -> bool:
    if not item.due_at:
        return False
    try:
        due_at = datetime.fromisoformat(item.due_at)
    except ValueError:
        return False
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    return due_at <= now


class ApprovalConsentCenterService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def build_payload(self, *, auth_context, query: ApprovalConsentQuery) -> ApprovalConsentCenterPayload:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        scope = self._resolve_scope(auth_context, query.scope)
        items: list[ApprovalConsentItem] = []
        items.extend(await self._ticket_approvals())
        items.extend(await self._change_approvals())
        items.extend(await self._risky_tool_consents())

        filtered = [
            item
            for item in items
            if _kind_matches(query.kind, item)
            and _status_matches(query.status, item)
            and (query.risk is None or item.risk == query.risk)
            and (query.object_type is None or item.object_type == query.object_type)
            and (query.queue is None or item.context.queue == query.queue)
            and (query.assignee is None or item.context.assignee == query.assignee)
            and self._scope_matches(scope, auth_context.actor_id, item)
        ]
        filtered.sort(key=lambda item: self._sort_key(item, now))
        paged = filtered[query.offset : query.offset + query.limit]

        return ApprovalConsentCenterPayload(
            generated_at=now.isoformat(),
            scope=scope,
            filters=ApprovalConsentFilters(
                kind=query.kind,
                status=query.status,
                risk=query.risk,
                object_type=query.object_type,
                queue=query.queue,
                assignee=query.assignee,
                due_window_hours=query.due_window_hours,
                limit=query.limit,
                offset=query.offset,
            ),
            summary=self._summary(filtered, now),
            sections=self._sections(filtered, now, auth_context.actor_id),
            items=paged,
        )

    def _resolve_scope(self, auth_context, requested_scope: str) -> str:
        requested = requested_scope if requested_scope in {"my", "team", "all"} else "team"
        if requested == "all" and auth_context.actor_role != "admin":
            return "team"
        return requested

    def _scope_matches(self, scope: str, actor_id: str, item: ApprovalConsentItem) -> bool:
        if scope != "my":
            return True
        return actor_id in {
            item.approver,
            item.requested_by,
            item.context.assignee,
        }

    def _sort_key(self, item: ApprovalConsentItem, now: datetime) -> tuple[int, int, str]:
        overdue_rank = 0 if _is_overdue(item, now) else 1
        risk_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(item.risk, 4)
        return (overdue_rank, risk_rank, item.due_at or item.created_at or "")

    async def _ticket_approvals(self) -> list[ApprovalConsentItem]:
        rows = (
            await self._session.execute(
                select(TicketApproval, Ticket)
                .join(Ticket, Ticket.ticket_id == TicketApproval.ticket_id)
                .order_by(TicketApproval.requested_at.desc())
                .limit(500)
            )
        ).all()
        items: list[ApprovalConsentItem] = []
        for approval, ticket in rows:
            is_closure = approval.approval_type in {"closure", "closure_approval", "requester_confirmation", "qa_closure"}
            kind = "closure_approval" if is_closure else "ticket_approval"
            reason = approval.reason or (
                "Закрытие тикета ждёт подтверждения" if is_closure else "Тикет ждёт согласования"
            )
            items.append(
                ApprovalConsentItem(
                    id=f"{kind}:{approval.id}",
                    kind=kind,
                    status=_normalize_status(approval.status),
                    title=_ticket_title(ticket),
                    reason=reason,
                    object_type="closure" if is_closure else "ticket",
                    object_id=ticket.ticket_id,
                    ticket_id=ticket.ticket_id,
                    ticket_number=ticket.ticket_code,
                    device_id=ticket.device_id,
                    requester_name=ticket.requester_id,
                    requested_by=approval.requested_by,
                    approver=approval.approver_id,
                    risk=_risk_from_priority(ticket.priority),
                    created_at=_iso(approval.requested_at),
                    updated_at=_iso(approval.decided_at or approval.requested_at),
                    blocking=ApprovalConsentBlocking(
                        blocks_ticket_progress=True,
                        blocks_sla=bool(ticket.resolution_due_at or ticket.first_response_due_at),
                        blocks_closure=is_closure,
                    ),
                    context=ApprovalConsentContext(
                        queue=_ticket_queue(ticket),
                        assignee=ticket.assignee_id,
                        service_code=ticket.service_code,
                        offering_code=ticket.offering_code,
                        closure_blocker=reason if is_closure else None,
                    ),
                    actions=[
                        ApprovalConsentAction(
                            key="open_ticket",
                            label="Открыть тикет",
                            href=f"/app/tickets/{ticket.ticket_id}",
                            enabled=True,
                        )
                    ],
                )
            )
        return items

    async def _change_approvals(self) -> list[ApprovalConsentItem]:
        rows = (
            await self._session.execute(
                select(ChangeApproval, Change)
                .join(Change, Change.change_id == ChangeApproval.change_id)
                .order_by(ChangeApproval.requested_at.desc())
                .limit(500)
            )
        ).all()
        items: list[ApprovalConsentItem] = []
        for approval, change in rows:
            window = None
            if change.planned_start_at and change.planned_end_at:
                window = f"{_iso(change.planned_start_at)} — {_iso(change.planned_end_at)}"
            items.append(
                ApprovalConsentItem(
                    id=f"change_approval:{approval.approval_id}",
                    kind="change_approval",
                    status=_normalize_status(approval.status),
                    title=change.title,
                    reason=f"Изменение ждёт согласования: {approval.approval_stage}",
                    object_type="change",
                    object_id=change.change_id,
                    change_id=change.change_id,
                    change_number=change.change_key,
                    requested_by=change.requested_by_actor_id,
                    approver=approval.approver_actor_id,
                    approver_group=approval.approver_group or approval.approver_role,
                    risk=_risk_from_change(change.risk_level),
                    due_at=_iso(approval.due_at),
                    created_at=_iso(approval.requested_at),
                    updated_at=_iso(approval.decided_at or approval.requested_at),
                    blocking=ApprovalConsentBlocking(blocks_change=True, blocks_sla=bool(approval.due_at)),
                    context=ApprovalConsentContext(
                        queue=str(change.queue_id) if change.queue_id is not None else None,
                        assignee=change.assignee_actor_id,
                        service_code=change.service_code,
                        offering_code=change.offering_code,
                        change_window=window,
                    ),
                    actions=[
                        ApprovalConsentAction(
                            key="open_change",
                            label="Открыть изменение",
                            href=f"/app/admin/changes?change={change.change_id}",
                            enabled=True,
                        )
                    ],
                )
            )
        return items

    async def _risky_tool_consents(self) -> list[ApprovalConsentItem]:
        rows = (
            await self._session.execute(
                select(Operation, Ticket)
                .outerjoin(Ticket, Ticket.ticket_id == Operation.ticket_id)
                .where(Operation.status == "waiting_consent")
                .order_by(Operation.queued_at.desc())
                .limit(500)
            )
        ).all()
        items: list[ApprovalConsentItem] = []
        for operation, ticket in rows:
            tool_name = operation.tool_name or operation.command_name or operation.kind
            actions = []
            if ticket is not None:
                actions.append(
                    ApprovalConsentAction(
                        key="open_ticket",
                        label="Открыть тикет",
                        href=f"/app/tickets/{ticket.ticket_id}",
                        enabled=True,
                    )
                )
            actions.append(
                ApprovalConsentAction(
                    key="open_device_operations",
                    label="Открыть устройство",
                    href=f"/app/admin/device?device={operation.device_id}",
                    enabled=True,
                )
            )
            items.append(
                ApprovalConsentItem(
                    id=f"risky_tool_consent:{operation.operation_id}",
                    kind="risky_tool_consent",
                    status="pending",
                    title=f"Согласие на рискованную команду: {tool_name}",
                    reason="Операция ожидает согласия перед выполнением",
                    object_type="operation",
                    object_id=operation.operation_id,
                    ticket_id=ticket.ticket_id if ticket else operation.ticket_id,
                    ticket_number=ticket.ticket_code if ticket else None,
                    operation_id=operation.operation_id,
                    device_id=operation.device_id,
                    requester_name=ticket.requester_id if ticket else None,
                    requested_by=None,
                    risk=_risk_from_priority(ticket.priority if ticket else None),
                    due_at=_iso(operation.deadline_at),
                    created_at=_iso(operation.queued_at),
                    updated_at=_iso(operation.started_at or operation.queued_at),
                    blocking=ApprovalConsentBlocking(
                        blocks_ticket_progress=ticket is not None,
                        blocks_operation=True,
                    ),
                    context=ApprovalConsentContext(
                        queue=_ticket_queue(ticket),
                        assignee=ticket.assignee_id if ticket else None,
                        service_code=ticket.service_code if ticket else None,
                        offering_code=ticket.offering_code if ticket else None,
                        tool_name=tool_name,
                    ),
                    actions=actions,
                )
            )
        return items

    def _summary(self, items: list[ApprovalConsentItem], now: datetime) -> ApprovalConsentSummary:
        return ApprovalConsentSummary(
            total_count=len(items),
            pending_count=sum(1 for item in items if item.status == "pending"),
            overdue_count=sum(1 for item in items if _is_overdue(item, now)),
            high_risk_count=sum(1 for item in items if item.risk in HIGH_RISKS),
            waiting_user_count=sum(1 for item in items if item.kind == "risky_tool_consent"),
            waiting_approver_count=sum(1 for item in items if item.kind in {"ticket_approval", "change_approval", "closure_approval", "policy_override"}),
            blocking_sla_count=sum(1 for item in items if item.blocking.blocks_sla),
            ticket_approvals_count=sum(1 for item in items if item.kind == "ticket_approval"),
            change_approvals_count=sum(1 for item in items if item.kind == "change_approval"),
            risky_tool_consents_count=sum(1 for item in items if item.kind == "risky_tool_consent"),
            remote_assist_consents_count=0,
            closure_approvals_count=sum(1 for item in items if item.kind == "closure_approval"),
            policy_overrides_count=sum(1 for item in items if item.kind == "policy_override"),
        )

    def _sections(self, items: list[ApprovalConsentItem], now: datetime, actor_id: str) -> list[ApprovalConsentSection]:
        specs = [
            ("waiting_me", "Ждёт меня", "Согласования, где текущий оператор указан исполнителем или согласующим.", lambda i: actor_id in {i.approver, i.context.assignee}, "warning"),
            ("waiting_user", "Ждёт пользователя", "Consent-запросы, которые должен подтвердить пользователь.", lambda i: i.kind == "risky_tool_consent", "warning"),
            ("overdue", "Просрочено", "Срок согласования или consent-запроса уже истёк.", lambda i: _is_overdue(i, now), "critical"),
            ("high_risk", "Высокий риск", "High/critical согласования и consent-запросы.", lambda i: i.risk in HIGH_RISKS, "critical"),
            ("ticket_approvals", "Тикеты", "Согласования в тикетном workflow.", lambda i: i.kind == "ticket_approval", "info"),
            ("change_approvals", "Изменения", "Согласования Change Enablement.", lambda i: i.kind == "change_approval", "info"),
            ("risky_tool_consents", "Рискованные команды", "Операции, ожидающие consent перед запуском.", lambda i: i.kind == "risky_tool_consent", "warning"),
            ("closure_approvals", "Закрытие", "Approval-like блокеры закрытия тикета.", lambda i: i.kind == "closure_approval", "warning"),
            ("policy_overrides", "Policy overrides", "Pending override-запросы политик, если источник существует.", lambda i: i.kind == "policy_override", "info"),
        ]
        sections = []
        for key, title, description, predicate, default_severity in specs:
            count = sum(1 for item in items if predicate(item))
            severity = "critical" if key == "overdue" and count else default_severity
            sections.append(
                ApprovalConsentSection(
                    key=key,
                    title=title,
                    description=description,
                    count=count,
                    severity=severity,
                    href=f"/app/support/approvals?kind={key}",
                )
            )
        return sections
