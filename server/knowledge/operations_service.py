from __future__ import annotations

from datetime import datetime, timezone
import hashlib
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
from knowledge.content_templates import CONTENT_TEMPLATES as STRUCTURED_CONTENT_TEMPLATES
from knowledge.contracts import actor_visible_visibilities, lint_requester_safe_publication
from knowledge.gap_service import KnowledgeGapService
from knowledge.quality_service import KnowledgeQualityService


def _new_id() -> str:
    return str(uuid.uuid4())


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


ROLLOUT_SURFACES = {"requester_portal", "agent_gui", "support_workspace", "api", "all"}
NO_SUGGESTIONS_BEHAVIORS = {"allow_submit", "show_message", "block_submit"}
API_UNAVAILABLE_BEHAVIORS = {"allow_submit", "show_warning", "block_submit"}


def _bool(payload: dict[str, Any], key: str, default: bool) -> bool:
    if key not in payload:
        return default
    return bool(payload.get(key))


def _int(payload: dict[str, Any], key: str, default: int) -> int:
    if key not in payload:
        return default
    return int(payload.get(key))


def _rollout_bucket(context: dict[str, Any]) -> int:
    stable = str(
        context.get("session_id")
        or context.get("actor_id")
        or context.get("device_id")
        or context.get("ticket_id")
        or "|".join(
            [
                str(context.get("service_code") or ""),
                str(context.get("offering_code") or ""),
                str(context.get("request_template_key") or ""),
                str(context.get("surface") or context.get("source_surface") or "api"),
            ]
        )
    )
    return int(hashlib.sha256(stable.encode("utf-8")).hexdigest()[:8], 16) % 100 + 1


CONTENT_TEMPLATES: tuple[dict[str, Any], ...] = (
    {"type": "article", "title": "Пошаговая статья", "sections": ["Когда использовать", "Шаги", "Если не помогло"]},
    {"type": "faq", "title": "FAQ", "sections": ["Вопрос", "Короткий ответ", "Связанные услуги"]},
    {"type": "runbook", "title": "Support runbook", "sections": ["Симптомы", "Проверки", "Действия", "Escalation"]},
    {"type": "known_error", "title": "Known error", "sections": ["Ошибка", "Причина", "Workaround", "Permanent fix"]},
    {"type": "workaround", "title": "Workaround", "sections": ["Когда применять", "Шаги", "Риски"]},
    {"type": "service_description", "title": "Описание услуги", "sections": ["Что входит", "Сроки", "Ограничения"]},
)

