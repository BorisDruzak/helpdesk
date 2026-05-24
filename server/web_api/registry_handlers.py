from __future__ import annotations

from aiohttp import web
from loguru import logger

from app.db import get_session
from app.db.models import Device
from auth.middleware import require_auth
from registry.account_state_service import build_agent_account_state
from registry.account_session_service import AccountSessionService
from registry.registration_form_service import build_lightweight_registry_options, build_registration_form_payload
from registry.registration_service import RegistrationConflictError, RegistrationService, RegistrationValidationError
from registry.service import RegistryIngestionService, RegistrySnapshotService

import uuid


def _success(data: dict) -> web.Response:
    return web.json_response({"status": "success", "data": data})


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
async def handle_web_admin_registry_device_timeline(request: web.Request) -> web.Response:
    device_id = str(request.match_info.get("device_id") or "").strip()
    async with get_session() as session:
        items = await RegistrationService(session).get_timeline(device_id)
    return _success({"device_id": device_id, "items": items})
