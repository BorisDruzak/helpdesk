from __future__ import annotations

from aiohttp import web
from loguru import logger
from sqlalchemy import select

from app.db import get_session
from app.db.models import Device, DeviceUserBinding, RegistryPerson, RegistryPersonIdentity, UiUser
from auth.middleware import require_auth
from auth.rate_limit import check_rate_limit, client_ip, rate_limited_response
from registry.account_state_service import build_agent_account_state
from registry.account_session_service import AccountSessionService
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.browser_pairing_service import BrowserPairingService
from registry.registration_form_service import build_lightweight_registry_options, build_registration_form_payload
from registry.registration_service import RegistrationConflictError, RegistrationService, RegistrationValidationError
from registry.service import RegistryIngestionService, RegistrySnapshotService

import uuid


def _success(data: dict) -> web.Response:
    return web.json_response({"status": "success", "data": data})


def _text(value: object, *, max_length: int = 500) -> str | None:
    text = str(value or "").strip()
    return text[:max_length] if text else None


def _validate_uuid_device_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return str(uuid.UUID(text))
    except ValueError as exc:
        raise RegistrationValidationError("device_id must be a valid UUID") from exc


async def _device_exists(session, device_id: str) -> bool:
    return await session.get(Device, device_id) is not None


def _forbidden(message: str = "forbidden") -> web.Response:
    return web.json_response({"status": "error", "error": message, "error_code": "FORBIDDEN"}, status=403)


def _browser_pairing_next_url(payload: dict) -> str:
    route_purpose = "register" if payload.get("purpose") == "registration" else "login"
    return f"/app/device/{route_purpose}?pairing_id={payload['pairing_id']}"


async def _resolve_submit_device_id(request: web.Request, data: dict, *, legacy: bool = False) -> str | web.Response:
    auth_context = request["auth_context"]
    body_device_id = str(data.get("device_id") or "").strip()
    role = auth_context.actor_role
    if role == "user":
        return _forbidden("user cannot submit registration profile for arbitrary device")
    if role == "agent":
        actor_device_id = _validate_uuid_device_id(auth_context.actor_id)
        if not actor_device_id:
            return web.json_response({"status": "error", "error": "agent device_id required", "error_code": "VALIDATION_ERROR"}, status=400)
        if body_device_id and _validate_uuid_device_id(body_device_id) != actor_device_id:
            return _forbidden("forbidden device_id")
        return actor_device_id
    if role in {"admin", "support"}:
        device_id = _validate_uuid_device_id(body_device_id)
        if not device_id:
            return web.json_response({"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"}, status=400)
        return device_id
    return _forbidden()


async def _resolve_registration_form_device_id(request: web.Request) -> str | web.Response:
    auth_context = request["auth_context"]
    role = auth_context.actor_role
    if role == "user":
        return _forbidden("user cannot access agent registration form")
    if role == "agent":
        actor_device_id = _validate_uuid_device_id(auth_context.actor_id)
        if not actor_device_id:
            return web.json_response({"status": "error", "error": "agent device_id required", "error_code": "VALIDATION_ERROR"}, status=400)
        body_device_id = str(request.query.get("device_id") or "").strip()
        if body_device_id and _validate_uuid_device_id(body_device_id) != actor_device_id:
            return _forbidden("forbidden device_id")
        return actor_device_id
    if role in {"admin", "support"}:
        device_id = _validate_uuid_device_id(str(request.query.get("device_id") or "").strip())
        if not device_id:
            return web.json_response({"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"}, status=400)
        return device_id
    return _forbidden()


@require_auth("admin")
async def handle_web_admin_registry(_request: web.Request) -> web.Response:
    try:
        async with get_session() as session:
            payload = await RegistrySnapshotService(session).build_snapshot()
    except Exception as exc:
        logger.warning(f"[registry] failed to build admin registry snapshot: {exc}")
        payload = {
            "summary": {
                "assets_count": 0,
                "people_count": 0,
                "locations_count": 0,
                "services_count": 0,
                "vendors_count": 0,
                "data_quality_issue_count": 0,
                "suggestions_count": 0,
            },
            "assets": [],
            "people": [],
            "locations": [],
            "departments": [],
            "services": [],
            "vendors": [],
            "data_quality": [],
            "suggestions": [],
        }
    return _success(payload)


@require_auth("admin", "support", "user", "agent")
async def handle_registry_options(_request: web.Request) -> web.Response:
    async with get_session() as session:
        payload = await build_lightweight_registry_options(session)

    return _success(payload)


@require_auth("admin", "support", "agent")
async def handle_registry_agent_registration_form(request: web.Request) -> web.Response:
    try:
        resolved_device_id = await _resolve_registration_form_device_id(request)
    except RegistrationValidationError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    if isinstance(resolved_device_id, web.Response):
        return resolved_device_id
    device_id = resolved_device_id
    async with get_session() as session:
        if not await _device_exists(session, device_id):
            return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
        payload = await build_registration_form_payload(session, device_id)
    return _success(payload)


@require_auth("admin", "support", "agent")
async def handle_registry_agent_account_state(request: web.Request) -> web.Response:
    try:
        resolved_device_id = await _resolve_registration_form_device_id(request)
    except RegistrationValidationError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    if isinstance(resolved_device_id, web.Response):
        return resolved_device_id
    device_id = resolved_device_id
    async with get_session() as session:
        if not await _device_exists(session, device_id):
            return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
        payload = await build_agent_account_state(session, device_id)
    return _success(payload)


