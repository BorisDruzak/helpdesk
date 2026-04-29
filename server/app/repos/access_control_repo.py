from __future__ import annotations

from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    AccessAudit,
    AccessGroup,
    AccessGroupMember,
    AccessGroupPermission,
    AccessGroupQueueMember,
    TicketQueue,
)
from shared.redaction import redact_sensitive_payload


class AccessControlRepo:
    """Repository for RBAC access groups, grants and audit."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_groups(self, include_inactive: bool = True) -> list[AccessGroup]:
        stmt = select(AccessGroup).order_by(AccessGroup.code.asc())
        if not include_inactive:
            stmt = stmt.where(AccessGroup.is_active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_group(self, group_id: int) -> AccessGroup | None:
        result = await self.session.execute(select(AccessGroup).where(AccessGroup.id == group_id))
        return result.scalar_one_or_none()

    async def get_group_by_code(self, code: str) -> AccessGroup | None:
        result = await self.session.execute(select(AccessGroup).where(AccessGroup.code == code))
        return result.scalar_one_or_none()

    async def create_group(
        self,
        *,
        code: str,
        name: str,
        description: str | None,
        is_active: bool,
        actor_id: str,
        actor_role: str,
    ) -> AccessGroup:
        group = AccessGroup(
            code=code,
            name=name,
            description=description,
            is_active=is_active,
        )
        self.session.add(group)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise ValueError("Access group already exists") from exc
        await self.add_audit(
            entity_type="access_group",
            entity_id=str(group.id),
            action="group_created",
            actor_id=actor_id,
            actor_role=actor_role,
            after_json=self.group_base_dict(group),
        )
        return group

    async def update_group(
        self,
        group_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
        actor_id: str,
        actor_role: str,
    ) -> AccessGroup | None:
        group = await self.get_group(group_id)
        if group is None:
            return None
        before = self.group_base_dict(group)
        if name is not None:
            group.name = name
        if description is not None:
            group.description = description
        if is_active is not None:
            group.is_active = is_active
        await self.session.flush()
        await self.add_audit(
            entity_type="access_group",
            entity_id=str(group.id),
            action="group_updated",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=before,
            after_json=self.group_base_dict(group),
        )
        return group

    async def set_group_permissions(
        self,
        group_id: int,
        permissions: Iterable[str],
        *,
        actor_id: str,
        actor_role: str,
    ) -> list[str] | None:
        group = await self.get_group(group_id)
        if group is None:
            return None
        before = await self.list_group_permissions(group_id)
        normalized = sorted({str(item).strip() for item in permissions if str(item).strip()})
        await self.session.execute(delete(AccessGroupPermission).where(AccessGroupPermission.group_id == group_id))
        for permission in normalized:
            self.session.add(AccessGroupPermission(group_id=group_id, permission_code=permission))
        await self.session.flush()
        await self.add_audit(
            entity_type="access_group",
            entity_id=str(group_id),
            action="group_permissions_updated",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json={"permissions": before},
            after_json={"permissions": normalized},
        )
        return normalized

    async def set_group_members(
        self,
        group_id: int,
        actor_ids: Iterable[str],
        *,
        actor_id: str,
        actor_role: str,
    ) -> list[str] | None:
        group = await self.get_group(group_id)
        if group is None:
            return None
        before = await self.list_group_members(group_id)
        normalized = sorted({str(item).strip() for item in actor_ids if str(item).strip()})
        await self.session.execute(delete(AccessGroupMember).where(AccessGroupMember.group_id == group_id))
        for member_actor_id in normalized:
            self.session.add(AccessGroupMember(group_id=group_id, actor_id=member_actor_id))
        await self.session.flush()
        await self.add_audit(
            entity_type="access_group",
            entity_id=str(group_id),
            action="group_members_updated",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json={"members": before},
            after_json={"members": normalized},
        )
        return normalized

    async def set_group_queues(
        self,
        group_id: int,
        queues: Iterable[dict],
        *,
        actor_id: str,
        actor_role: str,
    ) -> list[dict] | None:
        group = await self.get_group(group_id)
        if group is None:
            return None
        before = await self.list_group_queue_grants(group_id)
        normalized_by_queue: dict[int, str | None] = {}
        for item in queues:
            queue_id = int(item.get("queue_id") or 0)
            if queue_id <= 0:
                continue
            role_in_queue = item.get("role_in_queue")
            normalized_by_queue[queue_id] = str(role_in_queue).strip() if role_in_queue else None
        await self.session.execute(delete(AccessGroupQueueMember).where(AccessGroupQueueMember.group_id == group_id))
        for queue_id, role_in_queue in sorted(normalized_by_queue.items()):
            self.session.add(
                AccessGroupQueueMember(group_id=group_id, queue_id=queue_id, role_in_queue=role_in_queue)
            )
        await self.session.flush()
        after = await self.list_group_queue_grants(group_id)
        await self.add_audit(
            entity_type="access_group",
            entity_id=str(group_id),
            action="group_queues_updated",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json={"queues": before},
            after_json={"queues": after},
        )
        return after

    async def list_group_permissions(self, group_id: int) -> list[str]:
        result = await self.session.execute(
            select(AccessGroupPermission.permission_code)
            .where(AccessGroupPermission.group_id == group_id)
            .order_by(AccessGroupPermission.permission_code.asc())
        )
        return [str(item) for item in result.scalars().all()]

    async def list_group_members(self, group_id: int) -> list[str]:
        result = await self.session.execute(
            select(AccessGroupMember.actor_id)
            .where(AccessGroupMember.group_id == group_id)
            .order_by(AccessGroupMember.actor_id.asc())
        )
        return [str(item) for item in result.scalars().all()]

    async def list_group_queue_grants(self, group_id: int) -> list[dict]:
        result = await self.session.execute(
            select(
                TicketQueue.id,
                TicketQueue.code,
                TicketQueue.name,
                AccessGroupQueueMember.role_in_queue,
            )
            .join(AccessGroupQueueMember, AccessGroupQueueMember.queue_id == TicketQueue.id)
            .where(AccessGroupQueueMember.group_id == group_id)
            .order_by(TicketQueue.code.asc())
        )
        return [
            {
                "queue_id": int(row.id),
                "queue_code": str(row.code),
                "queue_name": str(row.name),
                "role_in_queue": row.role_in_queue,
            }
            for row in result.all()
        ]

    async def get_actor_group_codes(self, actor_id: str) -> list[str]:
        result = await self.session.execute(
            select(AccessGroup.code)
            .join(AccessGroupMember, AccessGroupMember.group_id == AccessGroup.id)
            .where(AccessGroupMember.actor_id == actor_id, AccessGroup.is_active.is_(True))
            .order_by(AccessGroup.code.asc())
        )
        return [str(item) for item in result.scalars().all()]

    async def get_actor_group_permissions(self, actor_id: str) -> list[str]:
        result = await self.session.execute(
            select(AccessGroupPermission.permission_code)
            .join(AccessGroup, AccessGroup.id == AccessGroupPermission.group_id)
            .join(AccessGroupMember, AccessGroupMember.group_id == AccessGroup.id)
            .where(AccessGroupMember.actor_id == actor_id, AccessGroup.is_active.is_(True))
            .order_by(AccessGroupPermission.permission_code.asc())
        )
        return sorted({str(item) for item in result.scalars().all()})

    async def get_actor_group_queues(self, actor_id: str) -> list[dict]:
        result = await self.session.execute(
            select(
                TicketQueue.id,
                TicketQueue.code,
                TicketQueue.name,
                AccessGroupQueueMember.role_in_queue,
            )
            .join(AccessGroupQueueMember, AccessGroupQueueMember.queue_id == TicketQueue.id)
            .join(AccessGroup, AccessGroup.id == AccessGroupQueueMember.group_id)
            .join(AccessGroupMember, AccessGroupMember.group_id == AccessGroup.id)
            .where(AccessGroupMember.actor_id == actor_id, AccessGroup.is_active.is_(True), TicketQueue.is_active.is_(True))
            .order_by(TicketQueue.code.asc())
        )
        seen: set[int] = set()
        queues: list[dict] = []
        for row in result.all():
            queue_id = int(row.id)
            if queue_id in seen:
                continue
            seen.add(queue_id)
            queues.append(
                {
                    "queue_id": queue_id,
                    "queue_code": str(row.code),
                    "queue_name": str(row.name),
                    "role_in_queue": row.role_in_queue,
                }
            )
        return queues

    async def add_audit(
        self,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str,
        actor_role: str,
        before_json: dict | None = None,
        after_json: dict | None = None,
    ) -> AccessAudit:
        audit = AccessAudit(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=redact_sensitive_payload(before_json or {}),
            after_json=redact_sensitive_payload(after_json or {}),
        )
        self.session.add(audit)
        await self.session.flush()
        return audit

    async def list_audit(self, limit: int = 100) -> list[AccessAudit]:
        result = await self.session.execute(
            select(AccessAudit).order_by(AccessAudit.created_at.desc(), AccessAudit.id.desc()).limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    def group_base_dict(group: AccessGroup) -> dict:
        return {
            "group_id": int(group.id),
            "code": group.code,
            "name": group.name,
            "description": group.description,
            "is_active": bool(group.is_active),
        }
