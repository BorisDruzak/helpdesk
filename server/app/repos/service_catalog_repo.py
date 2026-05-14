from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    HelpdeskService,
    HelpdeskServiceCatalogAudit,
    HelpdeskServiceOffering,
)
from tickets.service_catalog_contract import (
    full_offering_code,
    normalize_business_criticality,
    normalize_catalog_code,
    normalize_lifecycle_status,
    normalize_visibility,
)


def _new_id() -> str:
    return str(uuid.uuid4())


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def serialize_service(row: HelpdeskService) -> dict[str, Any]:
    return {
        "service_id": row.service_id,
        "code": row.code,
        "name": row.name,
        "public_title": row.public_title,
        "short_description": row.short_description,
        "description": row.description,
        "icon": row.icon,
        "lifecycle_status": row.lifecycle_status,
        "visibility": row.visibility,
        "sort_order": row.sort_order,
        "business_criticality": row.business_criticality,
        "owner_actor_id": row.owner_actor_id,
        "owner_person_id": row.owner_person_id,
        "owner_queue_id": row.owner_queue_id,
        "support_group_code": row.support_group_code,
        "registry_service_id": row.registry_service_id,
        "default_ticket_type_code": row.default_ticket_type_code,
        "default_queue_id": row.default_queue_id,
        "default_priority_policy_code": row.default_priority_policy_code,
        "default_routing_policy_code": row.default_routing_policy_code,
        "default_sla_policy_code": row.default_sla_policy_code,
        "default_ola_policy_code": row.default_ola_policy_code,
        "default_approval_policy_code": row.default_approval_policy_code,
        "default_diagnostic_policy_code": row.default_diagnostic_policy_code,
        "default_closure_policy_code": row.default_closure_policy_code,
        "default_visibility_policy_code": row.default_visibility_policy_code,
        "default_notification_policy_code": row.default_notification_policy_code,
        "default_reporting_policy_code": row.default_reporting_policy_code,
        "reporting_category": row.reporting_category,
        "metadata": deepcopy(row.metadata_json or {}),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "published_at": _iso(row.published_at),
        "retired_at": _iso(row.retired_at),
    }


def serialize_offering(row: HelpdeskServiceOffering, *, service_code: str | None = None) -> dict[str, Any]:
    return {
        "offering_id": row.offering_id,
        "service_id": row.service_id,
        "service_code": service_code,
        "code": row.code,
        "full_code": row.full_code,
        "name": row.name,
        "public_title": row.public_title,
        "short_description": row.short_description,
        "description": row.description,
        "lifecycle_status": row.lifecycle_status,
        "visibility": row.visibility,
        "sort_order": row.sort_order,
        "ticket_type_code": row.ticket_type_code,
        "request_type": row.request_type,
        "request_template_id": row.request_template_id,
        "request_template_key": row.request_template_key,
        "form_schema_id": row.form_schema_id,
        "default_queue_id": row.default_queue_id,
        "priority_policy_code": row.priority_policy_code,
        "routing_policy_code": row.routing_policy_code,
        "sla_policy_code": row.sla_policy_code,
        "ola_policy_code": row.ola_policy_code,
        "approval_policy_code": row.approval_policy_code,
        "diagnostic_policy_code": row.diagnostic_policy_code,
        "closure_policy_code": row.closure_policy_code,
        "visibility_policy_code": row.visibility_policy_code,
        "notification_policy_code": row.notification_policy_code,
        "reporting_policy_code": row.reporting_policy_code,
        "reporting_category": row.reporting_category,
        "kb_article_refs": deepcopy(row.kb_article_refs or []),
        "availability": deepcopy(row.availability_json or {}),
        "metadata": deepcopy(row.metadata_json or {}),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "published_at": _iso(row.published_at),
        "retired_at": _iso(row.retired_at),
    }


class ServiceCatalogRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def append_audit(
        self,
        *,
        object_type: str,
        object_code: str,
        action: str,
        actor_id: str | None,
        actor_role: str | None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        issues: list[dict[str, Any]] | None = None,
    ) -> None:
        self.session.add(
            HelpdeskServiceCatalogAudit(
                object_type=object_type,
                object_code=object_code,
                action=action,
                actor_id=actor_id,
                actor_role=actor_role,
                before_json=deepcopy(before) if before is not None else None,
                after_json=deepcopy(after) if after is not None else None,
                issues_json=deepcopy(issues or []),
            )
        )
        await self.session.flush()

    async def list_services(
        self,
        *,
        include_retired: bool = True,
        published_only: bool = False,
    ) -> list[dict[str, Any]]:
        stmt = select(HelpdeskService)
        if published_only:
            stmt = stmt.where(HelpdeskService.lifecycle_status == "published")
        elif not include_retired:
            stmt = stmt.where(HelpdeskService.lifecycle_status != "retired")
        stmt = stmt.order_by(HelpdeskService.sort_order.asc(), HelpdeskService.code.asc())
        rows = (await self.session.execute(stmt)).scalars().all()
        return [serialize_service(row) for row in rows]

    async def get_service_by_code(self, code: str | None) -> dict[str, Any] | None:
        normalized = normalize_catalog_code(code, field_name="service_code")
        row = (
            await self.session.execute(select(HelpdeskService).where(HelpdeskService.code == normalized))
        ).scalar_one_or_none()
        return serialize_service(row) if row else None

    async def get_service_row_by_code(self, code: str | None) -> HelpdeskService | None:
        normalized = normalize_catalog_code(code, field_name="service_code")
        return (
            await self.session.execute(select(HelpdeskService).where(HelpdeskService.code == normalized))
        ).scalar_one_or_none()

    async def upsert_service_draft(
        self,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str | None,
    ) -> dict[str, Any]:
        code = normalize_catalog_code(payload.get("code"), field_name="service_code")
        row = await self.get_service_row_by_code(code)
        before = serialize_service(row) if row else None
        now = datetime.now(timezone.utc)
        if row is None:
            row = HelpdeskService(
                service_id=str(payload.get("service_id") or _new_id()),
                code=code,
                name=_clean_text(payload.get("name") or payload.get("public_title") or code) or code,
                public_title=_clean_text(payload.get("public_title") or payload.get("name") or code) or code,
                created_at=now,
                updated_at=now,
                created_by=actor_id,
            )
            self.session.add(row)
        row.name = _clean_text(payload.get("name") or payload.get("public_title") or row.name) or row.name
        row.public_title = _clean_text(payload.get("public_title") or payload.get("name") or row.public_title) or row.public_title
        row.short_description = _clean_text(payload.get("short_description"))
        row.description = _clean_text(payload.get("description"))
        row.icon = _clean_text(payload.get("icon"))
        row.lifecycle_status = normalize_lifecycle_status(payload.get("lifecycle_status"), default=row.lifecycle_status or "draft")
        row.visibility = normalize_visibility(payload.get("visibility"), default=row.visibility or "internal")
        row.sort_order = int(payload.get("sort_order") or row.sort_order or 0)
        row.business_criticality = normalize_business_criticality(payload.get("business_criticality"), default=row.business_criticality or "medium")
        for field in (
            "owner_actor_id",
            "owner_person_id",
            "support_group_code",
            "registry_service_id",
            "default_ticket_type_code",
            "default_priority_policy_code",
            "default_routing_policy_code",
            "default_sla_policy_code",
            "default_ola_policy_code",
            "default_approval_policy_code",
            "default_diagnostic_policy_code",
            "default_closure_policy_code",
            "default_visibility_policy_code",
            "default_notification_policy_code",
            "default_reporting_policy_code",
            "reporting_category",
        ):
            if field in payload:
                setattr(row, field, _clean_text(payload.get(field)))
        for field in ("owner_queue_id", "default_queue_id"):
            if field in payload:
                value = payload.get(field)
                setattr(row, field, int(value) if value not in (None, "") else None)
        if isinstance(payload.get("metadata"), dict):
            row.metadata_json = deepcopy(payload["metadata"])
        elif isinstance(payload.get("metadata_json"), dict):
            row.metadata_json = deepcopy(payload["metadata_json"])
        row.updated_at = now
        row.updated_by = actor_id
        await self.session.flush()
        after = serialize_service(row)
        await self.append_audit(
            object_type="service",
            object_code=code,
            action="saved_draft",
            actor_id=actor_id,
            actor_role=actor_role,
            before=before,
            after=after,
        )
        return after

    async def publish_service(self, code: str, *, actor_id: str | None, actor_role: str | None) -> dict[str, Any]:
        row = await self.get_service_row_by_code(code)
        if row is None:
            raise ValueError("service not found")
        before = serialize_service(row)
        now = datetime.now(timezone.utc)
        row.lifecycle_status = "published"
        row.published_at = row.published_at or now
        row.retired_at = None
        row.updated_at = now
        row.updated_by = actor_id
        await self.session.flush()
        after = serialize_service(row)
        await self.append_audit(
            object_type="service",
            object_code=row.code,
            action="published",
            actor_id=actor_id,
            actor_role=actor_role,
            before=before,
            after=after,
        )
        return after

    async def retire_service(self, code: str, *, actor_id: str | None, actor_role: str | None) -> dict[str, Any]:
        row = await self.get_service_row_by_code(code)
        if row is None:
            raise ValueError("service not found")
        before = serialize_service(row)
        now = datetime.now(timezone.utc)
        row.lifecycle_status = "retired"
        row.retired_at = now
        row.updated_at = now
        row.updated_by = actor_id
        await self.session.flush()
        after = serialize_service(row)
        await self.append_audit(
            object_type="service",
            object_code=row.code,
            action="retired",
            actor_id=actor_id,
            actor_role=actor_role,
            before=before,
            after=after,
        )
        return after

    async def list_offerings(
        self,
        *,
        service_code: str | None = None,
        published_only: bool = False,
    ) -> list[dict[str, Any]]:
        service_rows = {row.service_id: row.code for row in (await self.session.execute(select(HelpdeskService))).scalars().all()}
        stmt = select(HelpdeskServiceOffering)
        if service_code:
            service = await self.get_service_row_by_code(service_code)
            if service is None:
                return []
            stmt = stmt.where(HelpdeskServiceOffering.service_id == service.service_id)
        if published_only:
            stmt = stmt.where(HelpdeskServiceOffering.lifecycle_status == "published")
        stmt = stmt.order_by(HelpdeskServiceOffering.sort_order.asc(), HelpdeskServiceOffering.full_code.asc())
        rows = (await self.session.execute(stmt)).scalars().all()
        return [serialize_offering(row, service_code=service_rows.get(row.service_id)) for row in rows]

    async def get_offering_by_full_code(self, value: str | None) -> dict[str, Any] | None:
        full_code = str(value or "").strip().lower()
        row = (
            await self.session.execute(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == full_code))
        ).scalar_one_or_none()
        if row is None:
            return None
        service = await self.session.get(HelpdeskService, row.service_id)
        return serialize_offering(row, service_code=service.code if service else None)

    async def get_offering_row_by_full_code(self, value: str | None) -> HelpdeskServiceOffering | None:
        full_code = str(value or "").strip().lower()
        if not full_code:
            return None
        return (
            await self.session.execute(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == full_code))
        ).scalar_one_or_none()

    async def upsert_offering_draft(
        self,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str | None,
    ) -> dict[str, Any]:
        service_code = normalize_catalog_code(payload.get("service_code"), field_name="service_code")
        service = await self.get_service_row_by_code(service_code)
        if service is None:
            raise ValueError("service not found")
        code = normalize_catalog_code(payload.get("code"), field_name="offering_code")
        combined = full_offering_code(service.code, code)
        row = await self.get_offering_row_by_full_code(combined)
        before = serialize_offering(row, service_code=service.code) if row else None
        now = datetime.now(timezone.utc)
        if row is None:
            row = HelpdeskServiceOffering(
                offering_id=str(payload.get("offering_id") or _new_id()),
                service_id=service.service_id,
                code=code,
                full_code=combined,
                name=_clean_text(payload.get("name") or payload.get("public_title") or code) or code,
                public_title=_clean_text(payload.get("public_title") or payload.get("name") or code) or code,
                created_at=now,
                updated_at=now,
                created_by=actor_id,
            )
            self.session.add(row)
        row.name = _clean_text(payload.get("name") or payload.get("public_title") or row.name) or row.name
        row.public_title = _clean_text(payload.get("public_title") or payload.get("name") or row.public_title) or row.public_title
        row.short_description = _clean_text(payload.get("short_description"))
        row.description = _clean_text(payload.get("description"))
        row.lifecycle_status = normalize_lifecycle_status(payload.get("lifecycle_status"), default=row.lifecycle_status or "draft")
        row.visibility = normalize_visibility(payload.get("visibility"), default=row.visibility or "internal")
        row.sort_order = int(payload.get("sort_order") or row.sort_order or 0)
        for field in (
            "ticket_type_code",
            "request_type",
            "request_template_id",
            "request_template_key",
            "form_schema_id",
            "priority_policy_code",
            "routing_policy_code",
            "sla_policy_code",
            "ola_policy_code",
            "approval_policy_code",
            "diagnostic_policy_code",
            "closure_policy_code",
            "visibility_policy_code",
            "notification_policy_code",
            "reporting_policy_code",
            "reporting_category",
        ):
            if field in payload:
                setattr(row, field, _clean_text(payload.get(field)))
        if "default_queue_id" in payload:
            value = payload.get("default_queue_id")
            row.default_queue_id = int(value) if value not in (None, "") else None
        if isinstance(payload.get("kb_article_refs"), list):
            row.kb_article_refs = deepcopy(payload["kb_article_refs"])
        if isinstance(payload.get("availability"), dict):
            row.availability_json = deepcopy(payload["availability"])
        if isinstance(payload.get("metadata"), dict):
            row.metadata_json = deepcopy(payload["metadata"])
        row.updated_at = now
        row.updated_by = actor_id
        await self.session.flush()
        after = serialize_offering(row, service_code=service.code)
        await self.append_audit(
            object_type="offering",
            object_code=combined,
            action="saved_draft",
            actor_id=actor_id,
            actor_role=actor_role,
            before=before,
            after=after,
        )
        return after

    async def publish_offering(self, full_code_value: str, *, actor_id: str | None, actor_role: str | None) -> dict[str, Any]:
        row = await self.get_offering_row_by_full_code(full_code_value)
        if row is None:
            raise ValueError("offering not found")
        service = await self.session.get(HelpdeskService, row.service_id)
        before = serialize_offering(row, service_code=service.code if service else None)
        now = datetime.now(timezone.utc)
        row.lifecycle_status = "published"
        row.published_at = row.published_at or now
        row.retired_at = None
        row.updated_at = now
        row.updated_by = actor_id
        await self.session.flush()
        after = serialize_offering(row, service_code=service.code if service else None)
        await self.append_audit(
            object_type="offering",
            object_code=row.full_code,
            action="published",
            actor_id=actor_id,
            actor_role=actor_role,
            before=before,
            after=after,
        )
        return after

    async def retire_offering(self, full_code_value: str, *, actor_id: str | None, actor_role: str | None) -> dict[str, Any]:
        row = await self.get_offering_row_by_full_code(full_code_value)
        if row is None:
            raise ValueError("offering not found")
        service = await self.session.get(HelpdeskService, row.service_id)
        before = serialize_offering(row, service_code=service.code if service else None)
        now = datetime.now(timezone.utc)
        row.lifecycle_status = "retired"
        row.retired_at = now
        row.updated_at = now
        row.updated_by = actor_id
        await self.session.flush()
        after = serialize_offering(row, service_code=service.code if service else None)
        await self.append_audit(
            object_type="offering",
            object_code=row.full_code,
            action="retired",
            actor_id=actor_id,
            actor_role=actor_role,
            before=before,
            after=after,
        )
        return after
