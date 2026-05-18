from __future__ import annotations

from typing import Any

from aiohttp import web

from app.db import get_session
from auth.middleware import require_auth
from change.analytics_service import ChangeAnalyticsService
from change.approval_service import ChangeApprovalService
from change.calendar_service import ChangeCalendarService
from change.change_service import ChangeService
from change.pir_service import PIRService
from change.plan_service import ChangePlanService
from change.policy_service import ChangePolicyService
from change.risk_service import RiskAssessmentService
from change.task_service import ChangeTaskService


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
async def handle_web_changes_list(request: web.Request) -> web.Response:
    async with get_session() as session:
        changes = await ChangeService(session).list_changes(status=request.query.get("status"))
        return _ok(changes=changes, count=len(changes))


@require_auth("admin", "support")
async def handle_web_changes_create(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            change = await ChangeService(session).create_change(await _json(request), actor_id=auth.actor_id)
            await session.commit()
            return _ok(change=change)
    except ValueError as exc:
        return _error(str(exc))


@require_auth("admin", "support", "auditor")
async def handle_web_change_get(request: web.Request) -> web.Response:
    try:
        async with get_session() as session:
            change = await ChangeService(session).get_change(request.match_info.get("change_id"))
            return _ok(change=change)
    except ValueError as exc:
        return _error(str(exc), status=404)


@require_auth("admin", "support")
async def handle_web_change_transition(request: web.Request) -> web.Response:
    auth = _auth(request)
    data = await _json(request)
    try:
        async with get_session() as session:
            change = await ChangeService(session).transition_change(request.match_info.get("change_id"), str(data.get("status") or ""), data, actor_id=auth.actor_id)
            await session.commit()
            return _ok(change=change)
    except ValueError as exc:
        return _error(str(exc))


@require_auth("admin", "support")
async def handle_web_change_from_problem(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            change = await ChangeService(session).create_from_problem(request.match_info.get("problem_id"), actor_id=auth.actor_id)
            await session.commit()
            return _ok(change=change)
    except ValueError as exc:
        return _error(str(exc))


@require_auth("admin", "support")
async def handle_web_change_from_improvement_action(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            change = await ChangeService(session).create_from_improvement_action(request.match_info.get("action_id"), actor_id=auth.actor_id)
            await session.commit()
            return _ok(change=change)
    except ValueError as exc:
        return _error(str(exc))


@require_auth("admin", "support")
async def handle_web_change_risk_create(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            risk = await RiskAssessmentService(session).create_assessment(request.match_info.get("change_id"), await _json(request), actor_id=auth.actor_id)
            await session.commit()
            return _ok(risk=risk)
    except ValueError as exc:
        return _error(str(exc))


@require_auth("admin", "support")
async def handle_web_change_risk_submit(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        risk = await RiskAssessmentService(session).submit_assessment(request.match_info.get("change_id"), request.match_info.get("assessment_id"), actor_id=auth.actor_id)
        await session.commit()
        return _ok(risk=risk)


@require_auth("admin", "support")
async def handle_web_change_risk_approve(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        risk = await RiskAssessmentService(session).approve_assessment(request.match_info.get("change_id"), request.match_info.get("assessment_id"), actor_id=auth.actor_id)
        await session.commit()
        return _ok(risk=risk)


@require_auth("admin", "support")
async def handle_web_change_plan_create(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            plan = await ChangePlanService(session).create_plan(request.match_info.get("change_id"), await _json(request), actor_id=auth.actor_id)
            await session.commit()
            return _ok(plan=plan)
    except ValueError as exc:
        return _error(str(exc))


@require_auth("admin", "support")
async def handle_web_change_plan_approve(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        plan = await ChangePlanService(session).approve_plan(request.match_info.get("change_id"), request.match_info.get("plan_id"), actor_id=auth.actor_id)
        await session.commit()
        return _ok(plan=plan)


@require_auth("admin", "support")
async def handle_web_change_approvals_request(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        result = await ChangeApprovalService(session).request_approvals(request.match_info.get("change_id"), actor_id=auth.actor_id)
        await session.commit()
        return _ok(**result)


@require_auth("admin", "support")
async def handle_web_change_approval_decide(request: web.Request) -> web.Response:
    auth = _auth(request)
    data = await _json(request)
    decision = str(data.get("decision") or ("approved" if request.path.endswith("/approve") else "rejected" if request.path.endswith("/reject") else ""))
    try:
        async with get_session() as session:
            approval = await ChangeApprovalService(session).decide_approval(
                request.match_info.get("change_id"),
                request.match_info.get("approval_id"),
                decision=decision,
                actor_id=auth.actor_id,
                actor_role=auth.role,
                comment=data.get("comment"),
            )
            await session.commit()
            return _ok(approval=approval)
    except ValueError as exc:
        return _error(str(exc), status=403 if "approver" in str(exc) else 400)


@require_auth("admin", "support", "auditor")
async def handle_web_change_windows(request: web.Request) -> web.Response:
    async with get_session() as session:
        windows = await ChangeCalendarService(session).list_windows()
        return _ok(windows=windows, count=len(windows))


@require_auth("admin", "support")
async def handle_web_change_windows_create(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            window = await ChangeCalendarService(session).create_window(await _json(request), actor_id=auth.actor_id)
            await session.commit()
            return _ok(window=window)
    except ValueError as exc:
        return _error(str(exc))


@require_auth("admin", "support")
async def handle_web_change_schedule(request: web.Request) -> web.Response:
    auth = _auth(request)
    data = await _json(request)
    try:
        async with get_session() as session:
            change = await ChangeCalendarService(session).schedule_change(
                request.match_info.get("change_id"),
                planned_start_at=data.get("planned_start_at"),
                planned_end_at=data.get("planned_end_at"),
                actor_id=auth.actor_id,
                blackout_override=bool(data.get("blackout_override", False)),
                override_justification=data.get("override_justification"),
            )
            await session.commit()
            return _ok(change=change)
    except ValueError as exc:
        return _error(str(exc))


@require_auth("admin", "support", "auditor")
async def handle_web_change_tasks(request: web.Request) -> web.Response:
    async with get_session() as session:
        tasks = await ChangeTaskService(session).list_tasks(request.match_info.get("change_id"))
        return _ok(tasks=tasks, count=len(tasks))


@require_auth("admin", "support")
async def handle_web_change_task_create(request: web.Request) -> web.Response:
    auth = _auth(request)
    try:
        async with get_session() as session:
            task = await ChangeTaskService(session).create_task(request.match_info.get("change_id"), await _json(request), actor_id=auth.actor_id)
            await session.commit()
            return _ok(task=task)
    except ValueError as exc:
        return _error(str(exc))


@require_auth("admin", "support")
async def handle_web_change_task_complete(request: web.Request) -> web.Response:
    auth = _auth(request)
    data = await _json(request)
    async with get_session() as session:
        task = await ChangeTaskService(session).complete_task(request.match_info.get("change_id"), request.match_info.get("task_id"), actor_id=auth.actor_id, result_notes=data.get("result_notes"))
        await session.commit()
        return _ok(task=task)


@require_auth("admin", "support")
async def handle_web_change_pir_create(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        pir = await PIRService(session).create_pir(request.match_info.get("change_id"), await _json(request), actor_id=auth.actor_id)
        await session.commit()
        return _ok(pir=pir)


@require_auth("admin", "support")
async def handle_web_change_pir_submit(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        pir = await PIRService(session).submit_pir(request.match_info.get("change_id"), request.match_info.get("pir_id"), actor_id=auth.actor_id)
        await session.commit()
        return _ok(pir=pir)


@require_auth("admin", "support")
async def handle_web_change_pir_approve(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        pir = await PIRService(session).approve_pir(request.match_info.get("change_id"), request.match_info.get("pir_id"), actor_id=auth.actor_id)
        await session.commit()
        return _ok(pir=pir)


@require_auth("admin", "support", "auditor")
async def handle_web_change_metrics_summary(request: web.Request) -> web.Response:
    async with get_session() as session:
        summary = await ChangeAnalyticsService(session).summary()
        return _ok(summary=summary)


@require_auth("admin", "support", "auditor")
async def handle_web_change_policies(request: web.Request) -> web.Response:
    async with get_session() as session:
        policies = await ChangePolicyService(session).list_policies()
        return _ok(policies=policies)


@require_auth("admin")
async def handle_web_change_policies_save(request: web.Request) -> web.Response:
    auth = _auth(request)
    async with get_session() as session:
        policy = await ChangePolicyService(session).save_policy(await _json(request), actor_id=auth.actor_id)
        await session.commit()
        return _ok(policy=policy)


@require_auth("admin", "support", "auditor")
async def handle_web_change_policies_preview(request: web.Request) -> web.Response:
    async with get_session() as session:
        policy = await ChangePolicyService(session).effective_policy(await _json(request))
        return _ok(policy=policy)
