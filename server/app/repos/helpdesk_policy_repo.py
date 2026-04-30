"""Repository for standalone helpdesk request-template and policy registries."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ApprovalPolicy,
    ClosurePolicy,
    DiagnosticPolicy,
    HelpdeskPolicyAudit,
    NotificationPolicy,
    PriorityPolicy,
    RequestTemplate,
    RoutingPolicy,
    SmartView,
    VisibilityPolicy,
)
from tickets.form_catalog import next_form_pack_version
from utils.versioning import version_key


POLICY_MODELS = {
    "priority": PriorityPolicy,
    "routing": RoutingPolicy,
    "approval": ApprovalPolicy,
    "closure": ClosurePolicy,
    "diagnostic": DiagnosticPolicy,
    "notification": NotificationPolicy,
    "visibility": VisibilityPolicy,
}

POLICY_TABLE_NAMES = {
    "priority": "priority_policies",
    "routing": "routing_policies",
    "approval": "approval_policies",
    "closure": "closure_policies",
    "diagnostic": "diagnostic_policies",
    "notification": "notification_policies",
    "visibility": "visibility_policies",
}

SCOPE_RANK = {
    "system": 0,
    "ticket_type": 1,
    "category": 2,
    "request_template": 3,
}


def normalize_policy_kind(raw_kind: Any) -> str:
    kind = str(raw_kind or "").strip().lower()
    kind = kind.removesuffix("_policy").removesuffix("_policies")
    if kind not in POLICY_MODELS:
        raise ValueError(f"unknown policy kind: {raw_kind}")
    return kind


def normalize_template_code(raw_value: Any) -> str:
    code = str(raw_value or "").strip().lower().replace(" ", "_")
    cleaned = "".join(ch for ch in code if ch.isalnum() or ch in {"_", "-", "."})
    return cleaned.strip("_.-")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if (
            isinstance(value, dict)
            and isinstance(result.get(key), dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _row_version(row: Any) -> str:
    return str(getattr(row, "version", "") or "")


def _latest_version(rows: list[Any]) -> str | None:
    if not rows:
        return None
    return max((_row_version(row) for row in rows), key=lambda value: version_key(value).key)


def _row_timestamp(row: Any) -> datetime:
    return (
        getattr(row, "published_at", None)
        or getattr(row, "updated_at", None)
        or getattr(row, "created_at", None)
        or datetime.min.replace(tzinfo=timezone.utc)
    )


def serialize_policy_row(kind: str, row: Any) -> dict[str, Any]:
    return {
        "kind": normalize_policy_kind(kind),
        "table": POLICY_TABLE_NAMES[normalize_policy_kind(kind)],
        "code": str(row.code),
        "version": str(row.version),
        "title": str(row.title),
        "description": row.description,
        "scope_level": str(row.scope_level or "system"),
        "scope_ref": row.scope_ref,
        "config": deepcopy(row.config_json or {}),
        "is_active": bool(row.is_active),
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by": row.created_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": row.updated_by,
    }


def serialize_request_template(row: RequestTemplate) -> dict[str, Any]:
    return {
        "template_code": str(row.template_code),
        "version": str(row.version),
        "public_title": str(row.public_title),
        "internal_name": row.internal_name,
        "description": row.description,
        "ticket_type": str(row.ticket_type),
        "category_id": row.category_id,
        "service_id": row.service_id,
        "subcategory_id": row.subcategory_id,
        "form_schema_id": row.form_schema_id,
        "workflow_profile_id": row.workflow_profile_id,
        "priority_policy_code": row.priority_policy_code,
        "routing_policy_code": row.routing_policy_code,
        "sla_policy_id": row.sla_policy_id,
        "ola_policy_code": row.ola_policy_code,
        "approval_policy_code": row.approval_policy_code,
        "diagnostic_policy_code": row.diagnostic_policy_code,
        "closure_policy_code": row.closure_policy_code,
        "visibility_policy_code": row.visibility_policy_code,
        "notification_policy_code": row.notification_policy_code,
        "config": deepcopy(row.config_json or {}),
        "overrides": deepcopy(row.overrides_json or {}),
        "is_active": bool(row.is_active),
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by": row.created_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": row.updated_by,
    }


def serialize_smart_view(row: SmartView) -> dict[str, Any]:
    return {
        "code": str(row.code),
        "version": str(row.version),
        "title": str(row.title),
        "description": row.description,
        "scope_level": str(row.scope_level or "system"),
        "scope_ref": row.scope_ref,
        "filter": deepcopy(row.filter_json or {}),
        "sort": deepcopy(row.sort_json or []),
        "columns": deepcopy(row.columns_json or []),
        "is_active": bool(row.is_active),
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by": row.created_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": row.updated_by,
    }


class HelpdeskPolicyRepo:
    """Data access for versioned request templates, policies and smart views."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _audit(
        self,
        *,
        entity_type: str,
        entity_code: str,
        version: str,
        action: str,
        actor_id: str | None,
        actor_role: str | None,
        before_json: dict[str, Any] | None,
        after_json: dict[str, Any] | None,
    ) -> None:
        self.session.add(
            HelpdeskPolicyAudit(
                entity_type=entity_type,
                entity_code=entity_code,
                version=version,
                action=action,
                actor_id=actor_id,
                actor_role=actor_role,
                before_json=before_json,
                after_json=after_json,
                created_at=datetime.now(timezone.utc),
            )
        )

    async def list_policies(self, kind: str | None = None, *, include_inactive: bool = True) -> dict[str, list[dict[str, Any]]]:
        kinds = [normalize_policy_kind(kind)] if kind else list(POLICY_MODELS)
        result: dict[str, list[dict[str, Any]]] = {}
        for item_kind in kinds:
            model = POLICY_MODELS[item_kind]
            stmt = select(model)
            if not include_inactive:
                stmt = stmt.where(model.is_active.is_(True))
            stmt = stmt.order_by(model.code.asc(), model.created_at.desc())
            rows = list((await self.session.execute(stmt)).scalars().all())
            result[item_kind] = [serialize_policy_row(item_kind, row) for row in rows]
        return result

    async def list_request_templates(self, *, include_inactive: bool = True) -> list[dict[str, Any]]:
        stmt = select(RequestTemplate)
        if not include_inactive:
            stmt = stmt.where(RequestTemplate.is_active.is_(True))
        stmt = stmt.order_by(RequestTemplate.template_code.asc(), RequestTemplate.created_at.desc())
        rows = list((await self.session.execute(stmt)).scalars().all())
        return [serialize_request_template(row) for row in rows]

    async def list_smart_views(self, *, include_inactive: bool = True) -> list[dict[str, Any]]:
        stmt = select(SmartView)
        if not include_inactive:
            stmt = stmt.where(SmartView.is_active.is_(True))
        stmt = stmt.order_by(SmartView.code.asc(), SmartView.created_at.desc())
        rows = list((await self.session.execute(stmt)).scalars().all())
        return [serialize_smart_view(row) for row in rows]

    async def publish_policy(
        self,
        *,
        kind: str,
        code: str,
        title: str,
        config: dict[str, Any],
        description: str | None = None,
        scope_level: str = "system",
        scope_ref: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        requested_version: str | None = None,
    ) -> dict[str, Any]:
        normalized_kind = normalize_policy_kind(kind)
        model = POLICY_MODELS[normalized_kind]
        normalized_code = normalize_template_code(code)
        if not normalized_code:
            raise ValueError("policy code is required")
        if not isinstance(config, dict):
            raise ValueError("policy config must be object")

        existing_rows = list(
            (
                await self.session.execute(
                    select(model).where(model.code == normalized_code)
                )
            ).scalars().all()
        )
        latest = _latest_version(existing_rows)
        version = str(requested_version or next_form_pack_version(latest)).strip()
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(model)
            .where(model.code == normalized_code, model.is_active.is_(True))
            .values(is_active=False, valid_to=now, updated_at=now, updated_by=actor_id)
        )
        row = model(
            code=normalized_code,
            version=version,
            title=str(title or normalized_code),
            description=description,
            scope_level=str(scope_level or "system"),
            scope_ref=str(scope_ref).strip() if scope_ref is not None and str(scope_ref).strip() else None,
            config_json=deepcopy(config),
            is_active=True,
            valid_from=now,
            published_at=now,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        serialized = serialize_policy_row(normalized_kind, row)
        await self._audit(
            entity_type=POLICY_TABLE_NAMES[normalized_kind],
            entity_code=normalized_code,
            version=version,
            action="published",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=None,
            after_json=serialized,
        )
        return serialized

    async def publish_request_template(
        self,
        *,
        template_code: str,
        public_title: str,
        ticket_type: str,
        internal_name: str | None = None,
        description: str | None = None,
        category_id: int | None = None,
        service_id: int | None = None,
        subcategory_id: int | None = None,
        form_schema_id: str | None = None,
        workflow_profile_id: str | None = None,
        priority_policy_code: str | None = None,
        routing_policy_code: str | None = None,
        sla_policy_id: int | None = None,
        ola_policy_code: str | None = None,
        approval_policy_code: str | None = None,
        diagnostic_policy_code: str | None = None,
        closure_policy_code: str | None = None,
        visibility_policy_code: str | None = None,
        notification_policy_code: str | None = None,
        config: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        requested_version: str | None = None,
    ) -> dict[str, Any]:
        code = normalize_template_code(template_code)
        if not code:
            raise ValueError("template code is required")
        existing_rows = list(
            (
                await self.session.execute(
                    select(RequestTemplate).where(RequestTemplate.template_code == code)
                )
            ).scalars().all()
        )
        latest = _latest_version(existing_rows)
        version = str(requested_version or next_form_pack_version(latest)).strip()
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(RequestTemplate)
            .where(RequestTemplate.template_code == code, RequestTemplate.is_active.is_(True))
            .values(is_active=False, valid_to=now, updated_at=now, updated_by=actor_id)
        )
        row = RequestTemplate(
            template_code=code,
            version=version,
            public_title=str(public_title or code),
            internal_name=internal_name,
            description=description,
            ticket_type=str(ticket_type or "incident"),
            category_id=category_id,
            service_id=service_id,
            subcategory_id=subcategory_id,
            form_schema_id=form_schema_id,
            workflow_profile_id=workflow_profile_id,
            priority_policy_code=priority_policy_code,
            routing_policy_code=routing_policy_code,
            sla_policy_id=sla_policy_id,
            ola_policy_code=ola_policy_code,
            approval_policy_code=approval_policy_code,
            diagnostic_policy_code=diagnostic_policy_code,
            closure_policy_code=closure_policy_code,
            visibility_policy_code=visibility_policy_code,
            notification_policy_code=notification_policy_code,
            config_json=deepcopy(config or {}),
            overrides_json=deepcopy(overrides or {}),
            is_active=True,
            valid_from=now,
            published_at=now,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        serialized = serialize_request_template(row)
        await self._audit(
            entity_type="request_templates",
            entity_code=code,
            version=version,
            action="published",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=None,
            after_json=serialized,
        )
        return serialized

    async def resolve_effective_policy(
        self,
        *,
        kind: str,
        ticket_type: str | None = None,
        category_id: int | str | None = None,
        template_code: str | None = None,
    ) -> dict[str, Any]:
        normalized_kind = normalize_policy_kind(kind)
        model = POLICY_MODELS[normalized_kind]
        category_ref = str(category_id) if category_id is not None and str(category_id).strip() else None
        template_ref = normalize_template_code(template_code)
        matching_scopes: list[tuple[str, str | None]] = [("system", None)]
        if ticket_type:
            matching_scopes.append(("ticket_type", str(ticket_type)))
        if category_ref:
            matching_scopes.append(("category", category_ref))
        if template_ref:
            matching_scopes.append(("request_template", template_ref))

        rows = list(
            (
                await self.session.execute(
                    select(model).where(model.is_active.is_(True))
                )
            ).scalars().all()
        )
        selected = [
            row
            for row in rows
            if (
                str(row.scope_level or "system"),
                str(row.scope_ref) if row.scope_ref is not None else None,
            )
            in matching_scopes
        ]
        selected.sort(
            key=lambda row: (
                SCOPE_RANK.get(str(row.scope_level or "system"), 99),
                _row_timestamp(row),
                version_key(str(row.version)).key,
            )
        )
        effective: dict[str, Any] = {}
        sources: list[dict[str, Any]] = []
        for row in selected:
            effective = _deep_merge(effective, row.config_json or {})
            sources.append(
                {
                    "code": row.code,
                    "version": row.version,
                    "scope_level": row.scope_level,
                    "scope_ref": row.scope_ref,
                }
            )
        return {
            "kind": normalized_kind,
            "config": effective,
            "sources": sources,
        }
