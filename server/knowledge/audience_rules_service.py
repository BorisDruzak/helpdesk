from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeAudienceRule, KnowledgeItem, KnowledgeSpace
from knowledge.access_service import KnowledgeAccessDecision, KnowledgeAccessService, RULE_TARGET_TYPES
from registry.effective_identity_service import EffectiveIdentityService


ALLOWED_SUBJECT_TYPES = {"space", "item"}
ALLOWED_RULE_STATUSES = {"active", "disabled"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any, *, max_length: int = 500) -> str | None:
    text = str(value or "").strip()
    return text[:max_length] if text else None


def _clean_subject_type(value: Any) -> str:
    subject_type = str(value or "").strip().lower()
    if subject_type not in ALLOWED_SUBJECT_TYPES:
        raise ValueError("subject_type must be space or item")
    return subject_type


def _clean_status(value: Any) -> str:
    status = str(value or "active").strip().lower()
    if status not in ALLOWED_RULE_STATUSES:
        raise ValueError("status must be active or disabled")
    return status


def _clean_target_type(value: Any) -> str:
    target_type = str(value or "").strip().lower()
    if target_type not in RULE_TARGET_TYPES:
        raise ValueError("target_type is not supported")
    return target_type


def _decision_payload(decision: KnowledgeAccessDecision) -> dict[str, Any]:
    return {
        "allowed": decision.allowed,
        "reason_code": decision.reason_code,
        "matched_rule_ids": list(decision.matched_rule_ids),
    }


def _item_payload(row: KnowledgeItem) -> dict[str, Any]:
    return {
        "item_id": row.item_id,
        "space_id": row.space_id,
        "slug": row.slug,
        "status": row.status,
        "visibility": row.visibility,
        "current_version_id": row.current_version_id,
    }


def _space_payload(row: KnowledgeSpace | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "space_id": row.space_id,
        "code": row.code,
        "title": row.title,
        "lifecycle_status": row.lifecycle_status,
        "visibility": row.visibility,
    }


def _space_preview_item_payload(space: KnowledgeSpace) -> dict[str, Any]:
    return {
        "item_id": f"__space_preview__:{space.space_id}",
        "space_id": space.space_id,
        "status": "published",
        "visibility": space.visibility,
        "current_version_id": f"__space_preview_version__:{space.space_id}",
    }


