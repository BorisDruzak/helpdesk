from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from aiohttp import web

from app.db import get_session
from auth.context import AuthContext, AuthType
from auth.middleware import require_auth
from auth.service import AuthService
from quality.analytics_service import ServiceQualityAnalyticsService
from quality.feedback_service import TicketFeedbackService
from quality.improvement_service import ContinuousImprovementService
from quality.policy_service import QualityPolicyService
from quality.reopen_service import TicketReopenService
from quality.review_service import QualityReviewService


def _ok(**payload: Any) -> web.Response:
    return web.json_response({"status": "ok", **payload})


def _error(error: str, *, status: int = 400, **extra: Any) -> web.Response:
    return web.json_response({"status": "error", "error": error, **extra}, status=status)


async def _json(request: web.Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _auth(request: web.Request) -> AuthContext:
    return request.get("auth_context")


def _period(request: web.Request) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    days = int(request.query.get("days", "30") or "30")
    return now - timedelta(days=max(min(days, 365), 1)), now


async def handle_ticket_feedback(request: web.Request) -> web.Response:
    auth = _auth(request)
    data = await _json(request)
    data["ticket_id"] = request.match_info.get("ticket_id")
    if auth.actor_role in {"user", "requester"}:
        data["source_surface"] = "requester_portal"
        data.pop("visibility", None)
    try:
        async with get_session() as session:
            result = await TicketFeedbackService(session).submit_feedback(
                data,
                actor_id=auth.actor_id,
                actor_role=auth.actor_role,
            )
            await session.commit()
            return _ok(
                ok=True,
                feedback_id=result["feedback_id"],
                message=result["message"],
                reopen_available=result["reopen_available"],
            )
    except ValueError as exc:
        return _error(str(exc), status=400)


async def handle_ticket_reopen(request: web.Request) -> web.Response:
    auth = _auth(request)
    data = await _json(request)
    try:
        async with get_session() as session:
            result = await TicketReopenService(session).reopen_ticket(
                request.match_info.get("ticket_id"),
                reason_code=str(data.get("reason_code") or ""),
                reason_comment=data.get("reason_comment"),
                linked_feedback_id=data.get("linked_feedback_id"),
                linked_knowledge_item_id=data.get("linked_knowledge_item_id"),
                actor_id=auth.actor_id,
                actor_role=auth.actor_role,
            )
            await session.commit()
            return _ok(ticket_id=result["ticket_id"], ticket_status=result["status"], reopen_id=result["reopen_id"])
    except ValueError as exc:
        return _error(str(exc), status=400)


async def _public_auth_context(request: web.Request) -> AuthContext | None:
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        parts = auth_header.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
    if not token:
        return None
    service = AuthService(request.app["state"])
    info = await service.verify_ticket_public_session_token(token)
    if not info:
        return None
    ticket_id = request.match_info.get("ticket_id")
    if info.get("ticket_id") != ticket_id:
        return None
    return AuthContext(
        actor_id=info.get("actor_id") or f"public:{ticket_id}",
        actor_role="user",
        auth_type=AuthType.PUBLIC_TICKET_TOKEN,
        token=token,
        ticket_scope=ticket_id,
    )


async def handle_public_ticket_feedback(request: web.Request) -> web.Response:
    auth = await _public_auth_context(request)
    if auth is None:
        return _error("public ticket token required", status=401)
    data = await _json(request)
    data["ticket_id"] = request.match_info.get("ticket_id")
    data["source_surface"] = "public_ticket_page"
    data.pop("visibility", None)
    try:
        async with get_session() as session:
            result = await TicketFeedbackService(session).submit_feedback(data, actor_id=auth.actor_id, actor_role="requester")
            await session.commit()
            return _ok(ok=True, feedback_id=result["feedback_id"], message=result["message"], reopen_available=result["reopen_available"])
    except ValueError as exc:
        return _error(str(exc), status=400)


async def handle_public_ticket_reopen(request: web.Request) -> web.Response:
    auth = await _public_auth_context(request)
    if auth is None:
        return _error("public ticket token required", status=401)
    data = await _json(request)
    try:
        async with get_session() as session:
            result = await TicketReopenService(session).reopen_ticket(
                request.match_info.get("ticket_id"),
                reason_code=str(data.get("reason_code") or ""),
                reason_comment=data.get("reason_comment"),
                linked_feedback_id=data.get("linked_feedback_id"),
                actor_id=auth.actor_id,
                actor_role="requester",
            )
            await session.commit()
            return _ok(ticket_id=result["ticket_id"], ticket_status=result["status"], reopen_id=result["reopen_id"])
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support", "auditor")
async def handle_quality_reviews(request: web.Request) -> web.Response:
    async with get_session() as session:
        reviews = await QualityReviewService(session).list_reviews(status=request.query.get("status"))
        ticket_id = request.query.get("ticket_id")
        if ticket_id:
            reviews = [review for review in reviews if review.get("ticket_id") == ticket_id]
        return _ok(reviews=reviews, count=len(reviews))


@require_auth("admin", "support")
async def handle_quality_reviews_assign(request: web.Request) -> web.Response:
    data = await _json(request)
    auth = _auth(request)
    try:
        async with get_session() as session:
            review = await QualityReviewService(session).assign_review(
                request.match_info.get("review_id"),
                assigned_to_actor_id=str(data.get("assigned_to_actor_id") or ""),
                actor_id=auth.actor_id,
            )
            await session.commit()
            return _ok(review=review)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support")
async def handle_quality_reviews_start(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            review = await QualityReviewService(session).start_review(request.match_info.get("review_id"), actor_id=auth.actor_id)
            await session.commit()
            return _ok(review=review)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support")
async def handle_quality_reviews_complete(request: web.Request) -> web.Response:
    data = await _json(request)
    auth = _auth(request)
    try:
        async with get_session() as session:
            review = await QualityReviewService(session).complete_review(
                request.match_info.get("review_id"),
                findings=data.get("findings") if isinstance(data.get("findings"), dict) else {},
                score=int(data.get("score") or 0),
                actor_id=auth.actor_id,
            )
            await session.commit()
            return _ok(review=review)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support")
async def handle_quality_reviews_dismiss(request: web.Request) -> web.Response:
    data = await _json(request)
    auth = _auth(request)
    try:
        async with get_session() as session:
            review = await QualityReviewService(session).dismiss_review(
                request.match_info.get("review_id"),
                actor_id=auth.actor_id,
                reason=str(data.get("reason") or "").strip() or None,
            )
            await session.commit()
            return _ok(review=review)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support", "auditor")
async def handle_quality_improvement_actions(request: web.Request) -> web.Response:
    async with get_session() as session:
        actions = await ContinuousImprovementService(session).list_actions(status=request.query.get("status"))
        ticket_id = request.query.get("ticket_id")
        if ticket_id:
            actions = [action for action in actions if action.get("ticket_id") == ticket_id]
        return _ok(actions=actions, count=len(actions))


@require_auth("admin", "support")
async def handle_quality_improvement_actions_create(request: web.Request) -> web.Response:
    data = await _json(request)
    auth = _auth(request)
    try:
        async with get_session() as session:
            action = await ContinuousImprovementService(session).create_action(data, actor_id=auth.actor_id)
            await session.commit()
            return _ok(action=action)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support")
async def handle_quality_improvement_action_patch(request: web.Request) -> web.Response:
    data = await _json(request)
    auth = _auth(request)
    try:
        async with get_session() as session:
            action = await ContinuousImprovementService(session).update_action(request.match_info.get("action_id"), data, actor_id=auth.actor_id)
            await session.commit()
            return _ok(action=action)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support")
async def handle_quality_improvement_action_close(request: web.Request) -> web.Response:
    data = await _json(request)
    auth = _auth(request)
    try:
        async with get_session() as session:
            action = await ContinuousImprovementService(session).close_action(
                request.match_info.get("action_id"),
                outcome_notes=str(data.get("outcome_notes") or ""),
                actor_id=auth.actor_id,
            )
            await session.commit()
            return _ok(action=action)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support", "auditor")
async def handle_quality_summary(request: web.Request) -> web.Response:
    start, end = _period(request)
    async with get_session() as session:
        summary = await ServiceQualityAnalyticsService(session).service_quality(period_start=start, period_end=end, bucket=request.query.get("bucket") or "week")
        rows = summary["rows"]
        feedback_count = sum(row["feedback_count"] for row in rows)
        avg_values = [row["avg_csat"] for row in rows if row["avg_csat"] is not None]
        return _ok(
            summary={
                "avg_csat": round(sum(avg_values) / len(avg_values), 2) if avg_values else None,
                "feedback_count": feedback_count,
                "negative_csat_count": sum(row["negative_csat_count"] for row in rows),
                "reopen_count": sum(row["reopen_count"] for row in rows),
                "sla_breach_count": sum(row["sla_breach_count"] for row in rows),
                "qa_review_count": sum(row["qa_review_count"] for row in rows),
                "improvement_action_count": sum(row["improvement_action_count"] for row in rows),
            }
        )


@require_auth("admin", "support", "auditor")
async def handle_quality_service_quality(request: web.Request) -> web.Response:
    start, end = _period(request)
    async with get_session() as session:
        summary = await ServiceQualityAnalyticsService(session).service_quality(period_start=start, period_end=end, bucket=request.query.get("bucket") or "week")
        return _ok(**summary)


@require_auth("admin", "support")
async def handle_quality_snapshots_recompute(request: web.Request) -> web.Response:
    start, end = _period(request)
    async with get_session() as session:
        summary = await ServiceQualityAnalyticsService(session).service_quality(
            period_start=start,
            period_end=end,
            bucket=request.query.get("bucket") or "week",
            recompute_snapshot=True,
        )
        await session.commit()
        return _ok(**summary)


@require_auth("admin", "support", "auditor")
async def handle_quality_policies(request: web.Request) -> web.Response:
    async with get_session() as session:
        policy = await QualityPolicyService(session).effective_policy(
            service_code=request.query.get("service_code"),
            offering_code=request.query.get("offering_code"),
            queue_id=int(request.query["queue_id"]) if request.query.get("queue_id") else None,
        )
        return _ok(policy=policy)


@require_auth("admin")
async def handle_quality_policies_save(request: web.Request) -> web.Response:
    data = await _json(request)
    auth = _auth(request)
    try:
        async with get_session() as session:
            policy = await QualityPolicyService(session).save_policy(data, actor_id=auth.actor_id)
            await session.commit()
            return _ok(policy=policy)
    except ValueError as exc:
        return _error(str(exc), status=400)