@require_auth("admin", "support", "agent")
async def handle_registry_agent_account_session_confirmed_binding(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        resolved_device_id = await _resolve_registration_form_device_id(request)
    except RegistrationValidationError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    if isinstance(resolved_device_id, web.Response):
        return resolved_device_id
    binding_id = str(data.get("binding_id") or "").strip()
    if not binding_id:
        return web.json_response({"status": "error", "error": "binding_id is required", "error_code": "VALIDATION_ERROR"}, status=400)
    async with get_session() as session:
        if not await _device_exists(session, resolved_device_id):
            return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
        try:
            payload = await AccountSessionService(session).create_confirmed_binding_session(
                device_id=resolved_device_id,
                binding_id=binding_id,
            )
            await session.commit()
        except ValueError as exc:
            return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("agent")
async def handle_registry_agent_browser_pairing_create(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = _validate_uuid_device_id(auth_context.actor_id)
    if not device_id:
        return web.json_response({"status": "error", "error": "agent device_id required", "error_code": "VALIDATION_ERROR"}, status=400)
    data = await request.json() if request.can_read_body else {}
    body_device_id = str(data.get("device_id") or "").strip()
    try:
        if body_device_id and _validate_uuid_device_id(body_device_id) != device_id:
            return _forbidden("forbidden device_id")
    except RegistrationValidationError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    async with get_session() as session:
        if not await _device_exists(session, device_id):
            return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
        try:
            payload = await BrowserPairingService(session).create_pairing(
                device_id=device_id,
                purpose=str(data.get("purpose") or "login"),
                actor_id=auth_context.actor_id,
                agent_version=str(data.get("agent_version") or "").strip() or None,
                user_agent=request.headers.get("User-Agent"),
            )
            await session.commit()
        except ValueError as exc:
            return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


async def _browser_pairing_payload_with_device(session, service: BrowserPairingService, pairing_id: str) -> dict | None:
    row = await service.repo.get_pairing(pairing_id)
    if row is None:
        return None
    payload = await service.serialize_pairing(row)
    device = await session.get(Device, row.device_id)
    payload["device"] = {
        "device_id": row.device_id,
        "hostname": getattr(device, "hostname", None),
        "os": getattr(device, "os", None),
        "agent_version": getattr(device, "agent_version", None),
    }
    return payload


@require_auth("user")
async def handle_web_registry_browser_pairing_code_lookup(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    rate_key = f"{client_ip(request)}:{auth_context.actor_id}"
    if not check_rate_limit("browser_pairing_code_lookup", rate_key, limit=5, window_seconds=60):
        return rate_limited_response()
    try:
        data = await request.json() if request.can_read_body else {}
    except Exception:
        data = {}
    pairing_code = str(data.get("pairing_code") or data.get("code") or "").strip()
    if not pairing_code:
        return web.json_response(
            {"status": "error", "error": "pairing_code is required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    async with get_session() as session:
        service = BrowserPairingService(session)
        payload = await service.lookup_by_pairing_code(pairing_code)
        await session.commit()
    if payload is None:
        return web.json_response(
            {
                "status": "error",
                "error": "pairing code not found or expired",
                "error_code": "PAIRING_CODE_NOT_FOUND",
            },
            status=404,
        )
    return _success(
        {
            "pairing_id": payload["pairing_id"],
            "purpose": payload["purpose"],
            "expires_at": payload.get("expires_at"),
            "next_url": _browser_pairing_next_url(payload),
        }
    )


@require_auth("user")
async def handle_web_registry_browser_pairing_get(request: web.Request) -> web.Response:
    pairing_id = str(request.match_info.get("pairing_id") or "").strip()
    async with get_session() as session:
        service = BrowserPairingService(session)
        payload = await _browser_pairing_payload_with_device(session, service, pairing_id)
        if payload is None:
            return web.json_response({"status": "error", "error": "pairing not found", "error_code": "NOT_FOUND"}, status=404)
    return _success(payload)


@require_auth("user")
async def handle_web_registry_browser_pairing_login_confirm(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    pairing_id = str(request.match_info.get("pairing_id") or "").strip()
    async with get_session() as session:
        service = BrowserPairingService(session)
        try:
            payload = await service.confirm_login_pairing_for_web_user(
                pairing_id=pairing_id,
                actor_id=auth_context.actor_id,
            )
            await session.commit()
        except ValueError as exc:
            message = str(exc)
            if "active binding" in message:
                return web.json_response({"status": "error", "error": message, "error_code": "PAIRING_FORBIDDEN"}, status=403)
            if "not found" in message:
                return web.json_response({"status": "error", "error": message, "error_code": "NOT_FOUND"}, status=404)
            return web.json_response({"status": "error", "error": message, "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("user")
async def handle_web_registry_browser_pairing_registration_confirm(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    pairing_id = str(request.match_info.get("pairing_id") or "").strip()
    async with get_session() as session:
        service = BrowserPairingService(session)
        try:
            payload = await service.confirm_registration_pairing_for_web_user(
                pairing_id=pairing_id,
                actor_id=auth_context.actor_id,
            )
            await session.commit()
        except ValueError as exc:
            message = str(exc)
            if "not found" in message:
                return web.json_response({"status": "error", "error": message, "error_code": "NOT_FOUND"}, status=404)
            return web.json_response({"status": "error", "error": message, "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("agent")
async def handle_registry_agent_browser_pairing_get(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = _validate_uuid_device_id(auth_context.actor_id)
    if not device_id:
        return web.json_response({"status": "error", "error": "agent device_id required", "error_code": "VALIDATION_ERROR"}, status=400)
    pairing_id = str(request.match_info.get("pairing_id") or "").strip()
    try:
        async with get_session() as session:
            payload = await BrowserPairingService(session).pickup_agent_result(
                device_id=device_id,
                pairing_id=pairing_id,
            )
            await session.commit()
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "NOT_FOUND"}, status=404)
    return _success(payload)


@require_auth("agent")
async def handle_registry_agent_account_session_registration_pending(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = _validate_uuid_device_id(auth_context.actor_id)
    if not device_id:
        return web.json_response({"status": "error", "error": "agent device_id required", "error_code": "VALIDATION_ERROR"}, status=400)
    data = await request.json() if request.can_read_body else {}
    claim_id = str(data.get("claim_id") or "").strip()
    if not claim_id:
        return web.json_response({"status": "error", "error": "claim_id is required", "error_code": "VALIDATION_ERROR"}, status=400)
    async with get_session() as session:
        if not await _device_exists(session, device_id):
            return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
        try:
            payload = await AccountSessionService(session).create_registration_pending_session(
                device_id=device_id,
                claim_id=claim_id,
            )
            await session.commit()
        except ValueError as exc:
            return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("agent")
async def handle_registry_agent_account_session_logout(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = _validate_uuid_device_id(auth_context.actor_id)
    if not device_id:
        return web.json_response({"status": "error", "error": "agent device_id required", "error_code": "VALIDATION_ERROR"}, status=400)
    session_id = str(request.match_info.get("session_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await AccountSessionService(session).logout_session(
                device_id=device_id,
                session_id=session_id,
                session_token=str(data.get("session_token") or "").strip() or None,
            )
            await session.commit()
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "ACCOUNT_SESSION_INVALID"}, status=403)
    return _success({"session": payload})


@require_auth("agent")
async def handle_registry_agent_account_login_request_create(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = _validate_uuid_device_id(auth_context.actor_id)
    if not device_id:
        return web.json_response({"status": "error", "error": "agent device_id required", "error_code": "VALIDATION_ERROR"}, status=400)
    data = await request.json() if request.can_read_body else {}
    async with get_session() as session:
        if not await _device_exists(session, device_id):
            return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
        try:
            payload = await AccountSessionService(session).create_other_account_login_request(
                device_id=device_id,
                requested_account=data,
            )
            await session.commit()
        except ValueError as exc:
            return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("agent")
async def handle_registry_agent_account_login_request_get(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = _validate_uuid_device_id(auth_context.actor_id)
    request_id = str(request.match_info.get("request_id") or "").strip()
    async with get_session() as session:
        service = AccountSessionService(session)
        row = await service.repo.get_login_request(request_id)
        if row is None or row.device_id != device_id:
            return web.json_response({"status": "error", "error": "request not found", "error_code": "NOT_FOUND"}, status=404)
        payload = service.serialize_login_request(row, include_session_token=True)
        if row.resulting_session_id:
            session_row = await service.repo.get_session(row.resulting_session_id)
            if session_row:
                payload = {**payload, "session": await service.serialize_session(session_row)}
        if payload.get("session_token"):
            row.metadata_json = {**(row.metadata_json or {})}
            row.metadata_json.pop("session_token_once", None)
            await session.commit()
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_account_login_requests(request: web.Request) -> web.Response:
    status = str(request.query.get("status") or "").strip() or None
    try:
        limit = int(request.query.get("limit") or "100")
    except ValueError:
        limit = 100
    async with get_session() as session:
        items = await AccountSessionService(session).list_login_requests(status=status, limit=limit)
    return _success({"items": items})


@require_auth("admin")
async def handle_web_admin_registry_account_login_request_approve(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    request_id = str(request.match_info.get("request_id") or "").strip()
    async with get_session() as session:
        try:
            payload = await AccountSessionService(session).approve_login_request(request_id, reviewed_by=auth_context.actor_id)
            await session.commit()
        except ValueError as exc:
            return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_account_login_request_reject(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    request_id = str(request.match_info.get("request_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    async with get_session() as session:
        try:
            payload = await AccountSessionService(session).reject_login_request(
                request_id,
                reviewed_by=auth_context.actor_id,
                reason=str(data.get("reason") or "").strip() or "rejected",
            )
            await session.commit()
        except ValueError as exc:
            return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_device_account_sessions(request: web.Request) -> web.Response:
    device_id = str(request.match_info.get("device_id") or "").strip()
    try:
        device_id = _validate_uuid_device_id(device_id) or ""
    except RegistrationValidationError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    async with get_session() as session:
        if not await _device_exists(session, device_id):
            return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
        items = await AccountSessionService(session).list_sessions_for_device_admin(device_id)
    return _success({"device_id": device_id, "items": items})


@require_auth("admin")
async def handle_web_admin_registry_device_account_events(request: web.Request) -> web.Response:
    device_id = str(request.match_info.get("device_id") or "").strip()
    try:
        device_id = _validate_uuid_device_id(device_id) or ""
        limit = int(request.query.get("limit") or "100")
    except RegistrationValidationError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    except ValueError:
        limit = 100
    async with get_session() as session:
        if not await _device_exists(session, device_id):
            return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
        items = await AccountSessionService(session).list_events_for_device_admin(device_id, limit=limit)
    return _success({"device_id": device_id, "items": items})


@require_auth("admin")
async def handle_web_admin_registry_account_session_timeline(request: web.Request) -> web.Response:
    session_id = str(request.match_info.get("session_id") or "").strip()
    try:
        limit = int(request.query.get("limit") or "100")
    except ValueError:
        limit = 100
    async with get_session() as session:
        service = AccountSessionService(session)
        row = await service.repo.get_session(session_id)
        if row is None:
            return web.json_response({"status": "error", "error": "session not found", "error_code": "NOT_FOUND"}, status=404)
        items = await service.list_events_for_session_admin(session_id, limit=limit)
    return _success({"session_id": session_id, "items": items})


@require_auth("admin")
async def handle_web_admin_registry_account_session_revoke(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    session_id = str(request.match_info.get("session_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await AccountSessionService(session).revoke_session(
                session_id=session_id,
                revoked_by=auth_context.actor_id,
                reason=str(data.get("reason") or "").strip() or None,
            )
            await session.commit()
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "NOT_FOUND"}, status=404)
    return _success({"session": payload})


@require_auth("agent")
async def handle_registry_agent_account_session_validate(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = _validate_uuid_device_id(auth_context.actor_id)
    if not device_id:
        return web.json_response({"status": "error", "error": "agent device_id required", "error_code": "VALIDATION_ERROR"}, status=400)
    session_id = str(request.match_info.get("session_id") or "").strip()
    session_token = None
    if request.method == "POST" and request.can_read_body:
        try:
            data = await request.json()
        except Exception:
            data = {}
        session_token = str((data or {}).get("session_token") or "").strip() or None
    if not session_token:
        auth_header = str(request.headers.get("Authorization") or "").strip()
        if auth_header.lower().startswith("account-session "):
            session_token = auth_header.split(" ", 1)[1].strip() or None
    if not session_token:
        session_token = str(request.headers.get("X-Account-Session-Token") or "").strip() or None
    if not session_token and request.query.get("session_token"):
        import config
        if not config.ACCOUNT_SESSION_ALLOW_QUERY_TOKEN:
            return web.json_response(
                {
                    "status": "error",
                    "error": "session_token query parameter is disabled",
                    "error_code": "SESSION_TOKEN_QUERY_DISABLED",
                },
                status=400,
            )
        session_token = str(request.query.get("session_token") or "").strip() or None
    async with get_session() as session:
        payload = await AccountSessionService(session).validate_session(
            device_id=device_id,
            session_id=session_id,
            session_token=session_token,
        )
    status = 200 if payload.get("valid") else 403
    return _success(payload) if status == 200 else web.json_response({"status": "error", "data": payload, "error_code": payload.get("error_code")}, status=status)


@require_auth("admin", "support", "agent")
async def handle_registry_profile_upsert(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json()
    try:
        resolved_device_id = await _resolve_submit_device_id(request, data, legacy=True)
    except RegistrationValidationError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    if isinstance(resolved_device_id, web.Response):
        return resolved_device_id
    device_id = resolved_device_id
    requester_id = str(data.get("requester_id") or auth_context.actor_id or "").strip() or None
    display_name = str(data.get("display_name") or "").strip() or None
    profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}

    async with get_session() as session:
        if not await _device_exists(session, device_id):
            return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
        service = RegistryIngestionService(session)
        result = await service.ingest_requester_profile(
            device_id=device_id,
            requester_id=requester_id,
            display_name=display_name,
            profile=profile,
        )
        repo = service.repo
        person = await repo.get_person(result.person_id)
        location = await repo.get_location(result.location_id)
        asset = await repo.get_asset(result.asset_id)
        await session.commit()

    return _success(
        {
            "person": {
                "person_id": person.person_id if person else None,
                "display_name": person.display_name if person else None,
                "status": person.status if person else None,
            },
            "location": {
                "location_id": location.location_id if location else None,
                "building": location.building if location else None,
                "room": location.room if location else None,
                "status": location.status if location else None,
            },
            "asset": {
                "asset_id": asset.asset_id if asset else None,
                "device_id": asset.device_id if asset else None,
                "name": asset.name if asset else None,
            },
            "registration": result.registration,
        }
    )


@require_auth("admin", "support", "agent")
async def handle_registry_agent_profile(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json()
    try:
        resolved_device_id = await _resolve_submit_device_id(request, data)
    except RegistrationValidationError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    if isinstance(resolved_device_id, web.Response):
        return resolved_device_id
    device_id = resolved_device_id
    requester_id = str(data.get("requester_id") or auth_context.actor_id or "").strip() or None
    display_name = str(data.get("display_name") or "").strip() or None
    profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    if auth_context.actor_role == "agent" and (
        data.get("user_confirmed") is True or profile.get("user_confirmed") is True
    ):
        return web.json_response(
            {
                "status": "error",
                "error": "agent cannot assert user confirmation",
                "error_code": "USER_CONFIRMATION_FORBIDDEN",
            },
            status=403,
        )
    if data.get("user_confirmed") is not None:
        profile = {**profile, "user_confirmed": bool(data.get("user_confirmed"))}
    try:
        async with get_session() as session:
            if not await _device_exists(session, device_id):
                return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
            result = await RegistrationService(session).submit_agent_profile_claim(
                device_id=device_id,
                requester_id=requester_id,
                display_name=display_name,
                profile=profile,
                actor_id=auth_context.actor_id,
                actor_role=auth_context.actor_role,
            )
            await session.commit()
    except (ValueError, RegistrationValidationError) as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(result)


@require_auth("admin", "support", "user", "agent")
async def handle_registry_agent_registration_status(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = str(request.query.get("device_id") or auth_context.actor_id or "").strip()
    if auth_context.actor_role == "agent" and device_id != auth_context.actor_id:
        return web.json_response({"status": "error", "error": "forbidden device_id", "error_code": "FORBIDDEN"}, status=403)
    if auth_context.actor_role == "user":
        return web.json_response({"status": "error", "error": "forbidden device_id", "error_code": "FORBIDDEN"}, status=403)
    try:
        device_id = _validate_uuid_device_id(device_id) or ""
    except RegistrationValidationError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    async with get_session() as session:
        if not await _device_exists(session, device_id):
            return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
        payload = await RegistrationService(session).get_device_registration_status(device_id)
    return _success(payload)


@require_auth("admin", "support", "user", "agent")
async def handle_registry_agent_claim_confirm(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    claim_id = str(request.match_info.get("claim_id") or "").strip()
    async with get_session() as session:
        service = RegistrationService(session)
        claim = await service.repo.get_claim(claim_id)
        if claim is None:
            return web.json_response({"status": "error", "error": "claim not found", "error_code": "NOT_FOUND"}, status=404)
        if not await service.can_confirm_claim_for_actor(claim, auth_context):
            return web.json_response({"status": "error", "error": "forbidden claim", "error_code": "FORBIDDEN"}, status=403)
        payload = await service.confirm_claim_by_user(
            claim_id,
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
        )
        await session.commit()
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_registrations(request: web.Request) -> web.Response:
    status = str(request.query.get("status") or "").strip() or None
    device_id = str(request.query.get("device_id") or "").strip() or None
    person_id = str(request.query.get("person_id") or "").strip() or None
    try:
        limit = int(request.query.get("limit") or "100")
    except ValueError:
        limit = 100
    async with get_session() as session:
        items = await RegistrationService(session).list_registration_claims(
            status=status,
            device_id=device_id,
            person_id=person_id,
            limit=limit,
        )
    return _success({"items": items})


@require_auth("admin")
async def handle_web_admin_registry_registration_approve(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    claim_id = str(request.match_info.get("claim_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).approve_claim(
                claim_id,
                reviewed_by=auth_context.actor_id,
                actor_role=auth_context.actor_role,
                replace_existing=bool(data.get("replace_existing")),
                admin_override_user_confirmation=bool(data.get("admin_override_user_confirmation") or data.get("force")),
                override_reason=str(data.get("reason") or "").strip() or None,
            )
            await session.commit()
    except RegistrationConflictError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "REGISTRATION_CONFLICT"}, status=409)
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_registration_reject(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    claim_id = str(request.match_info.get("claim_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    reason = str(data.get("reason") or "").strip() or "rejected"
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).reject_claim(claim_id, reviewed_by=auth_context.actor_id, reason=reason)
            await session.commit()
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_binding_revoke(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    binding_id = str(request.match_info.get("binding_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    async with get_session() as session:
        payload = await RegistrationService(session).revoke_binding(
            binding_id,
            revoked_by=auth_context.actor_id,
            reason=str(data.get("reason") or "").strip() or None,
        )
        await session.commit()
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_device_bind_person(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = str(request.match_info.get("device_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).bind_person_to_device(
                device_id=device_id,
                person_id=str(data.get("person_id") or "").strip(),
                relationship_type=str(data.get("relationship_type") or "primary_user").strip(),
                replace_existing=bool(data.get("replace_existing")),
                reviewed_by=auth_context.actor_id,
                reason=_text(data.get("reason"), max_length=1000),
            )
            await session.commit()
    except RegistrationConflictError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "REGISTRATION_CONFLICT"}, status=409)
    except (RegistrationValidationError, ValueError) as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_device_transfer_owner_preview(request: web.Request) -> web.Response:
    device_id = str(request.match_info.get("device_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).preview_transfer_owner(
                device_id=device_id,
                new_person_id=str(data.get("new_person_id") or "").strip(),
                old_binding_action=str(data.get("old_binding_action") or "transferred").strip(),
            )
    except (RegistrationConflictError, RegistrationValidationError, ValueError) as exc:
        status = 409 if isinstance(exc, RegistrationConflictError) else 400
        code = "REGISTRATION_CONFLICT" if status == 409 else "VALIDATION_ERROR"
        return web.json_response({"status": "error", "error": str(exc), "error_code": code}, status=status)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_device_transfer_owner(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = str(request.match_info.get("device_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).transfer_owner(
                device_id=device_id,
                new_person_id=str(data.get("new_person_id") or "").strip(),
                old_binding_action=str(data.get("old_binding_action") or "transferred").strip(),
                reviewed_by=auth_context.actor_id,
                reason=_text(data.get("reason"), max_length=1000),
            )
            await session.commit()
    except (RegistrationConflictError, RegistrationValidationError, ValueError) as exc:
        status = 409 if isinstance(exc, RegistrationConflictError) else 400
        code = "REGISTRATION_CONFLICT" if status == 409 else "VALIDATION_ERROR"
        return web.json_response({"status": "error", "error": str(exc), "error_code": code}, status=status)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_device_shared_users(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = str(request.match_info.get("device_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).add_shared_user(
                device_id=device_id,
                person_id=str(data.get("person_id") or "").strip(),
                reviewed_by=auth_context.actor_id,
                reason=_text(data.get("reason"), max_length=1000),
            )
            await session.commit()
    except (RegistrationConflictError, RegistrationValidationError, ValueError) as exc:
        status = 409 if isinstance(exc, RegistrationConflictError) else 400
        code = "REGISTRATION_CONFLICT" if status == 409 else "VALIDATION_ERROR"
        return web.json_response({"status": "error", "error": str(exc), "error_code": code}, status=status)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_device_responsible(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = str(request.match_info.get("device_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).assign_responsible(
                device_id=device_id,
                person_id=str(data.get("person_id") or "").strip(),
                replace_existing=bool(data.get("replace_existing", True)),
                reviewed_by=auth_context.actor_id,
                reason=_text(data.get("reason"), max_length=1000),
            )
            await session.commit()
    except (RegistrationConflictError, RegistrationValidationError, ValueError) as exc:
        status = 409 if isinstance(exc, RegistrationConflictError) else 400
        code = "REGISTRATION_CONFLICT" if status == 409 else "VALIDATION_ERROR"
        return web.json_response({"status": "error", "error": str(exc), "error_code": code}, status=status)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_account_sessions(request: web.Request) -> web.Response:
    device_id = str(request.query.get("device_id") or "").strip() or None
    person_id = str(request.query.get("person_id") or "").strip() or None
    status = str(request.query.get("verification_status") or request.query.get("status") or "").strip() or None
    try:
        limit = int(request.query.get("limit") or "200")
    except ValueError:
        limit = 200
    async with get_session() as session:
        items = await AccountSessionService(session).list_sessions_admin(
            device_id=device_id,
            person_id=person_id,
            verification_status=status,
            limit=limit,
        )
    return _success({"items": items})


@require_auth("admin")
async def handle_web_admin_registry_people_create(request: web.Request) -> web.Response:
    data = await request.json() if request.can_read_body else {}
    auth_context = request["auth_context"]
    display_name = _text(data.get("display_name") or data.get("full_name"), max_length=300)
    if not display_name:
        return web.json_response({"status": "error", "error": "display_name is required", "error_code": "VALIDATION_ERROR"}, status=400)
    async with get_session() as session:
        person = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name=display_name,
            full_name=_text(data.get("full_name"), max_length=300),
            phone=_text(data.get("phone"), max_length=80),
            email=_text(data.get("email"), max_length=320),
            department_id=_text(data.get("department_id"), max_length=36),
            location_id=_text(data.get("location_id"), max_length=36),
            source="manual",
            status=_text(data.get("status"), max_length=40) or "active",
            metadata_json={"reason": _text(data.get("reason"), max_length=1000)},
        )
        session.add(person)
        await session.flush()
        await RegistryAdminOperationsService(session).append_event(
            object_type="person",
            object_id=person.person_id,
            event_type="person_created",
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
            reason=_text(data.get("reason"), max_length=1000),
            related_person_id=person.person_id,
            payload={
                "person_id": person.person_id,
                "after": {
                    "display_name": person.display_name,
                    "full_name": person.full_name,
                    "email": person.email,
                    "phone": person.phone,
                    "department_id": person.department_id,
                    "location_id": person.location_id,
                    "status": person.status,
                    "source": person.source,
                },
            },
        )
        payload = {"person": {"person_id": person.person_id, "display_name": person.display_name}}
        await session.commit()
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_person_update(request: web.Request) -> web.Response:
    person_id = str(request.match_info.get("person_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    auth_context = request["auth_context"]
    async with get_session() as session:
        person = await session.get(RegistryPerson, person_id)
        if person is None:
            return web.json_response({"status": "error", "error": "person not found", "error_code": "NOT_FOUND"}, status=404)
        previous_status = person.status
        before = {
            "display_name": person.display_name,
            "full_name": person.full_name,
            "phone": person.phone,
            "email": person.email,
            "department_id": person.department_id,
            "location_id": person.location_id,
            "status": person.status,
        }
        for field, max_length in {
            "display_name": 300,
            "full_name": 300,
            "phone": 80,
            "email": 320,
            "department_id": 36,
            "location_id": 36,
            "status": 40,
        }.items():
            if field in data:
                setattr(person, field, _text(data.get(field), max_length=max_length))
        if not person.display_name:
            return web.json_response({"status": "error", "error": "display_name is required", "error_code": "VALIDATION_ERROR"}, status=400)
        revoked_bindings: list[dict[str, object]] = []
        if previous_status != person.status and person.status in {"inactive", "deactivated", "disabled"}:
            active_bindings = (
                await session.execute(
                    select(DeviceUserBinding).where(
                        DeviceUserBinding.person_id == person.person_id,
                        DeviceUserBinding.status == "active",
                    )
                )
            ).scalars().all()
            service = RegistrationService(session)
            reason = _text(data.get("reason"), max_length=1000) or f"person {person.status}"
            for binding in active_bindings:
                result = await service.revoke_binding(
                    binding.binding_id,
                    revoked_by=auth_context.actor_id,
                    reason=reason,
                )
                revoked_bindings.append(result["binding"])
        payload = {
            "person": {"person_id": person.person_id, "display_name": person.display_name, "status": person.status},
            "revoked_bindings": revoked_bindings,
        }
        await RegistryAdminOperationsService(session).append_event(
            object_type="person",
            object_id=person.person_id,
            event_type="person_updated",
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
            reason=_text(data.get("reason"), max_length=1000),
            related_person_id=person.person_id,
            payload={
                "person_id": person.person_id,
                "before": before,
                "after": {
                    "display_name": person.display_name,
                    "full_name": person.full_name,
                    "phone": person.phone,
                    "email": person.email,
                    "department_id": person.department_id,
                    "location_id": person.location_id,
                    "status": person.status,
                },
                "revoked_binding_ids": [row.get("binding_id") for row in revoked_bindings],
            },
        )
        await session.commit()
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_person_identity_create(request: web.Request) -> web.Response:
    person_id = str(request.match_info.get("person_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    auth_context = request["auth_context"]
    provider = str(data.get("provider") or "").strip()
    identifier = str(data.get("identifier") or "").strip()
    if not provider or not identifier:
        return web.json_response({"status": "error", "error": "provider and identifier are required", "error_code": "VALIDATION_ERROR"}, status=400)
    async with get_session() as session:
        if await session.get(RegistryPerson, person_id) is None:
            return web.json_response({"status": "error", "error": "person not found", "error_code": "NOT_FOUND"}, status=404)
        identity = await RegistrationService(session).repo.create_or_update_person_identity(
            person_id=person_id,
            provider=provider,
            identifier=identifier,
            verified=bool(data.get("verified")),
            source="admin_manual",
            metadata={"reason": _text(data.get("reason"), max_length=1000)},
        )
        if identity is None:
            return web.json_response({"status": "error", "error": "identity is empty", "error_code": "VALIDATION_ERROR"}, status=400)
        if identity.person_id != person_id:
            return web.json_response(
                {
                    "status": "error",
                    "error": "identity already belongs to another person",
                    "error_code": "IDENTITY_COLLISION",
                    "collision_person_id": identity.person_id,
                },
                status=409,
            )
        await RegistryAdminOperationsService(session).append_event(
            object_type="identity",
            object_id=identity.identity_id,
            event_type="identity_added",
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
            reason=_text(data.get("reason"), max_length=1000),
            related_person_id=person_id,
            payload={
                "identity_id": identity.identity_id,
                "person_id": person_id,
                "after": {
                    "provider": identity.provider,
                    "identifier": identity.identifier,
                    "normalized_identifier": identity.normalized_identifier,
                    "verified": identity.verified,
                    "source": identity.source,
                },
            },
        )
        if identity.verified:
            await RegistryAdminOperationsService(session).append_event(
                object_type="identity",
                object_id=identity.identity_id,
                event_type="identity_verified",
                actor_id=auth_context.actor_id,
                actor_role=auth_context.actor_role,
                reason=_text(data.get("reason"), max_length=1000),
                related_person_id=person_id,
                payload={"identity_id": identity.identity_id, "person_id": person_id, "changes": [{"field": "verified", "after": True}]},
            )
        payload = {"identity": {
            "identity_id": identity.identity_id,
            "person_id": identity.person_id,
            "provider": identity.provider,
            "identifier": identity.identifier,
            "normalized_identifier": identity.normalized_identifier,
            "verified": identity.verified,
            "source": identity.source,
            "last_seen_at": identity.last_seen_at.isoformat() if identity.last_seen_at else None,
        }}
        await session.commit()
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_ui_user_link_person(request: web.Request) -> web.Response:
    user_login = str(request.match_info.get("user_login") or "").strip()
    data = await request.json() if request.can_read_body else {}
    person_id = str(data.get("person_id") or "").strip()
    auth_context = request["auth_context"]
    if not user_login or not person_id:
        return web.json_response({"status": "error", "error": "user_login and person_id are required", "error_code": "VALIDATION_ERROR"}, status=400)
    async with get_session() as session:
        user = await session.get(UiUser, user_login)
        if user is None:
            return web.json_response({"status": "error", "error": "ui user not found", "error_code": "NOT_FOUND"}, status=404)
        person = await session.get(RegistryPerson, person_id)
        if person is None:
            return web.json_response({"status": "error", "error": "person not found", "error_code": "NOT_FOUND"}, status=404)
        repo = RegistrationService(session).repo
        before_identity = await repo.find_identity("ui_login", user.user_login)
        before_verified = bool(before_identity.verified) if before_identity is not None else False
        identity = await repo.create_or_update_person_identity(
            person_id=person_id,
            provider="ui_login",
            identifier=user.user_login,
            verified=True,
            source="admin_manual",
            metadata={"reason": _text(data.get("reason"), max_length=1000), "ui_user_login": user.user_login},
        )
        if identity is None:
            return web.json_response({"status": "error", "error": "identity is empty", "error_code": "VALIDATION_ERROR"}, status=400)
        if identity.person_id != person_id:
            return web.json_response(
                {
                    "status": "error",
                    "error": "ui user login already belongs to another person",
                    "error_code": "IDENTITY_COLLISION",
                    "collision_person_id": identity.person_id,
                },
                status=409,
            )
        event_type = "identity_added" if before_identity is None else ("identity_verified" if not before_verified else "identity_updated")
        await RegistryAdminOperationsService(session).append_event(
            object_type="identity",
            object_id=identity.identity_id,
            event_type=event_type,
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
            reason=_text(data.get("reason"), max_length=1000),
            related_person_id=person_id,
            payload={
                "identity_id": identity.identity_id,
                "person_id": person_id,
                "ui_user_login": user.user_login,
                "after": {
                    "provider": identity.provider,
                    "identifier": identity.identifier,
                    "normalized_identifier": identity.normalized_identifier,
                    "verified": identity.verified,
                    "source": identity.source,
                },
            },
        )
        payload = {
            "ui_user": {
                "user_login": user.user_login,
                "actor_role": user.actor_role,
                "is_active": bool(user.is_active),
                "failed_attempts": int(user.failed_attempts or 0),
                "locked_until": user.locked_until.isoformat() if user.locked_until else None,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                "linked_person_id": person.person_id,
                "linked_person_name": person.display_name,
                "linked_identity_id": identity.identity_id,
                "linked_identity_verified": bool(identity.verified),
            },
            "person": {
                "person_id": person.person_id,
                "display_name": person.display_name,
                "email": person.email,
                "status": person.status,
            },
            "identity": {
                "identity_id": identity.identity_id,
                "person_id": identity.person_id,
                "provider": identity.provider,
                "identifier": identity.identifier,
                "normalized_identifier": identity.normalized_identifier,
                "verified": identity.verified,
                "source": identity.source,
                "last_seen_at": identity.last_seen_at.isoformat() if identity.last_seen_at else None,
            },
        }
        await session.commit()
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_person_identity_update(request: web.Request) -> web.Response:
    identity_id = str(request.match_info.get("identity_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    auth_context = request["auth_context"]
    async with get_session() as session:
        identity = await session.get(RegistryPersonIdentity, identity_id)
        if identity is None:
            return web.json_response({"status": "error", "error": "identity not found", "error_code": "NOT_FOUND"}, status=404)
        before = {"verified": identity.verified, "source": identity.source}
        if "verified" in data:
            identity.verified = bool(data.get("verified"))
        if "source" in data:
            identity.source = _text(data.get("source"), max_length=40) or identity.source
        event_type = "identity_verified" if before["verified"] is not True and identity.verified is True else "identity_updated"
        await RegistryAdminOperationsService(session).append_event(
            object_type="identity",
            object_id=identity.identity_id,
            event_type=event_type,
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
            reason=_text(data.get("reason"), max_length=1000),
            related_person_id=identity.person_id,
            payload={
                "identity_id": identity.identity_id,
                "person_id": identity.person_id,
                "before": before,
                "after": {"verified": identity.verified, "source": identity.source},
            },
        )
        payload = {"identity": {"identity_id": identity.identity_id, "verified": identity.verified, "source": identity.source}}
        await session.commit()
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_person_identity_delete(request: web.Request) -> web.Response:
    identity_id = str(request.match_info.get("identity_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    auth_context = request["auth_context"]
    async with get_session() as session:
        identity = await session.get(RegistryPersonIdentity, identity_id)
        if identity is None:
            return web.json_response({"status": "error", "error": "identity not found", "error_code": "NOT_FOUND"}, status=404)
        person_id = identity.person_id
        await RegistryAdminOperationsService(session).append_event(
            object_type="identity",
            object_id=identity.identity_id,
            event_type="identity_deleted",
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
            reason=_text(data.get("reason"), max_length=1000),
            related_person_id=identity.person_id,
            payload={
                "identity_id": identity.identity_id,
                "person_id": identity.person_id,
                "before": {
                    "provider": identity.provider,
                    "identifier": identity.identifier,
                    "normalized_identifier": identity.normalized_identifier,
                    "verified": identity.verified,
                    "source": identity.source,
                },
                "after": None,
            },
        )
        await session.delete(identity)
        await session.commit()
    return _success({"identity_id": identity_id, "person_id": person_id, "deleted": True})


def _registry_admin_error(exc: Exception) -> web.Response:
    if isinstance(exc, LookupError):
        return web.json_response({"status": "error", "error": str(exc), "error_code": "NOT_FOUND"}, status=404)
    return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)


@require_auth("admin")
async def handle_web_admin_registry_locations(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            service = RegistryAdminOperationsService(session)
            if request.method == "POST":
                payload = await service.create_location(data, actor_id=auth_context.actor_id)
                await session.commit()
            else:
                payload = {"items": await service.list_locations()}
    except ValueError as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_location_update(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    location_id = str(request.match_info.get("location_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).update_location(location_id, data, actor_id=auth_context.actor_id)
            await session.commit()
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_location_archive(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    location_id = str(request.match_info.get("location_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).archive_location(location_id, data, actor_id=auth_context.actor_id)
            await session.commit()
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_locations_merge_preview(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).preview_merge_locations(data, actor_id=auth_context.actor_id)
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_locations_merge(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).merge_locations(data, actor_id=auth_context.actor_id)
            await session.commit()
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_departments(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            service = RegistryAdminOperationsService(session)
            if request.method == "POST":
                payload = await service.create_department(data, actor_id=auth_context.actor_id)
                await session.commit()
            else:
                payload = {"items": await service.list_departments()}
    except ValueError as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_department_update(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    department_id = str(request.match_info.get("department_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).update_department(department_id, data, actor_id=auth_context.actor_id)
            await session.commit()
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_department_archive(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    department_id = str(request.match_info.get("department_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).archive_department(department_id, data, actor_id=auth_context.actor_id)
            await session.commit()
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_departments_merge_preview(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).preview_merge_departments(data, actor_id=auth_context.actor_id)
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_departments_merge(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).merge_departments(data, actor_id=auth_context.actor_id)
            await session.commit()
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_policies(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            service = RegistryAdminOperationsService(session)
            if request.method == "PATCH":
                payload = await service.update_policies(data, actor_id=auth_context.actor_id)
                await session.commit()
            else:
                payload = await service.get_policies()
    except ValueError as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_policies_preview(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).preview_policies(data, actor_id=auth_context.actor_id)
    except ValueError as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_policies_reset(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).reset_policies(data, actor_id=auth_context.actor_id)
            await session.commit()
    except ValueError as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_people_merge_preview(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).preview_merge_people(data, actor_id=auth_context.actor_id)
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_people_merge(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).merge_people(data, actor_id=auth_context.actor_id)
            await session.commit()
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_bulk_preview(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).preview_bulk(data, actor_id=auth_context.actor_id)
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_bulk_devices_assign_location(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).bulk_assign_location(data, actor_id=auth_context.actor_id)
            await session.commit()
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_bulk_devices_assign_department(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).bulk_assign_department(data, actor_id=auth_context.actor_id, target="devices")
            await session.commit()
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_bulk_people_assign_department(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).bulk_assign_department(data, actor_id=auth_context.actor_id, target="people")
            await session.commit()
    except (LookupError, ValueError) as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_bulk_devices_revoke_account_sessions(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).bulk_revoke_sessions(data, actor_id=auth_context.actor_id, by_device=True)
            await session.commit()
    except ValueError as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_bulk_account_sessions_revoke(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).bulk_revoke_sessions(data, actor_id=auth_context.actor_id)
            await session.commit()
    except ValueError as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_export(request: web.Request) -> web.Response:
    export_type = str(request.query.get("type") or "devices").strip()
    export_format = str(request.query.get("format") or "csv").strip().lower()
    if export_format != "csv":
        return web.json_response({"status": "error", "error": "only csv export is supported", "error_code": "VALIDATION_ERROR"}, status=400)
    try:
        async with get_session() as session:
            csv_text = await RegistryAdminOperationsService(session).export_csv(export_type)
    except ValueError as exc:
        return _registry_admin_error(exc)
    filename = f"registry-{export_type}.csv"
    return web.Response(
        text=csv_text,
        content_type="text/csv",
        charset="utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@require_auth("admin")
async def handle_web_admin_registry_import_preview(request: web.Request) -> web.Response:
    data = await request.json() if request.can_read_body else {}
    import_format = str(data.get("format") or "csv").strip().lower()
    if import_format != "csv":
        return web.json_response({"status": "error", "error": "only csv import is supported", "error_code": "VALIDATION_ERROR"}, status=400)
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).preview_import_csv(
                str(data.get("type") or ""),
                str(data.get("csv_text") or ""),
            )
    except ValueError as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_import_apply(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json() if request.can_read_body else {}
    import_format = str(data.get("format") or "csv").strip().lower()
    if import_format != "csv":
        return web.json_response({"status": "error", "error": "only csv import is supported", "error_code": "VALIDATION_ERROR"}, status=400)
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).apply_import_csv(
                str(data.get("type") or ""),
                str(data.get("csv_text") or ""),
                preview_id=str(data.get("preview_id") or ""),
                actor_id=auth_context.actor_id,
                reason=str(data.get("reason") or ""),
            )
            await session.commit()
    except ValueError as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_quality_ignore(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    issue_key = str(request.match_info.get("issue_key") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).set_quality_issue_state(
                issue_key,
                status="ignored",
                reason=str(data.get("reason") or ""),
                actor_id=auth_context.actor_id,
            )
            await session.commit()
    except ValueError as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_quality_snooze(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    issue_key = str(request.match_info.get("issue_key") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).set_quality_issue_state(
                issue_key,
                status="snoozed",
                reason=str(data.get("reason") or ""),
                actor_id=auth_context.actor_id,
                days=int(data.get("days") or 7),
            )
            await session.commit()
    except ValueError as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_quality_resolve(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    issue_key = str(request.match_info.get("issue_key") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistryAdminOperationsService(session).set_quality_issue_state(
                issue_key,
                status="resolved",
                reason=str(data.get("reason") or ""),
                actor_id=auth_context.actor_id,
            )
            await session.commit()
    except ValueError as exc:
        return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_timeline(request: web.Request) -> web.Response:
    object_type = str(request.match_info.get("object_type") or "").strip()
    object_id = str(request.match_info.get("object_id") or "").strip()
    try:
        limit = int(request.query.get("limit") or "100")
    except ValueError:
        limit = 100
    async with get_session() as session:
        items = await RegistryAdminOperationsService(session).list_timeline(
            object_type=object_type,
            object_id=object_id,
            limit=limit,
        )
    return _success({"items": items})


@require_auth("admin")
async def handle_web_admin_registry_device_timeline(request: web.Request) -> web.Response:
    device_id = str(request.match_info.get("device_id") or "").strip()
    async with get_session() as session:
        items = await RegistrationService(session).get_timeline(device_id)
    return _success({"device_id": device_id, "items": items})
