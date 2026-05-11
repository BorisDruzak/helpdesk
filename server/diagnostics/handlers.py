from __future__ import annotations

from aiohttp import web
from sqlalchemy import select

from app.db import get_session
from access_control.service import resolve_effective_access
from app.db.models import Device, DeviceDesiredModule, DeviceModule, DiagnosticEvidence, DiagnosticFinding, Ticket
from app.repos.diagnostics_repo import DiagnosticRepo
from auth.middleware import require_auth
from diagnostics.capability_registry import CapabilityRegistry
from diagnostics.bundle import DiagnosticBundleService
from diagnostics.execution_router import CapabilityExecutionRouter
from diagnostics.findings import DiagnosticFindingService
from diagnostics.passport_bridge import DiagnosticPassportBridgeService
from diagnostics.profiles import list_profiles, resolve_ticket_profile
from diagnostics.profile_runner import DiagnosticProfileRunnerService
from diagnostics.projection import DiagnosticProjectionService
from diagnostics.readiness import CapabilityReadinessService, ReadinessContext
from diagnostics.serialization import bundle_to_dict, evidence_to_dict, finding_to_dict, session_to_dict, ticket_evidence_to_dict
from diagnostics.service import DiagnosticOverviewService
from diagnostics.sessions import DiagnosticSessionService
from tools.service import ToolExecutionService


def _capability_payload(capability):
    return capability.to_dict()


def _state_mapping(state, *names: str) -> dict:
    if state is None:
        return {}
    for name in names:
        value = getattr(state, name, None)
        if isinstance(value, dict):
            return value
        if hasattr(state, "get"):
            try:
                value = state.get(name)
            except Exception:
                value = None
            if isinstance(value, dict):
                return value
    return {}


def _device_platform(device: Device | None) -> str | None:
    raw = str(getattr(device, "os", "") or "").strip().lower()
    if not raw:
        return None
    if "windows" in raw or raw.startswith("win"):
        return "win32"
    if "darwin" in raw or "mac" in raw:
        return "darwin"
    if "linux" in raw:
        return "linux"
    return raw


def _installed_module_map(items: list[DeviceModule]) -> dict:
    result = {}
    for item in items:
        result[item.module_name] = {
            "version": item.version,
            "installed": item.installed,
            "active": item.active,
            "state": item.state,
            "last_error_code": item.last_error_code,
        }
    return result


def _desired_module_map(items: list[DeviceDesiredModule]) -> dict:
    return {
        item.module_name: {
            "version": item.desired_version,
            "state": item.state,
            "reason": item.reason,
        }
        for item in items
    }


