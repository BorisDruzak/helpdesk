from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgeApplicabilityRule,
    KnowledgeItem,
    KnowledgeItemPropertyValue,
    KnowledgeItemTaxonomyTerm,
    KnowledgePropertyDefinition,
    KnowledgeQualityModel,
    KnowledgeSpace,
    KnowledgeTaxonomyTerm,
)
from knowledge.contracts import (
    KNOWLEDGE_VISIBILITIES,
    KnowledgeValidationError,
    actor_visible_visibilities,
    can_mutate_knowledge_visibility,
    can_read_knowledge_visibility,
    normalize_knowledge_slug,
)


TAXONOMY_TERM_TYPES = {"category", "product", "audience", "topic", "tag"}
PROPERTY_VALUE_TYPES = {"text", "number", "boolean", "date", "select", "multi_select", "url"}
APPLICABILITY_SCOPE_TYPES = {
    "service",
    "offering",
    "request_template",
    "role",
    "device_os",
    "device_family",
    "audience",
    "taxonomy_term",
    "custom",
}
APPLICABILITY_INCLUDE_MODES = {"include", "exclude"}


def _new_id() -> str:
    return str(uuid.uuid4())


def _dict(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _json_value(row: KnowledgeItemPropertyValue) -> Any:
    value = row.value_json if isinstance(row.value_json, dict) else {}
    return deepcopy(value.get("value"))


def serialize_taxonomy_term(row: KnowledgeTaxonomyTerm) -> dict[str, Any]:
    return {
        "term_id": row.term_id,
        "space_id": row.space_id,
        "term_type": row.term_type,
        "code": row.code,
        "title": row.title,
        "description": row.description,
        "parent_term_id": row.parent_term_id,
        "visibility": row.visibility,
        "status": row.status,
        "sort_order": row.sort_order,
        "metadata": _dict(row.metadata_json),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "created_by": row.created_by,
        "updated_by": row.updated_by,
    }


def serialize_property_definition(row: KnowledgePropertyDefinition) -> dict[str, Any]:
    return {
        "property_id": row.property_id,
        "space_id": row.space_id,
        "code": row.code,
        "title": row.title,
        "description": row.description,
        "value_type": row.value_type,
        "required": bool(row.required),
        "allowed_values": _list(row.allowed_values_json),
        "applies_to_item_types": _list(row.applies_to_item_types_json),
        "quality_weight": int(row.quality_weight or 0),
        "status": row.status,
        "metadata": _dict(row.metadata_json),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "created_by": row.created_by,
        "updated_by": row.updated_by,
    }


def serialize_applicability_rule(row: KnowledgeApplicabilityRule) -> dict[str, Any]:
    return {
        "rule_id": row.rule_id,
        "item_id": row.item_id,
        "scope_type": row.scope_type,
        "scope_ref": row.scope_ref,
        "include_mode": row.include_mode,
        "priority": int(row.priority or 0),
        "conditions": _dict(row.conditions_json),
        "metadata": _dict(row.metadata_json),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "created_by": row.created_by,
        "updated_by": row.updated_by,
    }


def serialize_quality_model(row: KnowledgeQualityModel) -> dict[str, Any]:
    return {
        "model_id": row.model_id,
        "space_id": row.space_id,
        "code": row.code,
        "title": row.title,
        "weights": _dict(row.weights_json),
        "thresholds": _dict(row.thresholds_json),
        "status": row.status,
        "is_default": bool(row.is_default),
        "metadata": _dict(row.metadata_json),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "created_by": row.created_by,
        "updated_by": row.updated_by,
    }


class KnowledgeMetadataService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _space(self, space_id: str) -> KnowledgeSpace:
        row = (await self.session.execute(select(KnowledgeSpace).where(KnowledgeSpace.space_id == space_id))).scalar_one_or_none()
        if row is None:
            raise KnowledgeValidationError("knowledge space not found")
        return row

    def _assert_space_mutable(self, space: KnowledgeSpace, *, actor_role: str) -> None:
        if not can_mutate_knowledge_visibility(actor_role, space.visibility):
            raise KnowledgeValidationError("actor cannot mutate this knowledge space")

    async def _item(self, item_ref: str, *, actor_role: str) -> KnowledgeItem:
        row = (
            await self.session.execute(
                select(KnowledgeItem).where(or_(KnowledgeItem.item_id == item_ref, KnowledgeItem.slug == item_ref))
            )
        ).scalar_one_or_none()
        if row is None or not can_read_knowledge_visibility(actor_role, row.visibility):
            raise KnowledgeValidationError("knowledge item not found")
        return row

    async def upsert_taxonomy_term(self, payload: dict[str, Any], *, actor_id: str | None, actor_role: str) -> dict[str, Any]:
        space_id = str(payload.get("space_id") or "")
        space = await self._space(space_id)
        self._assert_space_mutable(space, actor_role=actor_role)
        term_type = str(payload.get("term_type") or "tag")
        if term_type not in TAXONOMY_TERM_TYPES:
            raise KnowledgeValidationError("unsupported taxonomy term_type")
        code = normalize_knowledge_slug(payload.get("code") or payload.get("title"))
        visibility = str(payload.get("visibility") or "support_internal")
        if visibility not in KNOWLEDGE_VISIBILITIES:
            raise KnowledgeValidationError("unsupported taxonomy visibility")
        status = str(payload.get("status") or "active")
        if status not in {"active", "draft", "archived"}:
            raise KnowledgeValidationError("unsupported taxonomy status")
        now = datetime.now(timezone.utc)
        row = (
            await self.session.execute(
                select(KnowledgeTaxonomyTerm).where(
                    KnowledgeTaxonomyTerm.space_id == space_id,
                    KnowledgeTaxonomyTerm.term_type == term_type,
                    KnowledgeTaxonomyTerm.code == code,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = KnowledgeTaxonomyTerm(
                term_id=str(payload.get("term_id") or _new_id()),
                space_id=space_id,
                term_type=term_type,
                code=code,
                title=str(payload.get("title") or code),
                created_at=now,
                updated_at=now,
                created_by=actor_id,
            )
            self.session.add(row)
        row.title = str(payload.get("title") or row.title or code)
        row.description = _text(payload.get("description"))
        row.parent_term_id = _text(payload.get("parent_term_id"))
        row.visibility = visibility
        row.status = status
        row.sort_order = int(payload.get("sort_order") or row.sort_order or 0)
        row.metadata_json = _dict(payload.get("metadata") or payload.get("metadata_json"))
        row.updated_at = now
        row.updated_by = actor_id
        await self.session.flush()
        return serialize_taxonomy_term(row)

    async def upsert_property_definition(self, payload: dict[str, Any], *, actor_id: str | None, actor_role: str) -> dict[str, Any]:
        space_id = str(payload.get("space_id") or "")
        space = await self._space(space_id)
        self._assert_space_mutable(space, actor_role=actor_role)
        code = normalize_knowledge_slug(payload.get("code") or payload.get("title"))
        value_type = str(payload.get("value_type") or "text")
        if value_type not in PROPERTY_VALUE_TYPES:
            raise KnowledgeValidationError("unsupported property value_type")
        status = str(payload.get("status") or "active")
        if status not in {"active", "draft", "archived"}:
            raise KnowledgeValidationError("unsupported property status")
        now = datetime.now(timezone.utc)
        row = (
            await self.session.execute(
                select(KnowledgePropertyDefinition).where(
                    KnowledgePropertyDefinition.space_id == space_id,
                    KnowledgePropertyDefinition.code == code,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = KnowledgePropertyDefinition(
                property_id=str(payload.get("property_id") or _new_id()),
                space_id=space_id,
                code=code,
                title=str(payload.get("title") or code),
                created_at=now,
                updated_at=now,
                created_by=actor_id,
            )
            self.session.add(row)
        row.title = str(payload.get("title") or row.title or code)
        row.description = _text(payload.get("description"))
        row.value_type = value_type
        row.required = bool(payload.get("required", row.required))
        row.allowed_values_json = _list(payload.get("allowed_values") or payload.get("allowed_values_json"))
        row.applies_to_item_types_json = _list(payload.get("applies_to_item_types") or payload.get("applies_to_item_types_json"))
        row.quality_weight = max(0, int(payload.get("quality_weight") or 0))
        row.status = status
        row.metadata_json = _dict(payload.get("metadata") or payload.get("metadata_json"))
        row.updated_at = now
        row.updated_by = actor_id
        await self.session.flush()
        return serialize_property_definition(row)

    def _validate_property_value(self, definition: KnowledgePropertyDefinition, value: Any) -> Any:
        value_type = definition.value_type
        allowed = _list(definition.allowed_values_json)
        if value_type == "text" or value_type == "url" or value_type == "date":
            return str(value).strip()
        if value_type == "number":
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise KnowledgeValidationError(f"invalid number for property {definition.code}") from exc
        if value_type == "boolean":
            if isinstance(value, bool):
                return value
            if str(value).lower() in {"true", "1", "yes"}:
                return True
            if str(value).lower() in {"false", "0", "no"}:
                return False
            raise KnowledgeValidationError(f"invalid boolean for property {definition.code}")
        if value_type == "select":
            text = str(value).strip()
            if allowed and text not in {str(item) for item in allowed}:
                raise KnowledgeValidationError(f"unsupported value for property {definition.code}")
            return text
        if value_type == "multi_select":
            values = [str(item).strip() for item in _list(value) if str(item).strip()]
            if allowed:
                allowed_set = {str(item) for item in allowed}
                invalid = [item for item in values if item not in allowed_set]
                if invalid:
                    raise KnowledgeValidationError(f"unsupported value for property {definition.code}")
            return values
        return value

    async def update_item_metadata(
        self,
        item_ref: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> dict[str, Any]:
        item = await self._item(item_ref, actor_role=actor_role)
        if not can_mutate_knowledge_visibility(actor_role, item.visibility):
            raise KnowledgeValidationError("actor cannot mutate this knowledge item")
        definitions = (
            await self.session.execute(
                select(KnowledgePropertyDefinition).where(
                    KnowledgePropertyDefinition.space_id == item.space_id,
                    KnowledgePropertyDefinition.status != "archived",
                )
            )
        ).scalars().all()
        by_code = {row.code: row for row in definitions}
        values = _dict(payload.get("properties"))
        now = datetime.now(timezone.utc)
        await self.session.execute(delete(KnowledgeItemPropertyValue).where(KnowledgeItemPropertyValue.item_id == item.item_id))
        for code, raw_value in values.items():
            definition = by_code.get(str(code))
            if definition is None:
                raise KnowledgeValidationError(f"unknown property: {code}")
            item_types = _list(definition.applies_to_item_types_json)
            if item_types and item.item_type not in {str(entry) for entry in item_types}:
                raise KnowledgeValidationError(f"property does not apply to item type: {code}")
            self.session.add(
                KnowledgeItemPropertyValue(
                    item_property_id=_new_id(),
                    item_id=item.item_id,
                    property_id=definition.property_id,
                    value_json={"value": self._validate_property_value(definition, raw_value)},
                    created_at=now,
                    updated_at=now,
                    updated_by=actor_id,
                )
            )
        term_ids = [str(term_id) for term_id in _list(payload.get("taxonomy_term_ids")) if str(term_id).strip()]
        if term_ids:
            rows = (
                await self.session.execute(
                    select(KnowledgeTaxonomyTerm).where(
                        KnowledgeTaxonomyTerm.term_id.in_(term_ids),
                        KnowledgeTaxonomyTerm.space_id == item.space_id,
                        KnowledgeTaxonomyTerm.status != "archived",
                    )
                )
            ).scalars().all()
            found = {row.term_id for row in rows}
            missing = [term_id for term_id in term_ids if term_id not in found]
            if missing:
                raise KnowledgeValidationError("unknown taxonomy term for item space")
        await self.session.execute(delete(KnowledgeItemTaxonomyTerm).where(KnowledgeItemTaxonomyTerm.item_id == item.item_id))
        for term_id in term_ids:
            self.session.add(
                KnowledgeItemTaxonomyTerm(
                    item_term_id=_new_id(),
                    item_id=item.item_id,
                    term_id=term_id,
                    created_at=now,
                    created_by=actor_id,
                )
            )
        item.updated_at = now
        item.updated_by = actor_id
        await self.session.flush()
        return await self.item_metadata(item.item_id, actor_role=actor_role)

    async def replace_applicability_rules(
        self,
        item_ref: str,
        rules: list[dict[str, Any]],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> list[dict[str, Any]]:
        item = await self._item(item_ref, actor_role=actor_role)
        if not can_mutate_knowledge_visibility(actor_role, item.visibility):
            raise KnowledgeValidationError("actor cannot mutate this knowledge item")
        now = datetime.now(timezone.utc)
        await self.session.execute(delete(KnowledgeApplicabilityRule).where(KnowledgeApplicabilityRule.item_id == item.item_id))
        for raw in rules:
            scope_type = str(raw.get("scope_type") or "")
            if scope_type not in APPLICABILITY_SCOPE_TYPES:
                raise KnowledgeValidationError("unsupported applicability scope_type")
            scope_ref = _text(raw.get("scope_ref"))
            if not scope_ref:
                raise KnowledgeValidationError("applicability scope_ref is required")
            include_mode = str(raw.get("include_mode") or "include")
            if include_mode not in APPLICABILITY_INCLUDE_MODES:
                raise KnowledgeValidationError("unsupported applicability include_mode")
            self.session.add(
                KnowledgeApplicabilityRule(
                    rule_id=str(raw.get("rule_id") or _new_id()),
                    item_id=item.item_id,
                    scope_type=scope_type,
                    scope_ref=scope_ref,
                    include_mode=include_mode,
                    priority=int(raw.get("priority") or 100),
                    conditions_json=_dict(raw.get("conditions") or raw.get("conditions_json")),
                    metadata_json=_dict(raw.get("metadata") or raw.get("metadata_json")),
                    created_at=now,
                    updated_at=now,
                    created_by=actor_id,
                    updated_by=actor_id,
                )
            )
        item.updated_at = now
        item.updated_by = actor_id
        await self.session.flush()
        return await self.item_applicability_rules(item.item_id, actor_role=actor_role)

    async def upsert_quality_model(self, payload: dict[str, Any], *, actor_id: str | None, actor_role: str) -> dict[str, Any]:
        space_id = _text(payload.get("space_id"))
        if space_id:
            space = await self._space(space_id)
            self._assert_space_mutable(space, actor_role=actor_role)
        elif str(actor_role or "").lower() not in {"admin", "security"}:
            raise KnowledgeValidationError("global quality model requires admin")
        code = normalize_knowledge_slug(payload.get("code") or payload.get("title"))
        status = str(payload.get("status") or "active")
        if status not in {"active", "draft", "archived"}:
            raise KnowledgeValidationError("unsupported quality model status")
        weights = _dict(payload.get("weights") or payload.get("weights_json"))
        for key, value in weights.items():
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise KnowledgeValidationError(f"invalid quality model weight: {key}") from exc
            if number < 0:
                raise KnowledgeValidationError(f"invalid quality model weight: {key}")
            weights[key] = int(number) if number.is_integer() else number
        now = datetime.now(timezone.utc)
        row = (
            await self.session.execute(
                select(KnowledgeQualityModel).where(
                    KnowledgeQualityModel.space_id.is_(None) if space_id is None else KnowledgeQualityModel.space_id == space_id,
                    KnowledgeQualityModel.code == code,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = KnowledgeQualityModel(
                model_id=str(payload.get("model_id") or _new_id()),
                space_id=space_id,
                code=code,
                title=str(payload.get("title") or code),
                created_at=now,
                updated_at=now,
                created_by=actor_id,
            )
            self.session.add(row)
        row.title = str(payload.get("title") or row.title or code)
        row.weights_json = weights
        row.thresholds_json = _dict(payload.get("thresholds") or payload.get("thresholds_json"))
        row.status = status
        row.is_default = bool(payload.get("is_default", row.is_default))
        row.metadata_json = _dict(payload.get("metadata") or payload.get("metadata_json"))
        row.updated_at = now
        row.updated_by = actor_id
        if row.is_default:
            await self.session.execute(
                update(KnowledgeQualityModel)
                .where(
                    KnowledgeQualityModel.model_id != row.model_id,
                    KnowledgeQualityModel.space_id.is_(None) if space_id is None else KnowledgeQualityModel.space_id == space_id,
                )
                .values(is_default=False)
            )
        await self.session.flush()
        return serialize_quality_model(row)

    async def quality_model_for_space(self, space_id: str | None) -> KnowledgeQualityModel | None:
        stmt = (
            select(KnowledgeQualityModel)
            .where(KnowledgeQualityModel.status == "active")
            .order_by(KnowledgeQualityModel.is_default.desc(), KnowledgeQualityModel.updated_at.desc())
        )
        if space_id:
            scoped = (
                await self.session.execute(
                    select(KnowledgeQualityModel)
                    .where(
                        KnowledgeQualityModel.space_id == space_id,
                        KnowledgeQualityModel.status == "active",
                    )
                    .order_by(KnowledgeQualityModel.is_default.desc(), KnowledgeQualityModel.updated_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if scoped is not None:
                return scoped
        return (await self.session.execute(stmt.where(KnowledgeQualityModel.space_id.is_(None)).limit(1))).scalar_one_or_none()

    async def item_metadata(self, item_ref: str, *, actor_role: str) -> dict[str, Any]:
        item = await self._item(item_ref, actor_role=actor_role)
        property_rows = (
            await self.session.execute(
                select(KnowledgeItemPropertyValue, KnowledgePropertyDefinition)
                .join(KnowledgePropertyDefinition, KnowledgePropertyDefinition.property_id == KnowledgeItemPropertyValue.property_id)
                .where(KnowledgeItemPropertyValue.item_id == item.item_id)
                .order_by(KnowledgePropertyDefinition.code.asc())
            )
        ).all()
        term_rows = (
            await self.session.execute(
                select(KnowledgeTaxonomyTerm)
                .join(KnowledgeItemTaxonomyTerm, KnowledgeItemTaxonomyTerm.term_id == KnowledgeTaxonomyTerm.term_id)
                .where(KnowledgeItemTaxonomyTerm.item_id == item.item_id)
                .order_by(KnowledgeTaxonomyTerm.term_type.asc(), KnowledgeTaxonomyTerm.code.asc())
            )
        ).scalars().all()
        rules = await self.item_applicability_rules(item.item_id, actor_role=actor_role)
        return {
            "item_id": item.item_id,
            "space_id": item.space_id,
            "slug": item.slug,
            "title": item.title,
            "properties": {definition.code: _json_value(value) for value, definition in property_rows},
            "property_values": [
                {
                    "item_property_id": value.item_property_id,
                    "property_id": definition.property_id,
                    "code": definition.code,
                    "title": definition.title,
                    "value": _json_value(value),
                    "updated_at": _iso(value.updated_at),
                    "updated_by": value.updated_by,
                }
                for value, definition in property_rows
            ],
            "taxonomy_terms": [serialize_taxonomy_term(row) for row in term_rows],
            "applicability_rules": rules,
        }

    async def item_applicability_rules(self, item_ref: str, *, actor_role: str) -> list[dict[str, Any]]:
        item = await self._item(item_ref, actor_role=actor_role)
        rows = (
            await self.session.execute(
                select(KnowledgeApplicabilityRule)
                .where(KnowledgeApplicabilityRule.item_id == item.item_id)
                .order_by(KnowledgeApplicabilityRule.priority.asc(), KnowledgeApplicabilityRule.scope_type.asc())
            )
        ).scalars().all()
        return [serialize_applicability_rule(row) for row in rows]

    async def bundle(self, *, actor_role: str) -> dict[str, Any]:
        allowed = set(actor_visible_visibilities(actor_role))
        spaces = (
            await self.session.execute(
                select(KnowledgeSpace)
                .where(KnowledgeSpace.visibility.in_(allowed))
                .order_by(KnowledgeSpace.code.asc())
            )
        ).scalars().all()
        space_ids = [row.space_id for row in spaces]
        terms = []
        properties = []
        quality_models = []
        if space_ids:
            terms = (
                await self.session.execute(
                    select(KnowledgeTaxonomyTerm)
                    .where(KnowledgeTaxonomyTerm.space_id.in_(space_ids), KnowledgeTaxonomyTerm.visibility.in_(allowed))
                    .order_by(KnowledgeTaxonomyTerm.term_type.asc(), KnowledgeTaxonomyTerm.code.asc())
                )
            ).scalars().all()
            properties = (
                await self.session.execute(
                    select(KnowledgePropertyDefinition)
                    .where(KnowledgePropertyDefinition.space_id.in_(space_ids))
                    .order_by(KnowledgePropertyDefinition.code.asc())
                )
            ).scalars().all()
            quality_models = (
                await self.session.execute(
                    select(KnowledgeQualityModel)
                    .where(or_(KnowledgeQualityModel.space_id.in_(space_ids), KnowledgeQualityModel.space_id.is_(None)))
                    .order_by(KnowledgeQualityModel.is_default.desc(), KnowledgeQualityModel.code.asc())
                )
            ).scalars().all()
        items = (
            await self.session.execute(
                select(KnowledgeItem)
                .where(KnowledgeItem.visibility.in_(allowed))
                .order_by(KnowledgeItem.updated_at.desc())
                .limit(100)
            )
        ).scalars().all()
        item_metadata = [await self.item_metadata(row.item_id, actor_role=actor_role) for row in items]
        rules = [rule for item in item_metadata for rule in item["applicability_rules"]]
        return {
            "spaces": [
                {
                    "space_id": row.space_id,
                    "code": row.code,
                    "title": row.title,
                    "visibility": row.visibility,
                    "lifecycle_status": row.lifecycle_status,
                }
                for row in spaces
            ],
            "taxonomy_terms": [serialize_taxonomy_term(row) for row in terms],
            "property_definitions": [serialize_property_definition(row) for row in properties],
            "applicability_rules": rules,
            "quality_models": [serialize_quality_model(row) for row in quality_models],
            "item_metadata": item_metadata,
        }