CONTENT_TEMPLATES = STRUCTURED_CONTENT_TEMPLATES


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
        elif action == "comment":
            pass
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
        summary = await KnowledgeQualityService(self.session).summary(actor_role=actor_role)
        return {
            **summary,
            "items": [{**item, "quality_score": item["score"], "issues": [issue["code"] for issue in item["issues"]]} for item in summary["items"]],
        }

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
        result = await KnowledgeGapService(self.session).recompute(actor_id=None)
        gaps = []
        for finding in result["findings"]:
            if finding["status"] == "dismissed":
                continue
            evidence = finding.get("evidence") or {}
            gaps.append(
                {
                    **finding,
                    "gap_type": "missing_requester_safe_knowledge" if finding["gap_type"] == "no_requester_article" else finding["gap_type"],
                    "ticket_count": int(evidence.get("ticket_count") or 0),
                    "ticket_created_after_view_count": int(evidence.get("ticket_created_after_view_count") or 0),
                    "not_helpful_count": int(evidence.get("not_helpful_count") or 0),
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
        if surface not in ROLLOUT_SURFACES:
            raise ValueError("unsupported rollout surface")
        service_code = str(payload.get("service_code") or "").strip() or None
        offering_code = str(payload.get("offering_code") or "").strip() or None
        request_template_key = str(payload.get("request_template_key") or "").strip() or None
        scope_type = str(payload.get("scope_type") or "").strip() or None
        if scope_type is None:
            if offering_code:
                scope_type = "offering"
            elif service_code:
                scope_type = "service"
            elif request_template_key:
                scope_type = "template"
            else:
                scope_type = "global"
        if scope_type == "global":
            service_code = None
            offering_code = None
            request_template_key = None
        elif scope_type == "service":
            if not service_code:
                raise ValueError("service policy requires service_code")
            offering_code = None
            request_template_key = None
        elif scope_type == "offering":
            if not service_code or not offering_code:
                raise ValueError("offering policy requires service_code and offering_code")
        elif scope_type == "template":
            if not request_template_key:
                raise ValueError("template policy requires request_template_key")
            service_code = None
            offering_code = None
        else:
            raise ValueError("unsupported scope_type")
        min_suggestions = max(0, _int(payload, "min_suggestions", 0))
        max_suggestions = max(0, _int(payload, "max_suggestions", 5))
        if max_suggestions < min_suggestions:
            raise ValueError("max_suggestions must be greater than or equal to min_suggestions")
        no_suggestions_behavior = str(payload.get("no_suggestions_behavior") or "allow_submit")
        api_unavailable_behavior = str(payload.get("api_unavailable_behavior") or "allow_submit")
        if no_suggestions_behavior not in NO_SUGGESTIONS_BEHAVIORS:
            raise ValueError("unsupported no_suggestions_behavior")
        if api_unavailable_behavior not in API_UNAVAILABLE_BEHAVIORS:
            raise ValueError("unsupported api_unavailable_behavior")
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
            row = KnowledgeRolloutPolicy(
                policy_id=_new_id(),
                service_code=service_code,
                offering_code=offering_code,
                request_template_key=request_template_key,
                scope_type=scope_type,
                surface=surface,
            )
            self.session.add(row)
        row.scope_type = scope_type
        row.enabled = bool(payload.get("enabled", True))
        row.rollout_percent = max(0, min(100, int(payload.get("rollout_percent", 100))))
        row.reason = str(payload.get("reason") or "").strip() or None
        row.metadata_json = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        row.show_before_form = _bool(payload, "show_before_form", True)
        row.show_after_form = _bool(payload, "show_after_form", False)
        row.require_suggestions_before_submit = _bool(payload, "require_suggestions_before_submit", False)
        row.allow_skip = _bool(payload, "allow_skip", True)
        row.urgency_bypass = _bool(payload, "urgency_bypass", True)
        row.impact_bypass = _bool(payload, "impact_bypass", True)
        row.min_suggestions = min_suggestions
        row.max_suggestions = max_suggestions
        row.deflection_prompt_enabled = _bool(payload, "deflection_prompt_enabled", True)
        row.feedback_required_on_article_view = _bool(payload, "feedback_required_on_article_view", False)
        row.show_known_errors = _bool(payload, "show_known_errors", True)
        row.show_quality_badge = _bool(payload, "show_quality_badge", True)
        row.show_review_freshness = _bool(payload, "show_review_freshness", True)
        row.no_suggestions_behavior = no_suggestions_behavior
        row.api_unavailable_behavior = api_unavailable_behavior
        row.bypass_roles = payload.get("bypass_roles") if isinstance(payload.get("bypass_roles"), dict) else None
        row.updated_at = datetime.now(timezone.utc)
        row.updated_by = actor_id
        await self.session.flush()
        return self._serialize_rollout_policy(row)

    async def rollout_decision(self, context: dict[str, Any], *, actor_role: str) -> dict[str, Any]:
        surface = str(context.get("surface") or context.get("source_surface") or "api")
        service_code = str(context.get("service_code") or "").strip() or None
        offering_code = str(context.get("offering_code") or "").strip() or None
        request_template_key = str(context.get("request_template_key") or "").strip() or None
        candidates = [
            ("template", None, None, request_template_key, surface),
            ("offering", service_code, offering_code, None, surface),
            ("service", service_code, None, None, surface),
            ("global", None, None, None, surface),
            ("template", None, None, request_template_key, "all"),
            ("offering", service_code, offering_code, None, "all"),
            ("service", service_code, None, None, "all"),
            ("global", None, None, None, "all"),
        ]
        for scope_type, candidate_service, candidate_offering, candidate_template, candidate_surface in candidates:
            if scope_type == "template" and not candidate_template:
                continue
            if scope_type == "offering" and not (candidate_service and candidate_offering):
                continue
            if scope_type == "service" and not candidate_service:
                continue
            row = (
                await self.session.execute(
                    select(KnowledgeRolloutPolicy).where(
                        KnowledgeRolloutPolicy.scope_type == scope_type,
                        KnowledgeRolloutPolicy.service_code.is_(None) if candidate_service is None else KnowledgeRolloutPolicy.service_code == candidate_service,
                        KnowledgeRolloutPolicy.offering_code.is_(None) if candidate_offering is None else KnowledgeRolloutPolicy.offering_code == candidate_offering,
                        KnowledgeRolloutPolicy.request_template_key.is_(None) if candidate_template is None else KnowledgeRolloutPolicy.request_template_key == candidate_template,
                        KnowledgeRolloutPolicy.surface == candidate_surface,
                    )
                )
            ).scalars().first()
            if row is not None:
                return self._decision_from_policy(row, context=context, actor_role=actor_role, requested_surface=surface)
        return self._default_rollout_decision(surface=surface, context=context)

    async def list_rollout_policies(self) -> dict[str, Any]:
        rows = (await self.session.execute(select(KnowledgeRolloutPolicy).order_by(KnowledgeRolloutPolicy.updated_at.desc()))).scalars().all()
        return {"policies": [self._serialize_rollout_policy(row) for row in rows]}

    def _serialize_rollout_policy(self, row: KnowledgeRolloutPolicy) -> dict[str, Any]:
        return {
            "policy_id": row.policy_id,
            "scope_type": row.scope_type,
            "service_code": row.service_code,
            "offering_code": row.offering_code,
            "request_template_key": row.request_template_key,
            "surface": row.surface,
            "enabled": bool(row.enabled),
            "rollout_percent": int(row.rollout_percent),
            "reason": row.reason,
            "show_before_form": bool(row.show_before_form),
            "show_after_form": bool(row.show_after_form),
            "require_suggestions_before_submit": bool(row.require_suggestions_before_submit),
            "allow_skip": bool(row.allow_skip),
            "urgency_bypass": bool(row.urgency_bypass),
            "impact_bypass": bool(row.impact_bypass),
            "min_suggestions": int(row.min_suggestions),
            "max_suggestions": int(row.max_suggestions),
            "deflection_prompt_enabled": bool(row.deflection_prompt_enabled),
            "feedback_required_on_article_view": bool(row.feedback_required_on_article_view),
            "show_known_errors": bool(row.show_known_errors),
            "show_quality_badge": bool(row.show_quality_badge),
            "show_review_freshness": bool(row.show_review_freshness),
            "no_suggestions_behavior": row.no_suggestions_behavior,
            "api_unavailable_behavior": row.api_unavailable_behavior,
            "bypass_roles": row.bypass_roles,
            "updated_at": _iso(row.updated_at),
            "updated_by": row.updated_by,
        }

    def _decision_from_policy(
        self,
        row: KnowledgeRolloutPolicy,
        *,
        context: dict[str, Any],
        actor_role: str,
        requested_surface: str,
    ) -> dict[str, Any]:
        decision = self._serialize_rollout_policy(row)
        decision["surface"] = requested_surface
        bucket = _rollout_bucket(context)
        decision["rollout_bucket"] = bucket
        decision["policy_id"] = row.policy_id
        bypass_applied = False
        bypass_reason = None
        urgency = str(context.get("urgency") or context.get("priority") or "").lower()
        impact = str(context.get("impact") or "").lower()
        if row.urgency_bypass and urgency in {"high", "urgent", "critical", "1", "p0", "p1"}:
            bypass_applied = True
            bypass_reason = "urgency"
        elif row.impact_bypass and impact in {"high", "critical", "1"}:
            bypass_applied = True
            bypass_reason = "impact"
        roles = row.bypass_roles if isinstance(row.bypass_roles, dict) else {}
        if actor_role in set(roles.get("roles") or []):
            bypass_applied = True
            bypass_reason = "role"
        if bucket > int(row.rollout_percent):
            decision["enabled"] = False
            decision["reason"] = "rollout_bucket_disabled"
        if bypass_applied:
            decision["require_suggestions_before_submit"] = False
            decision["allow_skip"] = True
        decision["bypass_applied"] = bypass_applied
        decision["bypass_reason"] = bypass_reason
        return decision

    def _default_rollout_decision(self, *, surface: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "enabled": True,
            "reason": None,
            "scope_type": "default",
            "policy_id": None,
            "surface": surface,
            "show_before_form": True,
            "show_after_form": False,
            "require_suggestions_before_submit": False,
            "allow_skip": True,
            "urgency_bypass": True,
            "impact_bypass": True,
            "min_suggestions": 0,
            "max_suggestions": 5,
            "deflection_prompt_enabled": True,
            "feedback_required_on_article_view": False,
            "show_known_errors": True,
            "show_quality_badge": True,
            "show_review_freshness": True,
            "no_suggestions_behavior": "allow_submit",
            "api_unavailable_behavior": "allow_submit",
            "bypass_applied": False,
            "bypass_reason": None,
            "rollout_bucket": _rollout_bucket(context),
        }