class KnowledgeAudienceRulesService:
    """Admin service for Knowledge audience-rule authoring and explain."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_rules(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        stmt = select(KnowledgeAudienceRule)
        if subject_type:
            stmt = stmt.where(KnowledgeAudienceRule.subject_type == _clean_subject_type(subject_type))
        if subject_id:
            stmt = stmt.where(KnowledgeAudienceRule.subject_id == str(subject_id).strip())
        if not include_archived:
            stmt = stmt.where(KnowledgeAudienceRule.status != "archived")
        stmt = stmt.order_by(
            KnowledgeAudienceRule.subject_type.asc(),
            KnowledgeAudienceRule.subject_id.asc(),
            KnowledgeAudienceRule.priority.asc(),
            KnowledgeAudienceRule.created_at.asc(),
            KnowledgeAudienceRule.rule_id.asc(),
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self.serialize_rule(row) for row in rows]

    async def replace_subject_rules(
        self,
        *,
        subject_type: str,
        subject_id: str,
        rules: list[dict[str, Any]],
        actor_id: str | None,
        reason: str | None = None,
    ) -> list[dict[str, Any]]:
        clean_subject_type = _clean_subject_type(subject_type)
        clean_subject_id = str(subject_id or "").strip()
        if not clean_subject_id:
            raise ValueError("subject_id is required")
        if not isinstance(rules, list):
            raise ValueError("rules must be a list")
        await self._ensure_subject_exists(clean_subject_type, clean_subject_id)

        existing = (
            await self.session.execute(
                select(KnowledgeAudienceRule).where(
                    KnowledgeAudienceRule.subject_type == clean_subject_type,
                    KnowledgeAudienceRule.subject_id == clean_subject_id,
                    KnowledgeAudienceRule.status != "archived",
                )
            )
        ).scalars().all()
        for row in existing:
            row.status = "archived"
            row.updated_by = actor_id
            row.updated_at = _now()

        for index, payload in enumerate(rules):
            rule_payload = self._normalize_rule_payload(
                payload,
                subject_type=clean_subject_type,
                subject_id=clean_subject_id,
                default_priority=(index + 1) * 10,
                default_reason=reason,
            )
            self.session.add(
                KnowledgeAudienceRule(
                    rule_id=str(uuid.uuid4()),
                    subject_type=clean_subject_type,
                    subject_id=clean_subject_id,
                    target_type=rule_payload["target_type"],
                    target_id=rule_payload["target_id"],
                    effect="allow",
                    include_children=rule_payload["include_children"],
                    priority=rule_payload["priority"],
                    status=rule_payload["status"],
                    reason=rule_payload["reason"],
                    metadata_json=rule_payload["metadata_json"],
                    created_by=actor_id,
                    updated_by=actor_id,
                )
            )
        await self.session.flush()
        return await self.list_rules(subject_type=clean_subject_type, subject_id=clean_subject_id)

    async def preview_subject_access(
        self,
        *,
        subject_type: str,
        subject_id: str,
        actor_id: str | None,
        actor_role: str,
        rules: list[dict[str, Any]] | None = None,
        service_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_subject_type = _clean_subject_type(subject_type)
        audience = await EffectiveIdentityService(self.session).resolve_person_audience(
            person_id=None,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        if clean_subject_type == "item":
            item, space = await self._load_item_and_space(str(subject_id or "").strip())
            if rules is None:
                rule_payloads = await self._rules_for_item(item)
            else:
                rule_payloads = [
                    self._normalize_rule_payload(
                        payload,
                        subject_type=clean_subject_type,
                        subject_id=item.item_id,
                        default_priority=(index + 1) * 10,
                    )
                    for index, payload in enumerate(rules)
                ]
            item_payload = _item_payload(item)
            space_payload = _space_payload(space)
            subject_payload = {"subject_type": clean_subject_type, "subject_id": item.item_id}
            response_item: dict[str, Any] | None = item_payload
        else:
            space = await self._load_space(str(subject_id or "").strip())
            if rules is None:
                rule_payloads = await self._rules_for_space(space)
            else:
                rule_payloads = [
                    self._normalize_rule_payload(
                        payload,
                        subject_type=clean_subject_type,
                        subject_id=space.space_id,
                        default_priority=(index + 1) * 10,
                    )
                    for index, payload in enumerate(rules)
                ]
            item_payload = _space_preview_item_payload(space)
            space_payload = _space_payload(space)
            subject_payload = {"subject_type": clean_subject_type, "subject_id": space.space_id}
            response_item = None

        decision = KnowledgeAccessService.evaluate_item_access(
            item=item_payload,
            space=space_payload,
            audience=audience,
            rules=rule_payloads,
            service_context=service_context,
        )
        return {
            "subject": subject_payload,
            "item": response_item,
            "space": space_payload,
            "audience": audience.to_dict(),
            "decision": _decision_payload(decision),
            "safe_payload": decision.safe_denial_payload(),
        }

    async def explain_item_access(
        self,
        *,
        item_id: str,
        actor_id: str | None,
        actor_role: str,
        service_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item, space = await self._load_item_and_space(str(item_id or "").strip())
        audience = await EffectiveIdentityService(self.session).resolve_person_audience(
            person_id=None,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        rules = await self._rules_for_item(item)
        decision = KnowledgeAccessService.evaluate_item_access(
            item=_item_payload(item),
            space=_space_payload(space),
            audience=audience,
            rules=rules,
            service_context=service_context,
        )
        return {
            "item": _item_payload(item),
            "space": _space_payload(space),
            "audience": audience.to_dict(),
            "rules": rules,
            "decision": _decision_payload(decision),
            "safe_payload": decision.safe_denial_payload(),
        }

    async def _rules_for_item(self, item: KnowledgeItem) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(KnowledgeAudienceRule)
                .where(
                    KnowledgeAudienceRule.status == "active",
                    or_(
                        and_(
                            KnowledgeAudienceRule.subject_type == "item",
                            KnowledgeAudienceRule.subject_id == item.item_id,
                        ),
                        and_(
                            KnowledgeAudienceRule.subject_type == "space",
                            KnowledgeAudienceRule.subject_id == item.space_id,
                        ),
                    ),
                )
                .order_by(
                    KnowledgeAudienceRule.priority.asc(),
                    KnowledgeAudienceRule.created_at.asc(),
                    KnowledgeAudienceRule.rule_id.asc(),
                )
            )
        ).scalars().all()
        return [self.serialize_rule(row) for row in rows]

    async def _rules_for_space(self, space: KnowledgeSpace) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(KnowledgeAudienceRule)
                .where(
                    KnowledgeAudienceRule.status == "active",
                    KnowledgeAudienceRule.subject_type == "space",
                    KnowledgeAudienceRule.subject_id == space.space_id,
                )
                .order_by(
                    KnowledgeAudienceRule.priority.asc(),
                    KnowledgeAudienceRule.created_at.asc(),
                    KnowledgeAudienceRule.rule_id.asc(),
                )
            )
        ).scalars().all()
        return [self.serialize_rule(row) for row in rows]

    async def _load_item_and_space(self, item_ref: str) -> tuple[KnowledgeItem, KnowledgeSpace | None]:
        if not item_ref:
            raise ValueError("item_id is required")
        row = (
            await self.session.execute(
                select(KnowledgeItem)
                .where(or_(KnowledgeItem.item_id == item_ref, KnowledgeItem.slug == item_ref))
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is None:
            raise ValueError("knowledge item was not found")
        space = await self.session.get(KnowledgeSpace, row.space_id) if row.space_id else None
        return row, space

    async def _load_space(self, space_ref: str) -> KnowledgeSpace:
        if not space_ref:
            raise ValueError("space_id is required")
        row = (
            await self.session.execute(
                select(KnowledgeSpace)
                .where(or_(KnowledgeSpace.space_id == space_ref, KnowledgeSpace.code == space_ref))
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is None:
            raise ValueError("knowledge space was not found")
        return row

    async def _ensure_subject_exists(self, subject_type: str, subject_id: str) -> None:
        if subject_type == "item":
            await self._load_item_and_space(subject_id)
            return
        await self._load_space(subject_id)

    def _normalize_rule_payload(
        self,
        payload: dict[str, Any],
        *,
        subject_type: str,
        subject_id: str,
        default_priority: int,
        default_reason: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("rule must be an object")
        target_type = _clean_target_type(payload.get("target_type"))
        target_id = str(payload.get("target_id") or "").strip()
        if not target_id:
            raise ValueError("target_id is required")
        try:
            priority = int(payload.get("priority") if payload.get("priority") is not None else default_priority)
        except (TypeError, ValueError) as exc:
            raise ValueError("priority must be an integer") from exc
        metadata_json = payload.get("metadata_json") or payload.get("metadata") or {}
        if not isinstance(metadata_json, dict):
            raise ValueError("metadata_json must be an object")
        return {
            "rule_id": str(payload.get("rule_id") or ""),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "target_type": target_type,
            "target_id": target_id,
            "effect": "allow",
            "include_children": bool(payload.get("include_children")) or target_type == "department_tree",
            "priority": priority,
            "status": _clean_status(payload.get("status")),
            "reason": _clean_text(payload.get("reason") or default_reason, max_length=1000),
            "metadata_json": metadata_json,
        }

    @staticmethod
    def serialize_rule(row: KnowledgeAudienceRule) -> dict[str, Any]:
        return {
            "rule_id": row.rule_id,
            "subject_type": row.subject_type,
            "subject_id": row.subject_id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "effect": row.effect,
            "include_children": bool(row.include_children),
            "priority": int(row.priority or 0),
            "status": row.status,
            "reason": row.reason,
            "metadata_json": row.metadata_json or {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "created_by": row.created_by,
            "updated_by": row.updated_by,
        }
