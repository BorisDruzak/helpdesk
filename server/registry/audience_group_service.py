from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import re
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AccessGroup,
    AccessGroupMember,
    RegistryAudienceGroup,
    RegistryAudienceGroupMember,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryPersonIdentity,
    UiUser,
)
from app.repos.registration_repo import normalize_identifier
from registry.admin_operations_service import RegistryAdminOperationsService


ALLOWED_MEMBER_TYPES = {"person", "department", "department_tree", "location", "access_group", "role", "service"}
ALLOWED_SOURCES = {"manual", "department_rule", "import", "system", "future_sync"}
BROAD_ROLES = {"user"}


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: Any, *, max_length: int = 500) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:max_length] if text else None


def _code(value: Any) -> str:
    text = re.sub(r"[^a-z0-9_-]+", "_", str(value or "").strip().lower()).strip("_")
    if not text or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", text):
        raise ValueError("code must start with a lowercase letter or digit and contain only lowercase letters, digits, _ or -")
    return text[:120]


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _warning(code: str, message: str, *, member: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if member:
        payload["member"] = member
    return payload


class RegistryAudienceService:
    """Admin-managed audience groups used for content targeting, not permissions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.events = RegistryAdminOperationsService(session)

    async def list_groups(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        stmt = select(RegistryAudienceGroup).order_by(RegistryAudienceGroup.code.asc())
        if not include_archived:
            stmt = stmt.where(RegistryAudienceGroup.status == "active")
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self.serialize_group(row) for row in rows]

    async def create_group(
        self,
        *,
        code: str,
        name: str,
        description: str | None = None,
        source: str = "manual",
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        clean_source = self._source(source)
        row = RegistryAudienceGroup(
            audience_group_id=_new_id(),
            code=_code(code),
            name=_text(name, max_length=300) or "",
            description=_text(description, max_length=1000),
            source=clean_source,
            status="active",
            created_by=actor_id,
            updated_by=actor_id,
        )
        if not row.name:
            raise ValueError("name is required")
        self.session.add(row)
        await self.session.flush()
        await self.events.append_event(
            object_type="audience_group",
            object_id=row.audience_group_id,
            event_type="audience_group_created",
            actor_id=actor_id,
            reason=reason,
            payload={"code": row.code, "name": row.name, "source": row.source},
        )
        return self.serialize_group(row)

    async def update_group(
        self,
        audience_group_id: str,
        *,
        fields: dict[str, Any],
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        row = await self._get_group(audience_group_id)
        before = self.serialize_group(row)
        if "code" in fields:
            row.code = _code(fields.get("code"))
        if "name" in fields:
            row.name = _text(fields.get("name"), max_length=300) or row.name
        if "description" in fields:
            row.description = _text(fields.get("description"), max_length=1000)
        if "source" in fields:
            row.source = self._source(fields.get("source"))
        row.updated_by = actor_id
        row.updated_at = _now()
        await self.session.flush()
        after = self.serialize_group(row)
        await self.events.append_event(
            object_type="audience_group",
            object_id=row.audience_group_id,
            event_type="audience_group_updated",
            actor_id=actor_id,
            reason=reason,
            payload={"before": before, "after": after},
        )
        return after

    async def archive_group(
        self,
        audience_group_id: str,
        *,
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        row = await self._get_group(audience_group_id)
        row.status = "archived"
        row.updated_by = actor_id
        row.updated_at = _now()
        await self.session.flush()
        await self.events.append_event(
            object_type="audience_group",
            object_id=row.audience_group_id,
            event_type="audience_group_archived",
            actor_id=actor_id,
            reason=reason,
            payload={"code": row.code},
        )
        return self.serialize_group(row)

    async def list_members(self, audience_group_id: str) -> list[dict[str, Any]]:
        await self._get_group(audience_group_id)
        rows = (
            await self.session.execute(
                select(RegistryAudienceGroupMember)
                .where(RegistryAudienceGroupMember.audience_group_id == str(audience_group_id))
                .order_by(
                    RegistryAudienceGroupMember.member_type.asc(),
                    RegistryAudienceGroupMember.member_id.asc(),
                    RegistryAudienceGroupMember.include_children.asc(),
                )
            )
        ).scalars().all()
        return [self.serialize_member(row) for row in rows]

    async def set_members(
        self,
        audience_group_id: str,
        members: list[dict[str, Any]],
        *,
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> list[dict[str, Any]]:
        group = await self._get_group(audience_group_id)
        normalized = self._normalize_members(members)
        before = await self.list_members(audience_group_id)
        await self.session.execute(
            delete(RegistryAudienceGroupMember).where(
                RegistryAudienceGroupMember.audience_group_id == group.audience_group_id
            )
        )
        for item in normalized:
            self.session.add(
                RegistryAudienceGroupMember(
                    membership_id=_new_id(),
                    audience_group_id=group.audience_group_id,
                    member_type=item["member_type"],
                    member_id=item["member_id"],
                    include_children=bool(item.get("include_children")),
                    source=item.get("source") or "manual",
                    metadata_json=item.get("metadata_json") or {},
                    created_by=actor_id,
                    updated_by=actor_id,
                )
            )
        group.updated_by = actor_id
        group.updated_at = _now()
        await self.session.flush()
        after = await self.list_members(audience_group_id)
        await self.events.append_event(
            object_type="audience_group",
            object_id=group.audience_group_id,
            event_type="audience_group_members_updated",
            actor_id=actor_id,
            reason=reason,
            payload={"before": before, "after": after},
        )
        return after

    async def preview_members(
        self,
        audience_group_id: str,
        *,
        members: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        group = await self._get_group(audience_group_id)
        member_payloads = self._normalize_members(members) if members is not None else await self.list_members(group.audience_group_id)
        people: dict[str, RegistryPerson] = {}
        warnings: list[dict[str, Any]] = []
        if not member_payloads:
            warnings.append(_warning("empty_group", "Audience group has no members."))
        for member in member_payloads:
            resolved, member_warnings = await self._resolve_member_people(member)
            warnings.extend(member_warnings)
            for person in resolved:
                people[person.person_id] = person
        people_payload = [self.serialize_person(person) for person in sorted(people.values(), key=lambda item: item.display_name.lower())]
        return {
            "audience_group_id": group.audience_group_id,
            "code": group.code,
            "member_count": len(member_payloads),
            "person_count": len(people_payload),
            "people": people_payload,
            "warnings": warnings,
        }

    async def _resolve_member_people(self, member: dict[str, Any]) -> tuple[list[RegistryPerson], list[dict[str, Any]]]:
        member_type = str(member.get("member_type") or "")
        member_id = str(member.get("member_id") or "").strip()
        if member_type == "person":
            person = await self.session.get(RegistryPerson, member_id)
            if person is None or person.status != "active":
                return [], [_warning("unknown_person", "Referenced person was not found or is not active.", member=member)]
            return [person], []
        if member_type in {"department", "department_tree"}:
            return await self._resolve_department_member(member, include_tree=member_type == "department_tree" or bool(member.get("include_children")))
        if member_type == "location":
            location = await self.session.get(RegistryLocation, member_id)
            if location is None:
                return [], [_warning("unknown_location", "Referenced location was not found.", member=member)]
            if location.status != "active":
                return [], [_warning("archived_location", "Referenced location is archived.", member=member)]
            result = await self.session.execute(
                select(RegistryPerson).where(RegistryPerson.location_id == location.location_id, RegistryPerson.status == "active")
            )
            return list(result.scalars().all()), []
        if member_type == "access_group":
            return await self._resolve_access_group_member(member)
        if member_type == "role":
            return await self._resolve_role_member(member)
        if member_type == "service":
            return [], [_warning("service_member_not_expandable", "Service audience expansion is reserved for Knowledge service context.", member=member)]
        return [], [_warning("unsupported_member_type", "Unsupported audience member type.", member=member)]

    async def _resolve_department_member(
        self,
        member: dict[str, Any],
        *,
        include_tree: bool,
    ) -> tuple[list[RegistryPerson], list[dict[str, Any]]]:
        department_id = str(member.get("member_id") or "").strip()
        department = await self.session.get(RegistryDepartment, department_id)
        if department is None:
            return [], [_warning("unknown_department", "Referenced department was not found.", member=member)]
        if department.status != "active":
            return [], [_warning("archived_department", "Referenced department is archived.", member=member)]
        department_ids = {department.department_id}
        if include_tree:
            department_ids.update(await self._department_descendants(department.department_id))
        result = await self.session.execute(
            select(RegistryPerson).where(RegistryPerson.department_id.in_(sorted(department_ids)), RegistryPerson.status == "active")
        )
        return list(result.scalars().all()), []

    async def _department_descendants(self, department_id: str) -> set[str]:
        rows = (
            await self.session.execute(
                select(RegistryDepartment.department_id, RegistryDepartment.parent_department_id).where(
                    RegistryDepartment.status == "active"
                )
            )
        ).all()
        children: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            if row.parent_department_id:
                children[str(row.parent_department_id)].append(str(row.department_id))
        result: set[str] = set()
        stack = list(children.get(str(department_id), []))
        while stack:
            current = stack.pop()
            if current in result:
                continue
            result.add(current)
            stack.extend(children.get(current, []))
        return result

    async def _resolve_access_group_member(self, member: dict[str, Any]) -> tuple[list[RegistryPerson], list[dict[str, Any]]]:
        code = str(member.get("member_id") or "").strip()
        group = (
            await self.session.execute(select(AccessGroup).where(AccessGroup.code == code, AccessGroup.is_active.is_(True)).limit(1))
        ).scalar_one_or_none()
        if group is None:
            return [], [_warning("unknown_access_group", "Referenced access group was not found or inactive.", member=member)]
        actor_ids = (
            await self.session.execute(
                select(AccessGroupMember.actor_id).where(AccessGroupMember.group_id == group.id).order_by(AccessGroupMember.actor_id.asc())
            )
        ).scalars().all()
        people: list[RegistryPerson] = []
        warnings: list[dict[str, Any]] = []
        for actor_id in actor_ids:
            person = await self._person_for_actor(str(actor_id))
            if person is None:
                warnings.append(_warning("unlinked_access_group_actor", "Access group actor is not linked to a registry person.", member={**member, "actor_id": str(actor_id)}))
            else:
                people.append(person)
        return people, warnings

    async def _resolve_role_member(self, member: dict[str, Any]) -> tuple[list[RegistryPerson], list[dict[str, Any]]]:
        role = str(member.get("member_id") or "").strip().lower()
        warnings: list[dict[str, Any]] = []
        if role in BROAD_ROLES:
            warnings.append(_warning("broad_role", "Broad role audience should be reviewed before use.", member=member))
        if role not in {"admin", "support", "auditor", "user"}:
            return [], [*warnings, _warning("unknown_role", "Referenced role is not supported.", member=member)]
        actor_ids = (
            await self.session.execute(
                select(UiUser.user_login).where(UiUser.actor_role == role, UiUser.is_active.is_(True)).order_by(func.lower(UiUser.user_login))
            )
        ).scalars().all()
        people = [person for actor_id in actor_ids if (person := await self._person_for_actor(str(actor_id))) is not None]
        return people, warnings

    async def _person_for_actor(self, actor_id: str) -> RegistryPerson | None:
        normalized = normalize_identifier("ui_login", actor_id)
        if not normalized:
            return None
        result = await self.session.execute(
            select(RegistryPerson)
            .join(RegistryPersonIdentity, RegistryPersonIdentity.person_id == RegistryPerson.person_id)
            .where(
                RegistryPersonIdentity.provider == "ui_login",
                RegistryPersonIdentity.normalized_identifier == normalized,
                RegistryPersonIdentity.verified.is_(True),
                RegistryPerson.status == "active",
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_group(self, audience_group_id: str) -> RegistryAudienceGroup:
        row = await self.session.get(RegistryAudienceGroup, str(audience_group_id))
        if row is None:
            raise ValueError("audience group not found")
        return row

    def _normalize_members(self, members: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_by_key: dict[tuple[str, str, bool], dict[str, Any]] = {}
        for raw in members or []:
            member_type = str(raw.get("member_type") or "").strip().lower()
            member_id = str(raw.get("member_id") or "").strip()
            if member_type not in ALLOWED_MEMBER_TYPES:
                raise ValueError(f"unsupported audience member type: {member_type}")
            if not member_id:
                raise ValueError("member_id is required")
            include_children = bool(raw.get("include_children")) or member_type == "department_tree"
            source = self._source(raw.get("source") or "manual")
            item = {
                "member_type": member_type,
                "member_id": member_id,
                "include_children": include_children,
                "source": source,
                "metadata_json": raw.get("metadata_json") if isinstance(raw.get("metadata_json"), dict) else {},
            }
            normalized_by_key[(member_type, member_id, include_children)] = item
        return [normalized_by_key[key] for key in sorted(normalized_by_key)]

    @staticmethod
    def _source(value: Any) -> str:
        source = str(value or "manual").strip().lower()
        if source not in ALLOWED_SOURCES:
            raise ValueError("invalid audience source")
        return source

    @staticmethod
    def serialize_group(row: RegistryAudienceGroup) -> dict[str, Any]:
        return {
            "audience_group_id": row.audience_group_id,
            "code": row.code,
            "name": row.name,
            "description": row.description,
            "source": row.source,
            "status": row.status,
            "metadata_json": row.metadata_json or {},
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
            "created_by": row.created_by,
            "updated_by": row.updated_by,
        }

    @staticmethod
    def serialize_member(row: RegistryAudienceGroupMember) -> dict[str, Any]:
        return {
            "membership_id": row.membership_id,
            "audience_group_id": row.audience_group_id,
            "member_type": row.member_type,
            "member_id": row.member_id,
            "include_children": bool(row.include_children),
            "valid_from": _iso(row.valid_from),
            "valid_to": _iso(row.valid_to),
            "source": row.source,
            "metadata_json": row.metadata_json or {},
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        }

    @staticmethod
    def serialize_person(person: RegistryPerson) -> dict[str, Any]:
        return {
            "person_id": person.person_id,
            "display_name": person.display_name,
            "full_name": person.full_name,
            "email": person.email,
            "department_id": person.department_id,
            "location_id": person.location_id,
            "status": person.status,
        }
