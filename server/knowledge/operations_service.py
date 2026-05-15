from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    HelpdeskService,
    HelpdeskServiceOffering,
    KnowledgeBinding,
    KnowledgeFeedbackEvent,
    KnowledgeItem,
    KnowledgeItemVersion,
    KnowledgeRolloutPolicy,
    Ticket,
)
from app.repos.knowledge_repo import serialize_item
from knowledge.contracts import actor_visible_visibilities, lint_requester_safe_publication


def _new_id() -> str:
    return str(uuid.uuid4())


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


CONTENT_TEMPLATES: tuple[dict[str, Any], ...] = (
    {"type": "article", "title": "Пошаговая статья", "sections": ["Когда использовать", "Шаги", "Если не помогло"]},
    {"type": "faq", "title": "FAQ", "sections": ["Вопрос", "Короткий ответ", "Связанные услуги"]},
    {"type": "runbook", "title": "Support runbook", "sections": ["Симптомы", "Проверки", "Действия", "Escalation"]},
    {"type": "known_error", "title": "Known error", "sections": ["Ошибка", "Причина", "Workaround", "Permanent fix"]},
    {"type": "workaround", "title": "Workaround", "sections": ["Когда применять", "Шаги", "Риски"]},
    {"type": "service_description", "title": "Описание услуги", "sections": ["Что входит", "Сроки", "Ограничения"]},
)


class KnowledgeOperationsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def review_queue(self, *, actor_role: str = "admin") -> dict[str, Any]:
        allowed = set(actor_visible_visibilities(actor_role))
        now = datetime.now(timezone.utc)
        rows = (
            await self.session.execute(
                select(KnowledgeItem)
                .where(KnowledgeItem.visibility.in_(allowed))
                .order_by(KnowledgeItem.review_due_at.asc().nulls_last(), KnowledgeItem.updated_at.desc())
            )
        ).scalars().all()
        items: list[dict[str, Any]] = []
        for row in rows:
            reason = None
            if row.status in {"draft", "in_review", "needs_review"}:
                reason = row.status
            elif row.review_due_at and row.review_due_at <= now:
                reason = "review_overdue"
            metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
            if metadata.get("review_required"):
                reason = "review_required"
            if reason:
                items.append({**serialize_item(row), "reason": reason})
        return {"items": items, "count": len(items)}

    async def review_action(self, item_id_or_slug: str, *, action: str, actor_id: str | None, note: str | None = None) -> dict[str, Any]:
        item = (
            await self.session.execute(
                select(KnowledgeItem).where((KnowledgeItem.item_id == item_id_or_slug) | (KnowledgeItem.slug == item_id_or_slug))
            )
        ).scalar_one_or_none()
        if item is None:
            raise ValueError("knowledge item not found")
        metadata = dict(item.metadata_json or {})
        metadata.setdefault("review_events", []).append(
            {"action": action, "actor_id": actor_id, "note": note, "created_at": datetime.now(timezone.utc).isoformat()}
        )
        if action == "submit_review":
            item.status = "in_review"
        elif action == "approve":
            metadata["review_required"] = False
        elif action == "request_changes":
            item.status = "draft"
            metadata["review_required"] = True
        elif action == "mark_needs_review":
            item.status = "needs_review"
            metadata["review_required"] = True
        elif action in {"archive", "retire"}:
            item.status = "archived"
            item.archived_at = datetime.now(timezone.utc)
        else:
            raise ValueError("unsupported review action")
        item.metadata_json = metadata
        item.updated_at = datetime.now(timezone.utc)
        item.updated_by = actor_id
        await self.session.flush()
        return {"item": serialize_item(item), "event": metadata["review_events"][-1]}

    async def quality_summary(self, *, actor_role: str = "admin") -> dict[str, Any]:
        allowed = set(actor_visible_visibilities(actor_role))
        rows = (
            await self.session.execute(
                select(KnowledgeItem)
                .where(KnowledgeItem.visibility.in_(allowed))
                .order_by(KnowledgeItem.updated_at.desc())
            )
        ).scalars().all()
        items = [await self._score_item(row) for row in rows]
        return {"items": items, "average_quality_score": (sum(item["quality_score"] for item in items) / len(items)) if items else 0.0}

    async def _score_item(self, item: KnowledgeItem) -> dict[str, Any]:
        score = 35
        issues: list[str] = []
        version = None
        if item.current_version_id:
            version = (
                await self.session.execute(select(KnowledgeItemVersion).where(KnowledgeItemVersion.version_id == item.current_version_id))
            ).scalar_one_or_none()
        bindings = (
            await self.session.execute(select(func.count(KnowledgeBinding.binding_id)).where(KnowledgeBinding.item_id == item.item_id))
        ).scalar_one()
        feedback_rows = (
            await self.session.execute(
                select(KnowledgeFeedbackEvent.event_type, func.count(KnowledgeFeedbackEvent.event_id))
                .where(KnowledgeFeedbackEvent.item_id == item.item_id)
                .group_by(KnowledgeFeedbackEvent.event_type)
            )
        ).all()
        feedback = {event_type: int(count) for event_type, count in feedback_rows}
        if item.status == "published":
            score += 15
        else:
            issues.append(f"status_{item.status}")
        if version is not None and str(version.body or "").strip():
            score += 15
            if len(str(version.body).split()) >= 20:
                score += 5
        else:
            issues.append("missing_published_body")
        if item.reviewer_actor_id:
            score += 10
        else:
            issues.append("missing_reviewer")
        if bindings:
            score += 10
        else:
            issues.append("missing_binding")
        if item.review_due_at and item.review_due_at <= datetime.now(timezone.utc):
            score -= 20
            issues.append("review_overdue")
        helpful = feedback.get("helpful", 0)
        not_helpful = feedback.get("not_helpful", 0)
        score += min(10, helpful * 2)
        if not_helpful:
            score -= min(20, not_helpful * 5)
            issues.append("not_helpful_feedback")
        lint = lint_requester_safe_publication(
            visibility=item.visibility,
            title=item.title,
            summary=item.summary,
            body=version.body if version is not None else "",
            metadata=item.metadata_json if isinstance(item.metadata_json, dict) else {},
        )
        if lint:
            score -= 30
            issues.extend(blocker["code"] for blocker in lint)
        return {
            "item_id": item.item_id,
            "slug": item.slug,
            "title": item.title,
            "visibility": item.visibility,
            "status": item.status,
            "quality_score": max(0, min(100, int(score))),
            "issues": sorted(set(issues)),
            "review_due_at": _iso(item.review_due_at),
            "feedback": feedback,
        }

    async def detect_gaps(self, *, actor_role: str = "admin") -> dict[str, Any]:
        services = (
            await self.session.execute(select(HelpdeskService).where(HelpdeskService.lifecycle_status == "published", HelpdeskService.visibility == "public"))
        ).scalars().all()
        offerings = (
            await self.session.execute(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.lifecycle_status == "published", HelpdeskServiceOffering.visibility == "public"))
        ).scalars().all()
        service_by_id = {service.service_id: service for service in services}
        gaps: list[dict[str, Any]] = []
        for offering in offerings:
            service = service_by_id.get(offering.service_id)
            if service is None:
                continue
            has_knowledge = await self._has_requester_safe_binding(service.code, offering.full_code)
            ticket_count = (
                await self.session.execute(select(func.count(Ticket.ticket_id)).where(Ticket.service_code == service.code, Ticket.offering_code == offering.full_code))
            ).scalar_one()
            feedback_counts = await self._feedback_counts(service.code, offering.full_code)
            if not has_knowledge:
                gaps.append(
                    {
                        "gap_type": "missing_requester_safe_knowledge",
                        "service_code": service.code,
                        "offering_code": offering.full_code,
                        "service_title": service.public_title or service.name,
                        "offering_title": offering.public_title or offering.name,
                        "ticket_count": int(ticket_count),
                        "ticket_created_after_view_count": feedback_counts.get("ticket_created_after_view", 0),
                        "not_helpful_count": feedback_counts.get("not_helpful", 0),
                        "severity": "high" if ticket_count or feedback_counts else "medium",
                    }
                )
        return {"gaps": gaps, "count": len(gaps)}

    async def _has_requester_safe_binding(self, service_code: str, offering_code: str) -> bool:
        row = (
            await self.session.execute(
                select(KnowledgeItem.item_id)
                .join(KnowledgeBinding, KnowledgeBinding.item_id == KnowledgeItem.item_id)
                .where(
                    KnowledgeItem.status == "published",
                    KnowledgeItem.visibility.in_(("public", "requester", "agent_requester_safe")),
                    KnowledgeBinding.service_code == service_code,
                    KnowledgeBinding.offering_code == offering_code,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return row is not None

    async def _feedback_counts(self, service_code: str | None, offering_code: str | None) -> dict[str, int]:
        rows = (
            await self.session.execute(
                select(KnowledgeFeedbackEvent.event_type, func.count(KnowledgeFeedbackEvent.event_id))
                .where(KnowledgeFeedbackEvent.service_code == service_code, KnowledgeFeedbackEvent.offering_code == offering_code)
                .group_by(KnowledgeFeedbackEvent.event_type)
            )
        ).all()
        return {event_type: int(count) for event_type, count in rows}

    async def upsert_rollout_policy(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        surface = str(payload.get("surface") or "requester_portal")
        service_code = str(payload.get("service_code") or "").strip() or None
        offering_code = str(payload.get("offering_code") or "").strip() or None
        request_template_key = str(payload.get("request_template_key") or "").strip() or None
        row = (
            await self.session.execute(
                select(KnowledgeRolloutPolicy).where(
                    KnowledgeRolloutPolicy.service_code.is_(None) if service_code is None else KnowledgeRolloutPolicy.service_code == service_code,
                    KnowledgeRolloutPolicy.offering_code.is_(None) if offering_code is None else KnowledgeRolloutPolicy.offering_code == offering_code,
                    KnowledgeRolloutPolicy.request_template_key.is_(None) if request_template_key is None else KnowledgeRolloutPolicy.request_template_key == request_template_key,
                    KnowledgeRolloutPolicy.surface == surface,
                )
            )
        ).scalars().first()
        if row is None:
            row = KnowledgeRolloutPolicy(policy_id=_new_id(), service_code=service_code, offering_code=offering_code, request_template_key=request_template_key, surface=surface)
            self.session.add(row)
        row.enabled = bool(payload.get("enabled", True))
        row.rollout_percent = max(0, min(100, int(payload.get("rollout_percent", 100))))
        row.reason = str(payload.get("reason") or "").strip() or None
        row.metadata_json = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        row.updated_at = datetime.now(timezone.utc)
        row.updated_by = actor_id
        await self.session.flush()
        return self._serialize_rollout_policy(row)

    async def rollout_decision(self, context: dict[str, Any], *, actor_role: str) -> dict[str, Any]:
        surface = str(context.get("surface") or context.get("source_surface") or "api")
        if actor_role in {"admin", "support", "auditor", "security"} or surface == "support_workspace":
            return {"enabled": True, "reason": None}
        candidates = [
            (context.get("service_code"), context.get("offering_code"), context.get("request_template_key"), surface),
            (context.get("service_code"), context.get("offering_code"), None, surface),
            (context.get("service_code"), None, None, surface),
            (None, None, None, surface),
        ]
        for service_code, offering_code, request_template_key, candidate_surface in candidates:
            row = (
                await self.session.execute(
                    select(KnowledgeRolloutPolicy).where(
                        KnowledgeRolloutPolicy.service_code.is_(None) if not service_code else KnowledgeRolloutPolicy.service_code == service_code,
                        KnowledgeRolloutPolicy.offering_code.is_(None) if not offering_code else KnowledgeRolloutPolicy.offering_code == offering_code,
                        KnowledgeRolloutPolicy.request_template_key.is_(None) if not request_template_key else KnowledgeRolloutPolicy.request_template_key == request_template_key,
                        KnowledgeRolloutPolicy.surface == candidate_surface,
                    )
                )
            ).scalars().first()
            if row is not None:
                return self._serialize_rollout_policy(row)
        return {"enabled": True, "reason": None}

    async def list_rollout_policies(self) -> dict[str, Any]:
        rows = (await self.session.execute(select(KnowledgeRolloutPolicy).order_by(KnowledgeRolloutPolicy.updated_at.desc()))).scalars().all()
        return {"policies": [self._serialize_rollout_policy(row) for row in rows]}

    def _serialize_rollout_policy(self, row: KnowledgeRolloutPolicy) -> dict[str, Any]:
        return {
            "policy_id": row.policy_id,
            "service_code": row.service_code,
            "offering_code": row.offering_code,
            "request_template_key": row.request_template_key,
            "surface": row.surface,
            "enabled": bool(row.enabled),
            "rollout_percent": int(row.rollout_percent),
            "reason": row.reason,
            "updated_at": _iso(row.updated_at),
            "updated_by": row.updated_by,
        }
