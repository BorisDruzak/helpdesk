from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgeApplicabilityRule,
    KnowledgeBinding,
    KnowledgeFeedbackEvent,
    KnowledgeItem,
    KnowledgeItemPropertyValue,
    KnowledgeItemTaxonomyTerm,
    KnowledgeItemVersion,
    KnowledgePropertyDefinition,
    KnowledgeQualityModel,
    KnowledgeQualitySnapshot,
)
from knowledge.content_lint import lint_knowledge_content
from knowledge.metadata_service import serialize_quality_model


def _new_id() -> str:
    return str(uuid.uuid4())


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _issue(severity: str, code: str, message: str, suggested_fix: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message, "suggested_fix": suggested_fix}


class KnowledgeQualityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _builtin_quality_model(self) -> dict[str, Any]:
        return {
            "model_id": None,
            "space_id": None,
            "code": "builtin-default",
            "title": "Built-in quality model",
            "weights": {},
            "thresholds": {"good": 80, "review": 70},
            "status": "active",
            "is_default": True,
        }

    async def _active_quality_model(self, space_id: str | None) -> KnowledgeQualityModel | None:
        if space_id:
            scoped = (
                await self.session.execute(
                    select(KnowledgeQualityModel)
                    .where(KnowledgeQualityModel.space_id == space_id, KnowledgeQualityModel.status == "active")
                    .order_by(KnowledgeQualityModel.is_default.desc(), KnowledgeQualityModel.updated_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if scoped is not None:
                return scoped
        return (
            await self.session.execute(
                select(KnowledgeQualityModel)
                .where(KnowledgeQualityModel.space_id.is_(None), KnowledgeQualityModel.status == "active")
                .order_by(KnowledgeQualityModel.is_default.desc(), KnowledgeQualityModel.updated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def _metadata_dimensions(self, item: KnowledgeItem, model: KnowledgeQualityModel | None) -> tuple[dict[str, int], list[dict[str, str]]]:
        if model is None:
            return {}, []
        weights = model.weights_json if isinstance(model.weights_json, dict) else {}
        property_weight = max(0, int(weights.get("properties") or 0))
        taxonomy_weight = max(0, int(weights.get("taxonomy") or 0))
        applicability_weight = max(0, int(weights.get("applicability") or 0))
        dimensions: dict[str, int] = {}
        issues: list[dict[str, str]] = []

        if property_weight:
            definitions = (
                await self.session.execute(
                    select(KnowledgePropertyDefinition).where(
                        KnowledgePropertyDefinition.space_id == item.space_id,
                        KnowledgePropertyDefinition.status == "active",
                    )
                )
            ).scalars().all()
            values = (
                await self.session.execute(
                    select(KnowledgeItemPropertyValue).where(KnowledgeItemPropertyValue.item_id == item.item_id)
                )
            ).scalars().all()
            value_property_ids = {row.property_id for row in values}
            applicable_definitions = [
                definition
                for definition in definitions
                if not definition.applies_to_item_types_json or item.item_type in {str(entry) for entry in definition.applies_to_item_types_json}
            ]
            missing_required = [definition for definition in applicable_definitions if definition.required and definition.property_id not in value_property_ids]
            if missing_required:
                dimensions["properties"] = 0
                for definition in missing_required:
                    issues.append(
                        _issue(
                            "error",
                            f"missing_required_property:{definition.code}",
                            "Required knowledge property is missing.",
                            "Set the required property before publishing or signoff.",
                        )
                    )
            elif value_property_ids:
                dimensions["properties"] = property_weight
            else:
                dimensions["properties"] = 0
                issues.append(
                    _issue(
                        "warning",
                        "missing_properties",
                        "No governed properties are attached.",
                        "Attach applicable metadata properties.",
                    )
                )

        if taxonomy_weight:
            taxonomy_count = (
                await self.session.execute(
                    select(func.count(KnowledgeItemTaxonomyTerm.item_term_id)).where(
                        KnowledgeItemTaxonomyTerm.item_id == item.item_id
                    )
                )
            ).scalar_one()
            if int(taxonomy_count or 0):
                dimensions["taxonomy"] = taxonomy_weight
            else:
                dimensions["taxonomy"] = 0
                issues.append(_issue("warning", "missing_taxonomy", "No taxonomy term is attached.", "Attach at least one taxonomy term."))

        if applicability_weight:
            applicability_count = (
                await self.session.execute(
                    select(func.count(KnowledgeApplicabilityRule.rule_id)).where(KnowledgeApplicabilityRule.item_id == item.item_id)
                )
            ).scalar_one()
            if int(applicability_count or 0):
                dimensions["applicability"] = applicability_weight
            else:
                dimensions["applicability"] = 0
                issues.append(
                    _issue("warning", "missing_applicability", "No applicability rule is defined.", "Add include/exclude applicability rules.")
                )

        return dimensions, issues

    async def score_item(self, item_id_or_slug: str, *, store_snapshot: bool = False) -> dict[str, Any]:
        item = (
            await self.session.execute(
                select(KnowledgeItem).where((KnowledgeItem.item_id == item_id_or_slug) | (KnowledgeItem.slug == item_id_or_slug))
            )
        ).scalar_one_or_none()
        if item is None:
            raise ValueError("knowledge item not found")
        version = None
        if item.current_version_id:
            version = (
                await self.session.execute(select(KnowledgeItemVersion).where(KnowledgeItemVersion.version_id == item.current_version_id))
            ).scalar_one_or_none()
        if version is None:
            version = (
                await self.session.execute(
                    select(KnowledgeItemVersion).where(KnowledgeItemVersion.item_id == item.item_id).order_by(KnowledgeItemVersion.version_number.desc())
                )
            ).scalars().first()

        bindings = (
            await self.session.execute(select(KnowledgeBinding).where(KnowledgeBinding.item_id == item.item_id))
        ).scalars().all()
        feedback_rows = (
            await self.session.execute(
                select(KnowledgeFeedbackEvent.event_type, func.count(KnowledgeFeedbackEvent.event_id))
                .where(KnowledgeFeedbackEvent.item_id == item.item_id)
                .group_by(KnowledgeFeedbackEvent.event_type)
            )
        ).all()
        feedback = {event_type: int(count) for event_type, count in feedback_rows}
        body = str(version.body if version is not None else "")
        source_refs = version.source_refs if version is not None else []

        issues: list[dict[str, str]] = []
        dimensions = {
            "completeness": 0,
            "governance": 0,
            "safety": 20,
            "usefulness": 10,
            "freshness": 0,
            "coverage": 0,
        }

        if item.title and item.summary and body.strip():
            dimensions["completeness"] += 12
        else:
            issues.append(_issue("error", "incomplete_content", "Title, summary and body are required.", "Complete title, summary and body."))
        if len(body.split()) >= 20:
            dimensions["completeness"] += 5
        if item.tags:
            dimensions["completeness"] += 3

        if item.owner_actor_id:
            dimensions["governance"] += 5
        else:
            issues.append(_issue("error", "missing_owner", "Owner is missing.", "Assign an owner."))
        if item.reviewer_actor_id:
            dimensions["governance"] += 5
        else:
            issues.append(_issue("error", "missing_reviewer", "Reviewer is missing.", "Assign a reviewer."))
        if item.status == "published":
            dimensions["governance"] += 3
        else:
            issues.append(_issue("warning", f"status_{item.status}", "Item is not published.", "Publish after review if useful."))
        if source_refs:
            dimensions["governance"] += 2

        lint = lint_knowledge_content(
            item_type=item.item_type,
            visibility=item.visibility,
            title=item.title,
            summary=item.summary,
            body=body,
            owner_actor_id=item.owner_actor_id,
            reviewer_actor_id=item.reviewer_actor_id,
            review_due_at=item.review_due_at,
            bindings=[{"service_code": row.service_code, "offering_code": row.offering_code} for row in bindings],
            source_refs=source_refs,
            metadata=item.metadata_json if isinstance(item.metadata_json, dict) else {},
        )
        if lint["errors"]:
            dimensions["safety"] = max(0, dimensions["safety"] - 15)
            issues.extend(lint["errors"])
        issues.extend(lint["warnings"])

        helpful = feedback.get("helpful", 0) + feedback.get("deflected", 0)
        support_used = feedback.get("support_used", 0)
        not_helpful = feedback.get("not_helpful", 0)
        dimensions["usefulness"] += min(8, helpful * 2 + support_used * 2)
        if not_helpful:
            dimensions["usefulness"] = max(0, dimensions["usefulness"] - min(12, not_helpful * 4))
            issues.append(_issue("warning", "not_helpful_feedback", "Users marked this content as not helpful.", "Review wording, scope and troubleshooting steps."))

        now = datetime.now(timezone.utc)
        if item.review_due_at and item.review_due_at > now:
            dimensions["freshness"] += 10
        elif item.review_due_at and item.review_due_at <= now:
            issues.append(_issue("warning", "review_overdue", "Review due date has passed.", "Review and set a new review due date."))
        else:
            issues.append(_issue("error", "missing_review_due", "Review due date is missing.", "Set review_due_at."))
        if item.updated_at:
            dimensions["freshness"] += 2

        if bindings:
            dimensions["coverage"] += 10
        else:
            issues.append(_issue("warning", "missing_binding", "No Service Catalog binding.", "Bind to service/offering if applicable."))
        if item.item_type in {"article", "faq", "runbook", "known_error", "workaround", "glossary_term"}:
            dimensions["coverage"] += 5

        quality_model = await self._active_quality_model(item.space_id)
        metadata_dimensions, metadata_issues = await self._metadata_dimensions(item, quality_model)
        dimensions.update(metadata_dimensions)
        issues.extend(metadata_issues)

        score = max(0, min(100, int(sum(dimensions.values()))))
        result = {
            "item_id": item.item_id,
            "version_id": version.version_id if version is not None else None,
            "slug": item.slug,
            "title": item.title,
            "visibility": item.visibility,
            "status": item.status,
            "review_due_at": item.review_due_at.isoformat() if item.review_due_at else None,
            "score": score,
            "grade": _grade(score),
            "dimensions": dimensions,
            "issues": issues,
            "feedback": feedback,
            "quality_model": serialize_quality_model(quality_model) if quality_model is not None else self._builtin_quality_model(),
            "computed_at": now.isoformat(),
        }
        if store_snapshot:
            self.session.add(
                KnowledgeQualitySnapshot(
                    snapshot_id=_new_id(),
                    item_id=item.item_id,
                    version_id=result["version_id"],
                    score=score,
                    grade=result["grade"],
                    dimensions_json=dimensions,
                    issues_json=issues,
                    computed_at=now,
                )
            )
            await self.session.flush()
        return result

    async def summary(self, *, actor_role: str = "admin") -> dict[str, Any]:
        from knowledge.contracts import actor_visible_visibilities

        rows = (
            await self.session.execute(
                select(KnowledgeItem).where(KnowledgeItem.visibility.in_(set(actor_visible_visibilities(actor_role)))).order_by(KnowledgeItem.updated_at.desc())
            )
        ).scalars().all()
        items = [await self.score_item(row.item_id) for row in rows]
        quality_model = next((item.get("quality_model") for item in items if item.get("quality_model")), self._builtin_quality_model())
        return {
            "items": items,
            "quality_model": quality_model,
            "average_quality_score": (sum(item["score"] for item in items) / len(items)) if items else 0.0,
            "low_quality_count": sum(1 for item in items if item["score"] < 70),
        }
