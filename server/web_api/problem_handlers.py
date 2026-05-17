from __future__ import annotations

from typing import Any

from aiohttp import web

from app.db import get_session
from auth.middleware import require_auth
from problem.analytics_service import ProblemAnalyticsService
from problem.candidate_service import ProblemCandidateService
from problem.known_error_service import ProblemKnownErrorService
from problem.problem_service import ProblemService
from problem.rca_service import RCAService


def _ok(**payload: Any) -> web.Response:
    return web.json_response({"status": "ok", **payload})


def _error(error: str, *, status: int = 400) -> web.Response:
    return web.json_response({"status": "error", "error": error}, status=status)


async def _json(request: web.Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _auth(request: web.Request):
    return request.get("auth_context")


@require_auth("admin", "support", "auditor")
async def handle_web_problems_list(request: web.Request) -> web.Response:
    async with get_session() as session:
        if request.query.get("ticket_id"):
            items = await ProblemService(session).list_ticket_problems(request.query.get("ticket_id"))
            return _ok(items=items, count=len(items))
        problems = await ProblemService(session).list_problems(status=request.query.get("status"))
        return _ok(problems=problems, count=len(problems))


@require_auth("admin", "support")
async def handle_web_problems_create(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            problem = await ProblemService(session).create_problem(await _json(request), actor_id=auth.actor_id)
            await session.commit()
            return _ok(problem=problem)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support", "auditor")
async def handle_web_problem_get(request: web.Request) -> web.Response:
    try:
        async with get_session() as session:
            problem_id = request.match_info.get("problem_id")
            problem = await ProblemService(session).get_problem(problem_id)
            links = await ProblemService(session).list_problem_ticket_links(problem_id)
            return _ok(problem=problem, ticket_links=links)
    except ValueError as exc:
        return _error(str(exc), status=404)


@require_auth("admin", "support")
async def handle_web_problem_transition(request: web.Request) -> web.Response:
    auth = _auth(request)
    data = await _json(request)
    try:
        async with get_session() as session:
            problem = await ProblemService(session).transition_problem(
                request.match_info.get("problem_id"),
                str(data.get("status") or ""),
                data,
                actor_id=auth.actor_id,
            )
            await session.commit()
            return _ok(problem=problem)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support")
async def handle_web_problem_link_ticket(request: web.Request) -> web.Response:
    auth = _auth(request)
    data = await _json(request)
    try:
        async with get_session() as session:
            link = await ProblemService(session).link_ticket(
                request.match_info.get("problem_id"),
                str(data.get("ticket_id") or ""),
                link_type=str(data.get("link_type") or "suspected"),
                evidence_summary=data.get("evidence_summary"),
                actor_id=auth.actor_id,
            )
            await session.commit()
            return _ok(link=link)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support")
async def handle_web_problem_unlink_ticket(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            result = await ProblemService(session).unlink_ticket(
                request.match_info.get("problem_id"),
                request.match_info.get("ticket_id"),
                actor_id=auth.actor_id,
            )
            await session.commit()
            return _ok(**result)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support")
async def handle_web_problem_affected_objects(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            affected = await ProblemService(session).add_affected_object(request.match_info.get("problem_id"), await _json(request), actor_id=auth.actor_id)
            await session.commit()
            return _ok(affected=affected)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support", "auditor")
async def handle_web_problem_candidates(request: web.Request) -> web.Response:
    async with get_session() as session:
        candidates = await ProblemCandidateService(session).list_candidates(status=request.query.get("status"))
        return _ok(candidates=candidates, count=len(candidates))


@require_auth("admin", "support")
async def handle_web_problem_candidates_scan(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        result = await ProblemCandidateService(session).scan(actor_id=auth.actor_id)
        await session.commit()
        return _ok(scan=result)


@require_auth("admin", "support")
async def handle_web_problem_candidate_convert(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            result = await ProblemCandidateService(session).convert_candidate(request.match_info.get("candidate_id"), actor_id=auth.actor_id)
            await session.commit()
            return _ok(**result)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support", "auditor")
async def handle_web_problem_metrics_summary(request: web.Request) -> web.Response:
    async with get_session() as session:
        summary = await ProblemAnalyticsService(session).summary()
        return _ok(summary=summary)


@require_auth("admin", "support")
async def handle_web_problem_rca_create(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            rca = await RCAService(session).create_draft(request.match_info.get("problem_id"), await _json(request), actor_id=auth.actor_id)
            await session.commit()
            return _ok(rca=rca)
    except ValueError as exc:
        return _error(str(exc), status=400)


@require_auth("admin", "support")
async def handle_web_problem_rca_submit(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        rca = await RCAService(session).submit_review(request.match_info.get("problem_id"), request.match_info.get("rca_id"), actor_id=auth.actor_id)
        await session.commit()
        return _ok(rca=rca)


@require_auth("admin", "support")
async def handle_web_problem_rca_approve(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        rca = await RCAService(session).approve(request.match_info.get("problem_id"), request.match_info.get("rca_id"), actor_id=auth.actor_id)
        await session.commit()
        return _ok(rca=rca)


@require_auth("admin", "support")
async def handle_web_problem_known_error_draft(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        result = await ProblemKnownErrorService(session).create_known_error_draft(request.match_info.get("problem_id"), actor_id=auth.actor_id)
        await session.commit()
        return _ok(link=result)


@require_auth("admin", "support")
async def handle_web_problem_workaround_draft(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        result = await ProblemKnownErrorService(session).create_workaround_draft(request.match_info.get("problem_id"), actor_id=auth.actor_id)
        await session.commit()
        return _ok(link=result)