@require_auth("admin", "support", "auditor")
async def handle_diagnostics_capabilities(request: web.Request) -> web.Response:
    state = request.app.get("state")
    tool_service = ToolExecutionService(state)
    registry = CapabilityRegistry(tool_service=tool_service, state=state)
    device_id = request.query.get("device_id")
    capabilities = await registry.list_capabilities(device_id=device_id)
    return web.json_response(
        {
            "status": "ok",
            "capabilities": [_capability_payload(capability) for capability in capabilities],
            "count": len(capabilities),
        }
    )


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_capabilities(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    if not ticket_id:
        return web.json_response(
            {"status": "error", "error_code": "TICKET_ID_REQUIRED", "error": "ticket_id is required"},
            status=400,
        )
    state = request.app.get("state")
    async with get_session() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one_or_none()
        device = None
        installed_modules = []
        desired_modules = []
        if ticket is not None and getattr(ticket, "device_id", None):
            device = (
                await session.execute(
                    select(Device).where(Device.device_id == ticket.device_id, Device.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            installed_modules = list(
                (
                    await session.execute(select(DeviceModule).where(DeviceModule.device_id == ticket.device_id))
                ).scalars()
            )
            desired_modules = list(
                (
                    await session.execute(select(DeviceDesiredModule).where(DeviceDesiredModule.device_id == ticket.device_id))
                ).scalars()
            )
    if ticket is None:
        return web.json_response(
            {"status": "error", "error_code": "TICKET_NOT_FOUND", "error": "Ticket not found"},
            status=404,
        )
    device_id = str(getattr(ticket, "device_id", "") or "").strip() or None
    tool_service = ToolExecutionService(state)
    registry = CapabilityRegistry(tool_service=tool_service, state=state)
    readiness_service = CapabilityReadinessService(state=state)
    capabilities = await registry.list_capabilities(device_id=device_id)
    auth_context = request.get("auth_context")
    access = resolve_effective_access(
        actor_id=getattr(auth_context, "actor_id", None),
        actor_role=getattr(auth_context, "actor_role", None),
    )
    context = ReadinessContext(
        ticket_id=ticket_id,
        device_id=device_id,
        actor=auth_context,
        device_platform=_device_platform(device),
        installed_modules=_installed_module_map(installed_modules),
        desired_modules=_desired_module_map(desired_modules),
        integration_configs=_state_mapping(state, "diagnostic_integration_configs", "integration_configs"),
        credential_keys=_state_mapping(state, "diagnostic_credential_keys", "credential_keys"),
        mappings=_state_mapping(state, "diagnostic_mappings", "integration_mappings"),
        policy_flags=_state_mapping(state, "diagnostic_policy_flags", "policy_flags"),
        permissions=set(access.permissions),
        has_root_trace=bool(getattr(ticket, "observer_root_trace_id", None)),
    )
    capability_items = []
    for capability in capabilities:
        readiness = await readiness_service.get_readiness(capability, context)
        item = readiness.to_dict()
        item.update(
            {
                "id": capability.id,
                "provider_id": capability.provider_id,
                "provider_type": capability.provider_type,
                "source": capability.source,
                "install_required_on_agent": capability.install_required_on_agent,
                "requires_integration": capability.requires_integration,
                "integration_key": capability.integration_key,
            }
        )
        capability_items.append(item)
    return web.json_response(
        {
            "status": "ok",
            "ticket_id": ticket_id,
            "device_id": device_id,
            "capabilities": capability_items,
            "count": len(capability_items),
        }
    )


@require_auth("admin", "support")
async def handle_ticket_diagnostics_capability_run(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    capability_id = str(request.match_info.get("capability_id") or "").strip()
    if not ticket_id or not capability_id:
        return web.json_response(
            {"status": "error", "error_code": "CAPABILITY_RUN_TARGET_REQUIRED", "error": "ticket_id and capability_id are required"},
            status=400,
        )
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    params = payload.get("params") if isinstance(payload, dict) and isinstance(payload.get("params"), dict) else {}
    state = request.app.get("state")
    async with get_session() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one_or_none()
    if ticket is None:
        return web.json_response(
            {"status": "error", "error_code": "TICKET_NOT_FOUND", "error": "Ticket not found"},
            status=404,
        )
    device_id = str(getattr(ticket, "device_id", "") or "").strip() or None
    tool_service = ToolExecutionService(state)
    registry = CapabilityRegistry(tool_service=tool_service, state=state)
    router = CapabilityExecutionRouter(capability_registry=registry, tool_service=tool_service)
    result = await router.run_capability(
        ticket_id=ticket_id,
        device_id=device_id,
        capability_id=capability_id,
        params=params,
        actor=request.get("auth_context"),
    )
    status = 200
    if result.get("error_code") == "CAPABILITY_NOT_FOUND":
        status = 404
    elif result.get("status") == "error":
        status = 400
    return web.json_response(result, status=status)


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_overview(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        try:
            payload = await DiagnosticOverviewService(session).get_ticket_diagnostics_overview(
                ticket_id,
                actor=request.get("auth_context"),
            )
            await session.commit()
        except KeyError:
            return web.json_response({"status": "error", "error_code": "TICKET_NOT_FOUND", "error": "Ticket not found"}, status=404)
    return web.json_response(payload)


@require_auth("admin", "support", "auditor")
async def handle_web_support_ticket_diagnostics_overview(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        try:
            payload = await DiagnosticOverviewService(session).get_ticket_diagnostics_overview(
                ticket_id,
                actor=request.get("auth_context"),
            )
            await session.commit()
        except KeyError:
            return web.json_response({"status": "error", "error_code": "TICKET_NOT_FOUND", "error": "Ticket not found"}, status=404)
    return web.json_response({"status": "success", "data": payload})


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_sessions(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        items = await DiagnosticSessionService(session).list_sessions(ticket_id)
    return web.json_response({"status": "ok", "ticket_id": ticket_id, "sessions": [session_to_dict(item) for item in items]})


@require_auth("admin", "support")
async def handle_ticket_diagnostics_session_create(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    async with get_session() as session:
        service = DiagnosticSessionService(session)
        item = await service.create_session(
            ticket_id=ticket_id,
            profile_id=payload.get("profile_id") if isinstance(payload, dict) else None,
            trigger_source=payload.get("trigger_source", "manual") if isinstance(payload, dict) else "manual",
            actor=request.get("auth_context"),
        )
        await session.commit()
    return web.json_response({"status": "ok", "session": session_to_dict(item)}, status=201)


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_session_detail(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    session_id = str(request.match_info.get("session_id") or "").strip()
    async with get_session() as session:
        repo = DiagnosticRepo(session)
        item = await repo.get_session(session_id)
        if item is None or item.ticket_id != ticket_id:
            return web.json_response({"status": "error", "error_code": "SESSION_NOT_FOUND"}, status=404)
        steps = await repo.list_steps(ticket_id, session_id=session_id)
    return web.json_response({"status": "ok", "session": session_to_dict(item, steps=steps)})


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_evidence(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        items = await DiagnosticRepo(session).list_evidence(ticket_id)
    return web.json_response({"status": "ok", "ticket_id": ticket_id, "evidence": [evidence_to_dict(item) for item in items]})


@require_auth("admin", "support")
async def handle_ticket_diagnostics_manual_evidence(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    actor = request.get("auth_context")
    async with get_session() as session:
        item = await DiagnosticProjectionService(session).create_manual_evidence(
            ticket_id=ticket_id,
            title=str(payload.get("title") or "Manual diagnostic evidence"),
            summary=payload.get("summary"),
            status=str(payload.get("status") or "info"),
            kind=str(payload.get("kind") or "manual.check"),
            domain=str(payload.get("domain") or "manual"),
            perspective=str(payload.get("perspective") or "manual"),
            created_by="support",
            passport_eligible=bool(payload.get("passport_eligible", True)),
        )
        await session.commit()
    return web.json_response({"status": "ok", "evidence": evidence_to_dict(item)}, status=201)


@require_auth("admin", "support")
async def handle_ticket_diagnostics_evidence_patch(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    evidence_id = str(request.match_info.get("evidence_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    async with get_session() as session:
        repo = DiagnosticRepo(session)
        item = await repo.get_evidence(evidence_id)
        if item is None or item.ticket_id != ticket_id:
            return web.json_response({"status": "error", "error_code": "EVIDENCE_NOT_FOUND"}, status=404)
        if isinstance(payload, dict) and "selected_for_passport" in payload:
            item.selected_for_passport = bool(payload["selected_for_passport"])
        await session.commit()
    return web.json_response({"status": "ok", "evidence": evidence_to_dict(item)})


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_findings(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        items = await DiagnosticFindingService(session).list_findings(ticket_id)
    return web.json_response({"status": "ok", "ticket_id": ticket_id, "findings": [finding_to_dict(item) for item in items]})


@require_auth("admin", "support")
async def handle_ticket_diagnostics_findings_evaluate(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        await DiagnosticProjectionService(session).project_ticket_sources(ticket_id)
        items = await DiagnosticFindingService(session).evaluate_ticket(ticket_id)
        await session.commit()
    return web.json_response({"status": "ok", "ticket_id": ticket_id, "findings": [finding_to_dict(item) for item in items]})


@require_auth("admin", "support")
async def handle_ticket_diagnostics_manual_finding(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    async with get_session() as session:
        item = await DiagnosticRepo(session).upsert_finding(
            ticket_id=ticket_id,
            session_id=payload.get("session_id"),
            root_cause_code=payload.get("root_cause_code"),
            title=str(payload.get("title") or "Manual finding"),
            description=payload.get("description"),
            confidence=payload.get("confidence"),
            status=str(payload.get("status") or "suspected"),
            evidence_ids=payload.get("evidence_ids") if isinstance(payload.get("evidence_ids"), list) else [],
            recommended_actions=payload.get("recommended_actions") if isinstance(payload.get("recommended_actions"), list) else [],
            created_by="support",
        )
        await session.commit()
    return web.json_response({"status": "ok", "finding": finding_to_dict(item)}, status=201)


@require_auth("admin", "support")
async def handle_ticket_diagnostics_finding_patch(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    finding_id = str(request.match_info.get("finding_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    async with get_session() as session:
        item = await session.get(DiagnosticFinding, finding_id)
        if item is None or item.ticket_id != ticket_id:
            return web.json_response({"status": "error", "error_code": "FINDING_NOT_FOUND"}, status=404)
        if isinstance(payload, dict):
            for field in ("status", "description", "confidence"):
                if field in payload:
                    setattr(item, field, payload[field])
        await session.commit()
    return web.json_response({"status": "ok", "finding": finding_to_dict(item)})


@require_auth("admin", "support")
async def handle_ticket_diagnostics_bundle_create(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    async with get_session() as session:
        await DiagnosticProjectionService(session).project_ticket_sources(ticket_id)
        item = await DiagnosticBundleService(session).build_bundle(
            ticket_id=ticket_id,
            session_id=payload.get("session_id"),
            actor=request.get("auth_context"),
            include_agent_actions=bool(payload.get("include_agent_actions", False)),
            include_observer=bool(payload.get("include_observer", True)),
            include_artifacts=bool(payload.get("include_artifacts", True)),
            include_remote_assist=bool(payload.get("include_remote_assist", True)),
            include_monitoring=bool(payload.get("include_monitoring", True)),
        )
        await session.commit()
    return web.json_response({"status": "ok", "bundle": bundle_to_dict(item)}, status=201)


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_bundle_get(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    bundle_id = str(request.match_info.get("bundle_id") or "").strip()
    async with get_session() as session:
        item = await DiagnosticBundleService(session).get_bundle(bundle_id)
        if item is None or item.ticket_id != ticket_id:
            return web.json_response({"status": "error", "error_code": "BUNDLE_NOT_FOUND"}, status=404)
    return web.json_response({"status": "ok", "bundle": bundle_to_dict(item)})


@require_auth("admin", "support")
async def handle_ticket_diagnostics_passport_attach_selected(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    async with get_session() as session:
        items = await DiagnosticPassportBridgeService(session).attach_selected_diagnostic_evidence_to_passport(
            ticket_id=ticket_id,
            actor=request.get("auth_context"),
            passport_id=payload.get("passport_id"),
        )
        await session.commit()
    return web.json_response(
        {
            "status": "ok",
            "ticket_id": ticket_id,
            "attached_count": len(items),
            "evidence": [ticket_evidence_to_dict(item) for item in items],
        }
    )


@require_auth("admin", "support")
async def handle_ticket_diagnostics_run_profile(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    async with get_session() as session:
        try:
            result = await DiagnosticProfileRunnerService(session).run_profile(
                ticket_id=ticket_id,
                profile_id=payload.get("profile_id"),
                params=payload.get("params") if isinstance(payload.get("params"), dict) else {},
                auto_select_evidence=bool(payload.get("auto_select_evidence", False)),
                actor=request.get("auth_context"),
            )
            await session.commit()
        except KeyError:
            return web.json_response({"status": "error", "error_code": "TICKET_NOT_FOUND"}, status=404)
    response = {"status": "ok", **result}
    return web.json_response(response, status=201)


@require_auth("admin", "support", "auditor")
async def handle_diagnostics_profiles(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "profiles": list_profiles()})


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_profile(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket is None:
            return web.json_response({"status": "error", "error_code": "TICKET_NOT_FOUND"}, status=404)
        profile = resolve_ticket_profile(ticket)
    return web.json_response({"status": "ok", "ticket_id": ticket_id, "profile": profile})
