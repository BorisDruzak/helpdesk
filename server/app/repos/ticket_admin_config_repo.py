"""
Stage 9: Репозиторий для admin-config: очереди, routing rules, SLA policies.
CRUD с учётом include_inactive/include_disabled.
"""
from typing import List, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    TicketQueue,
    TicketQueueMember,
    TicketQueueOlaTarget,
    TicketRoutingRule,
    TicketSlaPolicy,
    TicketSlaTarget,
    TicketPriorityMatrix,
    TicketBusinessCalendar,
    Ticket,
    TicketResolutionCode,
)


class TicketAdminConfigRepo:
    """CRUD для ticket queues, routing rules, SLA policies."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Queues ---
    async def list_queues(self, include_inactive: bool = False) -> List[TicketQueue]:
        stmt = select(TicketQueue)
        if not include_inactive:
            stmt = stmt.where(TicketQueue.is_active.is_(True))
        stmt = stmt.order_by(TicketQueue.code.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_queue(self, queue_id: int) -> Optional[TicketQueue]:
        result = await self.session.execute(
            select(TicketQueue).where(TicketQueue.id == queue_id)
        )
        return result.scalar_one_or_none()

    async def get_queue_by_code(self, code: str) -> Optional[TicketQueue]:
        result = await self.session.execute(
            select(TicketQueue).where(TicketQueue.code == code)
        )
        return result.scalar_one_or_none()

    async def create_queue(
        self,
        code: str,
        name: str,
        is_triage: bool = False,
        auto_assign_enabled: bool = True,
    ) -> TicketQueue:
        q = TicketQueue(
            code=code,
            name=name,
            is_triage=is_triage,
            is_active=True,
            auto_assign_enabled=auto_assign_enabled,
        )
        self.session.add(q)
        await self.session.flush()
        return q

    async def update_queue(
        self, queue_id: int, **kwargs
    ) -> Optional[TicketQueue]:
        q = await self.get_queue(queue_id)
        if not q:
            return None
        for key in ("code", "name", "is_triage", "is_active", "auto_assign_enabled"):
            if key in kwargs:
                setattr(q, key, kwargs[key])
        await self.session.flush()
        return q

    async def count_open_tickets_in_queue(self, queue_id: int) -> int:
        """Количество open тикетов в очереди (status не resolved/closed)."""
        stmt = select(func.count(Ticket.ticket_id)).where(
            and_(
                Ticket.queue_id == queue_id,
                Ticket.status.notin_(["resolved", "closed"]),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_enabled_rules_targeting_queue(self, queue_id: int) -> int:
        """Количество enabled routing rules с target_queue_id."""
        stmt = select(func.count(TicketRoutingRule.id)).where(
            and_(
                TicketRoutingRule.target_queue_id == queue_id,
                TicketRoutingRule.enabled.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # --- Queue members ---
    async def list_queue_members(self, queue_id: int) -> List[TicketQueueMember]:
        result = await self.session.execute(
            select(TicketQueueMember).where(TicketQueueMember.queue_id == queue_id)
        )
        return list(result.scalars().all())

    async def get_queue_member(
        self, queue_id: int, actor_id: str
    ) -> Optional[TicketQueueMember]:
        result = await self.session.execute(
            select(TicketQueueMember).where(
                and_(
                    TicketQueueMember.queue_id == queue_id,
                    TicketQueueMember.actor_id == actor_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def put_queue_member(
        self, queue_id: int, actor_id: str, role_in_queue: Optional[str] = None
    ) -> TicketQueueMember:
        m = await self.get_queue_member(queue_id, actor_id)
        if m:
            m.role_in_queue = role_in_queue
            await self.session.flush()
            return m
        m = TicketQueueMember(queue_id=queue_id, actor_id=actor_id, role_in_queue=role_in_queue)
        self.session.add(m)
        await self.session.flush()
        return m

    async def delete_queue_member(self, queue_id: int, actor_id: str) -> bool:
        m = await self.get_queue_member(queue_id, actor_id)
        if not m:
            return False
        await self.session.delete(m)
        await self.session.flush()
        return True

    # --- Resolution codes ---
    async def list_resolution_codes(self, include_inactive: bool = False) -> List[TicketResolutionCode]:
        stmt = select(TicketResolutionCode).order_by(TicketResolutionCode.sort_order.asc(), TicketResolutionCode.code.asc())
        if not include_inactive:
            stmt = stmt.where(TicketResolutionCode.is_active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_resolution_code(self, code: str) -> Optional[TicketResolutionCode]:
        result = await self.session.execute(
            select(TicketResolutionCode).where(TicketResolutionCode.code == code)
        )
        return result.scalar_one_or_none()

    async def create_resolution_code(
        self,
        code: str,
        name: str,
        *,
        is_active: bool = True,
        sort_order: int = 0,
    ) -> TicketResolutionCode:
        item = TicketResolutionCode(
            code=code,
            name=name,
            is_active=is_active,
            sort_order=sort_order,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def update_resolution_code(self, code: str, **kwargs) -> Optional[TicketResolutionCode]:
        item = await self.get_resolution_code(code)
        if not item:
            return None
        for key in ("name", "is_active", "sort_order"):
            if key in kwargs:
                setattr(item, key, kwargs[key])
        await self.session.flush()
        return item

    async def delete_resolution_code(self, code: str) -> bool:
        item = await self.get_resolution_code(code)
        if not item:
            return False
        await self.session.delete(item)
        await self.session.flush()
        return True

    async def count_tickets_with_resolution_code(self, code: str) -> int:
        stmt = select(func.count(Ticket.ticket_id)).where(Ticket.resolution_code == code)
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    # --- Routing rules ---
    async def list_routing_rules(
        self, include_disabled: bool = False
    ) -> List[TicketRoutingRule]:
        stmt = select(TicketRoutingRule)
        if not include_disabled:
            stmt = stmt.where(TicketRoutingRule.enabled.is_(True))
        stmt = stmt.order_by(TicketRoutingRule.priority_order.asc(), TicketRoutingRule.id.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_routing_rule(self, rule_id: int) -> Optional[TicketRoutingRule]:
        result = await self.session.execute(
            select(TicketRoutingRule).where(TicketRoutingRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def create_routing_rule(
        self,
        target_queue_id: int,
        priority_order: int = 0,
        condition_json: Optional[dict] = None,
        enabled: bool = True,
    ) -> TicketRoutingRule:
        r = TicketRoutingRule(
            target_queue_id=target_queue_id,
            priority_order=priority_order,
            condition_json=condition_json,
            enabled=enabled,
        )
        self.session.add(r)
        await self.session.flush()
        return r

    async def update_routing_rule(
        self, rule_id: int, **kwargs
    ) -> Optional[TicketRoutingRule]:
        r = await self.get_routing_rule(rule_id)
        if not r:
            return None
        for key in ("enabled", "priority_order", "condition_json", "target_queue_id"):
            if key in kwargs:
                setattr(r, key, kwargs[key])
        await self.session.flush()
        return r

    # --- SLA policies ---
    async def list_sla_policies(
        self, include_inactive: bool = False
    ) -> List[TicketSlaPolicy]:
        stmt = select(TicketSlaPolicy)
        if not include_inactive:
            stmt = stmt.where(TicketSlaPolicy.is_active.is_(True))
        stmt = stmt.order_by(TicketSlaPolicy.id.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_sla_policy(self, policy_id: int) -> Optional[TicketSlaPolicy]:
        result = await self.session.execute(
            select(TicketSlaPolicy).where(TicketSlaPolicy.id == policy_id)
        )
        return result.scalar_one_or_none()

    async def get_default_sla_policy(self) -> Optional[TicketSlaPolicy]:
        result = await self.session.execute(
            select(TicketSlaPolicy).where(
                and_(
                    TicketSlaPolicy.is_default.is_(True),
                    TicketSlaPolicy.is_active.is_(True),
                )
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def create_sla_policy(
        self,
        name: str,
        timezone: str = "UTC",
        business_hours_json: Optional[dict] = None,
        calendar_id: Optional[int] = None,
        is_default: bool = False,
    ) -> TicketSlaPolicy:
        p = TicketSlaPolicy(
            name=name,
            timezone=timezone,
            business_hours_json=business_hours_json,
            calendar_id=calendar_id,
            is_default=is_default,
            is_active=True,
        )
        self.session.add(p)
        await self.session.flush()
        return p

    async def update_sla_policy(
        self, policy_id: int, **kwargs
    ) -> Optional[TicketSlaPolicy]:
        p = await self.get_sla_policy(policy_id)
        if not p:
            return None
        for key in ("name", "timezone", "business_hours_json", "calendar_id", "is_default", "is_active"):
            if key in kwargs:
                setattr(p, key, kwargs[key])
        await self.session.flush()
        return p

    async def count_open_tickets_with_policy(self, policy_id: int) -> int:
        stmt = select(func.count(Ticket.ticket_id)).where(
            and_(
                Ticket.sla_policy_id == policy_id,
                Ticket.status.notin_(["resolved", "closed"]),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # --- SLA targets ---
    async def get_sla_targets(self, policy_id: int) -> List[TicketSlaTarget]:
        result = await self.session.execute(
            select(TicketSlaTarget).where(TicketSlaTarget.policy_id == policy_id)
        )
        return list(result.scalars().all())

    async def replace_sla_targets(
        self, policy_id: int, targets: List[dict]
    ) -> List[TicketSlaTarget]:
        """targets: [{"priority":"P1","first_response_min":15,"resolution_min":240}, ...]"""
        # Delete existing
        await self.session.execute(
            TicketSlaTarget.__table__.delete().where(
                TicketSlaTarget.policy_id == policy_id
            )
        )
        # Insert new
        out = []
        for t in targets:
            row = TicketSlaTarget(
                policy_id=policy_id,
                priority=t["priority"],
                first_response_min=t["first_response_min"],
                resolution_min=t["resolution_min"],
            )
            self.session.add(row)
            out.append(row)
        await self.session.flush()
        return out

    # --- Priority matrix ---
    async def get_priority_matrix(self, policy_id: int) -> List[TicketPriorityMatrix]:
        result = await self.session.execute(
            select(TicketPriorityMatrix).where(
                TicketPriorityMatrix.policy_id == policy_id
            )
        )
        return list(result.scalars().all())

    async def replace_priority_matrix(
        self, policy_id: int, matrix: List[dict]
    ) -> List[TicketPriorityMatrix]:
        """matrix: [{"impact":1,"urgency":1,"priority":"P4"}, ...]"""
        await self.session.execute(
            TicketPriorityMatrix.__table__.delete().where(
                TicketPriorityMatrix.policy_id == policy_id
            )
        )
        out = []
        for m in matrix:
            row = TicketPriorityMatrix(
                policy_id=policy_id,
                impact=m["impact"],
                urgency=m["urgency"],
                priority=m["priority"],
            )
            self.session.add(row)
            out.append(row)
        await self.session.flush()
        return out

    # --- Stage 11: Calendars ---
    async def list_calendars(
        self, include_inactive: bool = False
    ) -> List[TicketBusinessCalendar]:
        stmt = select(TicketBusinessCalendar).order_by(TicketBusinessCalendar.code.asc())
        if not include_inactive:
            stmt = stmt.where(TicketBusinessCalendar.is_active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_calendar(self, calendar_id: int) -> Optional[TicketBusinessCalendar]:
        result = await self.session.execute(
            select(TicketBusinessCalendar).where(TicketBusinessCalendar.id == calendar_id)
        )
        return result.scalar_one_or_none()

    async def get_calendar_by_code(self, code: str) -> Optional[TicketBusinessCalendar]:
        result = await self.session.execute(
            select(TicketBusinessCalendar).where(TicketBusinessCalendar.code == code)
        )
        return result.scalar_one_or_none()

    async def create_calendar(
        self,
        code: str,
        name: str,
        timezone: str = "UTC",
        weekly_hours_json: Optional[dict] = None,
        holidays_json: Optional[dict] = None,
    ) -> TicketBusinessCalendar:
        c = TicketBusinessCalendar(
            code=code,
            name=name,
            timezone=timezone,
            weekly_hours_json=weekly_hours_json,
            holidays_json=holidays_json,
            is_active=True,
        )
        self.session.add(c)
        await self.session.flush()
        return c

    async def update_calendar(
        self, calendar_id: int, **kwargs
    ) -> Optional[TicketBusinessCalendar]:
        c = await self.get_calendar(calendar_id)
        if not c:
            return None
        for key in ("code", "name", "timezone", "weekly_hours_json", "holidays_json", "is_active"):
            if key in kwargs:
                setattr(c, key, kwargs[key])
        await self.session.flush()
        return c

    # --- Stage 11: OLA targets ---
    async def list_ola_targets(self, queue_id: int) -> List[TicketQueueOlaTarget]:
        result = await self.session.execute(
            select(TicketQueueOlaTarget).where(TicketQueueOlaTarget.queue_id == queue_id)
        )
        return list(result.scalars().all())

    async def replace_ola_targets(
        self, queue_id: int, targets: List[dict]
    ) -> List[TicketQueueOlaTarget]:
        """targets: [{"priority":"P1","ack_min":5,"processing_min":60}, ...]"""
        await self.session.execute(
            TicketQueueOlaTarget.__table__.delete().where(
                TicketQueueOlaTarget.queue_id == queue_id
            )
        )
        out = []
        for t in targets:
            row = TicketQueueOlaTarget(
                queue_id=queue_id,
                priority=t["priority"],
                ack_min=t["ack_min"],
                processing_min=t["processing_min"],
            )
            self.session.add(row)
            out.append(row)
        await self.session.flush()
        return out
