from __future__ import annotations

from datetime import datetime, timezone

from aiohttp import web
from loguru import logger
from sqlalchemy import select

from app.db import get_session
from app.db.models import Device, DeviceAccountSession, DeviceUserBinding, RegistryPerson, RegistryPersonIdentity, UiUser, UiUserAudit
from app.repos.auth_tokens_repo import AuthTokensRepo
from auth.middleware import ensure_server_request_id, require_auth
from auth.password_service import PasswordPolicyError
from auth.rate_limit import check_rate_limit, client_ip, rate_limited_response
from auth.service import AuthService
from observer.web_event_writer import write_web_cabinet_observer_event
from registry.account_state_service import build_agent_account_state
from registry.account_session_service import AccountSessionService
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.audience_group_service import RegistryAudienceService
from registry.effective_identity_service import EffectiveIdentityService
from registry.password_reset_service import PasswordResetRequestService
from registry.registration_form_service import build_lightweight_registry_options, build_registration_form_payload
from registry.registration_service import RegistrationConflictError, RegistrationService, RegistrationValidationError
from registry.service import RegistryIngestionService, RegistrySnapshotService
from registry.profile_schema_service import ProfileSchemaValidationError, RequesterProfileSchemaService
from requester.identity_service import RequesterIdentityResolver

import uuid


WEB_BROWSER_PAIRING_ROLES = ("admin", "support", "user")


def _success(data: dict) -> web.Response:
    return web.json_response({"status": "success", "data": data})


def _text(value: object, *, max_length: int = 500) -> str | None:
    text = str(value or "").strip()
    return text[:max_length] if text else None


async def _disable_ui_user_access(
    session,
    user: UiUser,
    *,
    actor_id: str | None,
    reason: str | None,
    action: str,
    related_person_id: str | None = None,
) -> dict[str, object]:
    revoked_tokens = await AuthTokensRepo(session).revoke_active_ui_tokens_for_user(user.user_login, commit=False)
    was_active = bool(user.is_active)
    if was_active:
        user.is_active = False
    if was_active or revoked_tokens:
        session.add(
            UiUserAudit(
                user_login=user.user_login,
                action=action,
                actor_id=actor_id,
                details_json={
                    "reason": reason,
                    "related_person_id": related_person_id,
                    "revoked_ui_tokens": revoked_tokens,
                    "was_active": was_active,
                },
            )
        )
    return {
        "user_login": user.user_login,
        "actor_role": user.actor_role,
        "was_active": was_active,
        "is_active": False,
        "revoked_ui_tokens": revoked_tokens,
    }


async def _disable_linked_requester_ui_users(
    session,
    *,
    person_id: str,
    actor_id: str | None,
    reason: str | None,
) -> list[dict[str, object]]:
    identities = (
        await session.execute(
            select(RegistryPersonIdentity).where(
                RegistryPersonIdentity.person_id == person_id,
                RegistryPersonIdentity.provider == "ui_login",
            )
        )
    ).scalars().all()

    disabled: list[dict[str, object]] = []
    seen: set[str] = set()
    for identity in identities:
        user_login = str(identity.identifier or "").strip()
        if not user_login or user_login.lower() in seen:
            continue
        seen.add(user_login.lower())
        user = await session.get(UiUser, user_login)
        if user is None or user.actor_role != "user":
            continue
        result = await _disable_ui_user_access(
            session,
            user,
            actor_id=actor_id,
            reason=reason,
            action="disabled_by_person_archive",
            related_person_id=person_id,
        )
        if result["was_active"] or result["revoked_ui_tokens"]:
            disabled.append(result)
    return disabled


def _observer_actor_context(
    request: web.Request,
    *,
    actor_id: str | None,
    actor_role: str | None,
) -> dict[str, str | None]:
    return {
        "actor_id": actor_id,
        "actor_role": actor_role,
        "method": request.method,
        "server_request_id": ensure_server_request_id(request),
        "request_id": _text(request.headers.get("X-Request-ID"), max_length=120),
        "correlation_id": (
            _text(request.headers.get("X-Request-ID"), max_length=120)
            or _text(request.headers.get("X-Correlation-ID"), max_length=120)
        ),
    }


async def _write_device_linking_observer_event(
    session,
    request: web.Request,
    *,
    event_type: str,
    severity: str,
    result: str,
    device_id: str | None = None,
    person_id: str | None = None,
    error_code: str | None = None,
    payload: dict | None = None,
    route: str | None = None,
) -> None:
    auth_context = request.get("auth_context")
    try:
        await write_web_cabinet_observer_event(
            session,
            source="device_linking",
            event_type=event_type,
            severity=severity,
            route=route or request.path,
            actor_context=_observer_actor_context(
                request,
                actor_id=getattr(auth_context, "actor_id", None),
                actor_role=getattr(auth_context, "actor_role", None),
            ),
            result=result,
            device_id=device_id,
            person_id=person_id,
            error_code=error_code,
            payload=payload,
        )
    except Exception as exc:
        logger.warning(f"[device_linking_observer] failed to write {event_type}: {exc}")


async def _write_registry_binding_observer_event(
    session,
    request: web.Request,
    *,
    event_type: str,
    severity: str,
    result: str,
    device_id: str | None = None,
    person_id: str | None = None,
    error_code: str | None = None,
    payload: dict | None = None,
    route: str | None = None,
) -> None:
    auth_context = request.get("auth_context")
    try:
        await write_web_cabinet_observer_event(
            session,
            source="registry_binding",
            event_type=event_type,
            severity=severity,
            route=route or request.path,
            actor_context=_observer_actor_context(
                request,
                actor_id=getattr(auth_context, "actor_id", None),
                actor_role=getattr(auth_context, "actor_role", None),
            ),
            result=result,
            device_id=device_id,
            person_id=person_id,
            error_code=error_code,
            payload=payload,
        )
    except Exception as exc:
        logger.warning(f"[registry_binding_observer] failed to write {event_type}: {exc}")


async def _write_registry_binding_created_observer_event(
    session,
    request: web.Request,
    *,
    response_payload: dict,
    device_id: str,
    person_id: str | None,
    relationship_type: str,
    replace_existing: bool,
    reason: str | None,
    route: str,
) -> None:
    binding = response_payload.get("binding") if isinstance(response_payload, dict) else {}
    asset = response_payload.get("asset") if isinstance(response_payload, dict) else {}
    events = response_payload.get("events") if isinstance(response_payload, dict) else {}
    if not isinstance(binding, dict):
        binding = {}
    if not isinstance(asset, dict):
        asset = {}
    if not isinstance(events, dict):
        events = {}
    await _write_registry_binding_observer_event(
        session,
        request,
        event_type="registry_binding_created",
        severity="info",
        result="succeeded",
        device_id=str(binding.get("device_id") or asset.get("device_id") or device_id or "") or None,
        person_id=str(binding.get("person_id") or person_id or "") or None,
        payload={
            "binding_status": binding.get("status"),
            "relationship_type": binding.get("relationship_type") or relationship_type,
            "replace_existing": replace_existing,
            "reason_present": bool(reason),
            "reused_existing_binding": bool(events.get("reused_existing_binding") or False),
            "satisfied_pending_claim": bool(events.get("satisfied_pending_claim") or False),
        },
        route=route,
    )


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


def _requester_profile_incomplete_response(completion: dict) -> web.Response:
    return web.json_response(
        {
            "status": "error",
            "error": "Заполните профиль, чтобы продолжить работу в кабинете пользователя.",
            "error_code": "REQUESTER_PROFILE_INCOMPLETE",
            "details": completion,
        },
        status=403,
    )


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


@require_auth("admin")
async def handle_web_admin_registry_profile_schema(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        service = RequesterProfileSchemaService(session)
        if request.method == "GET":
            return _success({"schema": await service.get_schema()})
        data = await request.json() if request.can_read_body else {}
        if not isinstance(data, dict):
            data = {}
        try:
            payload = await service.save_schema(data, actor_id=auth_context.actor_id)
            await session.commit()
        except ProfileSchemaValidationError as exc:
            await session.rollback()
            return web.json_response(
                {
                    "status": "error",
                    "error": str(exc),
                    "error_code": "VALIDATION_ERROR",
                    "details": exc.details,
                },
                status=400,
            )
        except ValueError as exc:
            await session.rollback()
            return _registry_admin_error(exc)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_profile_schema_preview(request: web.Request) -> web.Response:
    data = await request.json() if request.can_read_body else {}
    if not isinstance(data, dict):
        data = {}
    async with get_session() as session:
        try:
            payload = await RequesterProfileSchemaService(session).preview_schema(data)
        except ProfileSchemaValidationError as exc:
            return web.json_response(
                {
                    "status": "error",
                    "error": str(exc),
                    "error_code": "VALIDATION_ERROR",
                    "details": exc.details,
                },
                status=400,
            )
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_effective_identity(request: web.Request) -> web.Response:
    actor_id = str(request.query.get("actor_id") or "").strip()
    actor_role = str(request.query.get("actor_role") or "user").strip()
    if not actor_id:
        return web.json_response(
            {"status": "error", "error": "actor_id is required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    async with get_session() as session:
        identity = await EffectiveIdentityService(session).resolve_actor_identity(actor_id, actor_role)
    return _success({"identity": identity.to_dict()})


@require_auth("admin")
async def handle_web_admin_registry_person_audience(request: web.Request) -> web.Response:
    person_id = str(request.match_info.get("person_id") or "").strip()
    actor_id = str(request.query.get("actor_id") or "").strip() or None
    actor_role = str(request.query.get("actor_role") or "user").strip()
    async with get_session() as session:
        audience = await EffectiveIdentityService(session).resolve_person_audience(
            person_id=person_id,
            actor_id=actor_id,
            actor_role=actor_role,
        )
    return _success({"audience": audience.to_dict()})


@require_auth("admin")
async def handle_web_admin_registry_account_session_identity_explain(request: web.Request) -> web.Response:
    session_id = str(request.match_info.get("session_id") or "").strip()
    if not session_id:
        return web.json_response(
            {"status": "error", "error": "session_id is required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    device_id = str(request.query.get("device_id") or "").strip()
    session_token = str(
        request.headers.get("X-Account-Session-Token") or request.query.get("session_token") or ""
    ).strip() or None
    async with get_session() as session:
        if not device_id:
            row = await session.get(DeviceAccountSession, session_id)
            if row is None:
                return web.json_response(
                    {"status": "error", "error": "account session not found", "error_code": "NOT_FOUND"},
                    status=404,
                )
            device_id = str(row.device_id)
        identity = await EffectiveIdentityService(session).resolve_account_session_identity(
            device_id=device_id,
            session_id=session_id,
            session_token=session_token,
        )
    return _success({"identity": identity.to_dict()})


@require_auth("admin")
async def handle_web_admin_registry_audience_groups(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        service = RegistryAudienceService(session)
        if request.method == "GET":
            include_archived = str(request.query.get("include_archived") or "").strip().lower() in {"1", "true", "yes"}
            return _success({"groups": await service.list_groups(include_archived=include_archived)})
        try:
            data = await request.json()
            group = await service.create_group(
                code=str(data.get("code") or ""),
                name=str(data.get("name") or ""),
                description=data.get("description"),
                source=str(data.get("source") or "manual"),
                actor_id=auth_context.actor_id,
                reason=_text(data.get("reason"), max_length=1000),
            )
            await session.commit()
            return _success({"group": group})
        except Exception as exc:
            await session.rollback()
            return _registry_admin_error(exc)


@require_auth("admin")
async def handle_web_admin_registry_audience_group_update(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    audience_group_id = str(request.match_info.get("audience_group_id") or "").strip()
    async with get_session() as session:
        try:
            data = await request.json()
            group = await RegistryAudienceService(session).update_group(
                audience_group_id,
                fields=data,
                actor_id=auth_context.actor_id,
                reason=_text(data.get("reason"), max_length=1000),
            )
            await session.commit()
            return _success({"group": group})
        except Exception as exc:
            await session.rollback()
            return _registry_admin_error(exc)


@require_auth("admin")
async def handle_web_admin_registry_audience_group_archive(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    audience_group_id = str(request.match_info.get("audience_group_id") or "").strip()
    async with get_session() as session:
        try:
            data = await request.json() if request.can_read_body else {}
            group = await RegistryAudienceService(session).archive_group(
                audience_group_id,
                actor_id=auth_context.actor_id,
                reason=_text(data.get("reason"), max_length=1000),
            )
            await session.commit()
            return _success({"group": group})
        except Exception as exc:
            await session.rollback()
            return _registry_admin_error(exc)


@require_auth("admin")
async def handle_web_admin_registry_audience_group_members(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    audience_group_id = str(request.match_info.get("audience_group_id") or "").strip()
    async with get_session() as session:
        service = RegistryAudienceService(session)
        if request.method == "GET":
            try:
                return _success({"members": await service.list_members(audience_group_id)})
            except Exception as exc:
                return _registry_admin_error(exc)
        try:
            data = await request.json()
            members = await service.set_members(
                audience_group_id,
                data.get("members") or [],
                actor_id=auth_context.actor_id,
                reason=_text(data.get("reason"), max_length=1000),
            )
            await session.commit()
            return _success({"members": members})
        except Exception as exc:
            await session.rollback()
            return _registry_admin_error(exc)


@require_auth("admin")
async def handle_web_admin_registry_audience_group_preview_members(request: web.Request) -> web.Response:
    audience_group_id = str(request.match_info.get("audience_group_id") or "").strip()
    async with get_session() as session:
        try:
            data = await request.json() if request.can_read_body else {}
            preview = await RegistryAudienceService(session).preview_members(
                audience_group_id,
                members=data.get("members") if isinstance(data.get("members"), list) else None,
            )
            return _success({"preview": preview})
        except Exception as exc:
            return _registry_admin_error(exc)


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
        await session.commit()
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
async def handle_registry_agent_account_session_login(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = _validate_uuid_device_id(auth_context.actor_id)
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "agent device_id required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        data = await request.json() if request.can_read_body else {}
    except Exception:
        data = {}
    login = str(data.get("login") or "").strip()
    password = str(data.get("password") or "")
    if not login or not password:
        return web.json_response(
            {"status": "error", "error": "login and password are required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    rate_key = f"{client_ip(request)}:{device_id}:{login.lower()}"
    if not check_rate_limit("agent_gui_password_login", rate_key, limit=10, window_seconds=60):
        return rate_limited_response()
    try:
        ok, actor_role = await AuthService(request.app["state"]).authenticate(login, password)
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Authentication backend unavailable", "error_code": "AUTH_BACKEND_UNAVAILABLE"},
            status=503,
        )
    if not ok:
        return web.json_response(
            {
                "status": "error",
                "error": "Invalid login or password",
                "error_code": "INVALID_CREDENTIALS",
            },
            status=401,
        )
    if actor_role != "user":
        return web.json_response(
            {
                "status": "error",
                "error": "Account is not available on this agent",
                "error_code": "ACCOUNT_SESSION_DEVICE_MISMATCH",
            },
            status=403,
        )
    async with get_session() as session:
        if not await _device_exists(session, device_id):
            return web.json_response(
                {"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"},
                status=404,
            )
        try:
            payload = await AccountSessionService(session).create_gui_password_session(
                device_id=device_id,
                login=login,
            )
            await session.commit()
        except PermissionError:
            await session.rollback()
            return web.json_response(
                {
                    "status": "error",
                    "error": "Account is not available on this agent",
                    "error_code": "ACCOUNT_SESSION_DEVICE_MISMATCH",
                    "details": {
                        "actions": [
                            "open_web_cabinet",
                            "create_ticket_web",
                            "request_temporary_access",
                            "request_ownership_change",
                        ]
                    },
                },
                status=403,
            )
        except ValueError as exc:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"},
                status=400,
            )
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
        payload, changed = await service.get_login_request_for_device(
            device_id=device_id,
            request_id=request_id,
            include_session_token=True,
        )
        if payload is None:
            return web.json_response({"status": "error", "error": "request not found", "error_code": "NOT_FOUND"}, status=404)
        if changed:
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
        await session.commit()
    return _success({"items": items})


@require_auth("admin")
async def handle_web_admin_registry_password_reset_requests(request: web.Request) -> web.Response:
    status = str(request.query.get("status") or "").strip() or None
    try:
        limit = int(request.query.get("limit") or "100")
    except ValueError:
        limit = 100
    async with get_session() as session:
        items = await PasswordResetRequestService(session).list_requests(status=status, limit=limit)
    return _success({"items": items})


@require_auth("admin")
async def handle_web_admin_registry_password_reset_request_complete(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    request_id = str(request.match_info.get("request_id") or "").strip()
    try:
        data = await request.json() if request.can_read_body else {}
    except Exception:
        return web.json_response({"status": "error", "error": "Некорректный JSON", "error_code": "INVALID_JSON"}, status=400)
    password = str(data.get("password") or "")
    if not password:
        return web.json_response({"status": "error", "error": "Введите новый пароль", "error_code": "VALIDATION_ERROR"}, status=400)
    reason = str(data.get("reason") or "").strip() or None
    async with get_session() as session:
        try:
            payload = await PasswordResetRequestService(session).complete_request(
                request_id=request_id,
                password=password,
                actor_id=auth_context.actor_id,
                reason=reason,
            )
            commit = getattr(session, "commit", None)
            if commit:
                await commit()
        except PasswordPolicyError as exc:
            return web.json_response({"status": "error", "error": str(exc), "error_code": "PASSWORD_POLICY_ERROR"}, status=400)
        except ValueError as exc:
            status_code = 404 if "not found" in str(exc).lower() else 400
            return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=status_code)
    return _success(payload)


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
            registration = payload.get("registration") or {}
            binding = payload.get("binding") or {}
            person = payload.get("person") or {}
            asset = payload.get("asset") or {}
            await _write_device_linking_observer_event(
                session,
                request,
                event_type="device_link_request_approved",
                severity="info",
                result="succeeded",
                device_id=binding.get("device_id") or asset.get("device_id"),
                person_id=binding.get("person_id") or person.get("person_id"),
                payload={
                    "registration_status": registration.get("status"),
                    "binding_status": binding.get("status"),
                    "relationship_type": binding.get("relationship_type"),
                    "replace_existing": bool(data.get("replace_existing")),
                    "admin_override_user_confirmation": bool(
                        data.get("admin_override_user_confirmation") or data.get("force")
                    ),
                },
                route="/api/web/admin/registry/registrations/{claim_id}/approve",
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
            registration = payload.get("registration") or {}
            person = payload.get("person") or {}
            asset = payload.get("asset") or {}
            await _write_device_linking_observer_event(
                session,
                request,
                event_type="device_link_request_rejected",
                severity="info",
                result="succeeded",
                device_id=asset.get("device_id"),
                person_id=person.get("person_id"),
                payload={
                    "registration_status": registration.get("status"),
                    "reason_present": bool(reason),
                },
                route="/api/web/admin/registry/registrations/{claim_id}/reject",
            )
            await session.commit()
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_binding_revoke(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    binding_id = str(request.match_info.get("binding_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    reason = _text(data.get("reason"), max_length=1000)
    async with get_session() as session:
        current_binding = await session.get(DeviceUserBinding, binding_id)
        payload = await RegistrationService(session).revoke_binding(
            binding_id,
            revoked_by=auth_context.actor_id,
            reason=reason,
        )
        events = payload.get("events") if isinstance(payload, dict) else {}
        binding = payload.get("binding") if isinstance(payload, dict) else {}
        if not isinstance(events, dict):
            events = {}
        if not isinstance(binding, dict):
            binding = {}
        revoked_sessions = events.get("revoked_sessions")
        canceled_login_requests = events.get("canceled_login_requests")
        await _write_registry_binding_observer_event(
            session,
            request,
            event_type="registry_binding_revoked",
            severity="info",
            result="succeeded",
            device_id=getattr(current_binding, "device_id", None),
            person_id=getattr(current_binding, "person_id", None),
            payload={
                "binding_status": binding.get("status"),
                "reason_present": bool(reason),
                "revoked_session_count": len(revoked_sessions) if isinstance(revoked_sessions, list) else 0,
                "canceled_login_request_count": len(canceled_login_requests)
                if isinstance(canceled_login_requests, list)
                else 0,
            },
            route="/api/web/admin/registry/bindings/{binding_id}/revoke",
        )
        await session.commit()
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_device_bind_person(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = str(request.match_info.get("device_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    relationship_type = str(data.get("relationship_type") or "primary_user").strip()
    replace_existing = bool(data.get("replace_existing"))
    reason = _text(data.get("reason"), max_length=1000)
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).bind_person_to_device(
                device_id=device_id,
                person_id=str(data.get("person_id") or "").strip(),
                relationship_type=relationship_type,
                replace_existing=replace_existing,
                reviewed_by=auth_context.actor_id,
                reason=reason,
            )
            await _write_registry_binding_created_observer_event(
                session,
                request,
                response_payload=payload,
                device_id=device_id,
                person_id=str(data.get("person_id") or "").strip(),
                relationship_type=relationship_type,
                replace_existing=replace_existing,
                reason=reason,
                route="/api/web/admin/registry/devices/{device_id}/bind-person",
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
    old_binding_action = str(data.get("old_binding_action") or "transferred").strip()
    reason = _text(data.get("reason"), max_length=1000)
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).transfer_owner(
                device_id=device_id,
                new_person_id=str(data.get("new_person_id") or "").strip(),
                old_binding_action=old_binding_action,
                reviewed_by=auth_context.actor_id,
                reason=reason,
            )
            binding = payload.get("binding") if isinstance(payload, dict) else {}
            asset = payload.get("asset") if isinstance(payload, dict) else {}
            summary = payload.get("summary") if isinstance(payload, dict) else {}
            if not isinstance(binding, dict):
                binding = {}
            if not isinstance(asset, dict):
                asset = {}
            if not isinstance(summary, dict):
                summary = {}
            await _write_device_linking_observer_event(
                session,
                request,
                event_type="device_link_owner_transferred",
                severity="info",
                result="succeeded",
                device_id=str(binding.get("device_id") or asset.get("device_id") or device_id or "") or None,
                person_id=str(binding.get("person_id") or data.get("new_person_id") or "") or None,
                payload={
                    "operation": payload.get("operation"),
                    "operation_status": payload.get("status"),
                    "new_binding_status": binding.get("status"),
                    "relationship_type": binding.get("relationship_type"),
                    "old_binding_action": old_binding_action,
                    "revoked_session_count": int(summary.get("revoked_sessions") or 0),
                    "reason_present": bool(reason),
                    "reused_existing_binding": bool(summary.get("reused") or False),
                },
                route="/api/web/admin/registry/devices/{device_id}/transfer-owner",
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
    reason = _text(data.get("reason"), max_length=1000)
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).add_shared_user(
                device_id=device_id,
                person_id=str(data.get("person_id") or "").strip(),
                reviewed_by=auth_context.actor_id,
                reason=reason,
            )
            await _write_registry_binding_created_observer_event(
                session,
                request,
                response_payload=payload,
                device_id=device_id,
                person_id=str(data.get("person_id") or "").strip(),
                relationship_type="shared_user",
                replace_existing=False,
                reason=reason,
                route="/api/web/admin/registry/devices/{device_id}/shared-users",
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
    replace_existing = bool(data.get("replace_existing", True))
    reason = _text(data.get("reason"), max_length=1000)
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).assign_responsible(
                device_id=device_id,
                person_id=str(data.get("person_id") or "").strip(),
                replace_existing=replace_existing,
                reviewed_by=auth_context.actor_id,
                reason=reason,
            )
            await _write_registry_binding_created_observer_event(
                session,
                request,
                response_payload=payload,
                device_id=device_id,
                person_id=str(data.get("person_id") or "").strip(),
                relationship_type="responsible",
                replace_existing=replace_existing,
                reason=reason,
                route="/api/web/admin/registry/devices/{device_id}/responsible",
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
            metadata_json={
                "reason": _text(data.get("reason"), max_length=1000),
                **{
                    field: value
                    for field, value in {
                        "position": _text(data.get("position"), max_length=200),
                        "workplace_label": _text(data.get("workplace_label"), max_length=200),
                        "internal_extension": _text(data.get("internal_extension"), max_length=50),
                        "manager_person_id": _text(data.get("manager_person_id"), max_length=36),
                    }.items()
                    if value
                },
            },
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
                    "position": (person.metadata_json or {}).get("position"),
                    "workplace_label": (person.metadata_json or {}).get("workplace_label"),
                    "internal_extension": (person.metadata_json or {}).get("internal_extension"),
                    "manager_person_id": (person.metadata_json or {}).get("manager_person_id"),
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
            "position": (person.metadata_json or {}).get("position"),
            "workplace_label": (person.metadata_json or {}).get("workplace_label"),
            "internal_extension": (person.metadata_json or {}).get("internal_extension"),
            "manager_person_id": (person.metadata_json or {}).get("manager_person_id"),
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
        metadata = dict(person.metadata_json or {})
        for field, max_length in {
            "position": 200,
            "workplace_label": 200,
            "internal_extension": 50,
            "manager_person_id": 36,
        }.items():
            if field not in data:
                continue
            value = _text(data.get(field), max_length=max_length)
            if value:
                metadata[field] = value
            else:
                metadata.pop(field, None)
        person.metadata_json = metadata
        if not person.display_name:
            return web.json_response({"status": "error", "error": "display_name is required", "error_code": "VALIDATION_ERROR"}, status=400)
        revoked_bindings: list[dict[str, object]] = []
        disabled_ui_users: list[dict[str, object]] = []
        reason = _text(data.get("reason"), max_length=1000)
        if previous_status != person.status and person.status in {"archived", "inactive", "deactivated", "disabled"}:
            active_bindings = (
                await session.execute(
                    select(DeviceUserBinding).where(
                        DeviceUserBinding.person_id == person.person_id,
                        DeviceUserBinding.status == "active",
                    )
                )
            ).scalars().all()
            service = RegistrationService(session)
            reason = reason or f"person {person.status}"
            for binding in active_bindings:
                result = await service.revoke_binding(
                    binding.binding_id,
                    revoked_by=auth_context.actor_id,
                    reason=reason,
                )
                revoked_bindings.append(result["binding"])
            disabled_ui_users = await _disable_linked_requester_ui_users(
                session,
                person_id=person.person_id,
                actor_id=auth_context.actor_id,
                reason=reason,
            )
        payload = {
            "person": {"person_id": person.person_id, "display_name": person.display_name, "status": person.status},
            "revoked_bindings": revoked_bindings,
            "disabled_ui_users": disabled_ui_users,
        }
        await RegistryAdminOperationsService(session).append_event(
            object_type="person",
            object_id=person.person_id,
            event_type="person_updated",
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
            reason=reason,
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
                    "position": (person.metadata_json or {}).get("position"),
                    "workplace_label": (person.metadata_json or {}).get("workplace_label"),
                    "internal_extension": (person.metadata_json or {}).get("internal_extension"),
                    "manager_person_id": (person.metadata_json or {}).get("manager_person_id"),
                    "status": person.status,
                },
                "revoked_binding_ids": [row.get("binding_id") for row in revoked_bindings],
                "disabled_ui_user_logins": [row.get("user_login") for row in disabled_ui_users],
            },
        )
        await session.commit()
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_person_archive(request: web.Request) -> web.Response:
    person_id = str(request.match_info.get("person_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    auth_context = request["auth_context"]
    reason = _text(data.get("reason"), max_length=1000)
    if not reason:
        return web.json_response({"status": "error", "error": "reason is required", "error_code": "VALIDATION_ERROR"}, status=400)
    async with get_session() as session:
        person = await session.get(RegistryPerson, person_id)
        if person is None:
            return web.json_response({"status": "error", "error": "person not found", "error_code": "NOT_FOUND"}, status=404)
        before = {
            "display_name": person.display_name,
            "full_name": person.full_name,
            "status": person.status,
        }
        if person.status != "archived":
            person.status = "archived"
        metadata = dict(person.metadata_json or {})
        metadata["archived_at"] = datetime.now(timezone.utc).isoformat()
        metadata["archived_by"] = auth_context.actor_id
        metadata["archive_reason"] = reason
        person.metadata_json = metadata
        revoked_bindings: list[dict[str, object]] = []
        service = RegistrationService(session)
        active_bindings = (
            await session.execute(
                select(DeviceUserBinding).where(
                    DeviceUserBinding.person_id == person.person_id,
                    DeviceUserBinding.status == "active",
                )
            )
        ).scalars().all()
        revoked_sessions: list[dict[str, object]] = []
        for binding in active_bindings:
            result = await service.revoke_binding(
                binding.binding_id,
                revoked_by=auth_context.actor_id,
                reason=reason,
            )
            revoked_bindings.append(result["binding"])
            events = result.get("events") if isinstance(result.get("events"), dict) else {}
            for revoked_session in events.get("revoked_sessions") or []:
                if isinstance(revoked_session, dict):
                    revoked_sessions.append(revoked_session)

        account_service = AccountSessionService(session)
        revoked_session_ids = {str(row.get("session_id")) for row in revoked_sessions if row.get("session_id")}
        active_sessions = (
            await session.execute(
                select(DeviceAccountSession).where(
                    DeviceAccountSession.person_id == person.person_id,
                    DeviceAccountSession.verification_status.in_(["verified", "pending_verification"]),
                    ~DeviceAccountSession.session_id.in_(revoked_session_ids or [""]),
                )
            )
        ).scalars().all()
        for account_session in active_sessions:
            revoked = await account_service.revoke_session(
                session_id=account_session.session_id,
                revoked_by=auth_context.actor_id,
                reason=reason,
            )
            revoked_sessions.append(revoked)
        disabled_ui_users = await _disable_linked_requester_ui_users(
            session,
            person_id=person.person_id,
            actor_id=auth_context.actor_id,
            reason=reason,
        )

        payload = {
            "person": {"person_id": person.person_id, "display_name": person.display_name, "status": person.status},
            "revoked_bindings": revoked_bindings,
            "revoked_sessions": revoked_sessions,
            "disabled_ui_users": disabled_ui_users,
        }
        await RegistryAdminOperationsService(session).append_event(
            object_type="person",
            object_id=person.person_id,
            event_type="person_archived",
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
            reason=reason,
            related_person_id=person.person_id,
            payload={
                "person_id": person.person_id,
                "before": before,
                "after": {
                    "display_name": person.display_name,
                    "full_name": person.full_name,
                    "status": person.status,
                },
                "revoked_binding_ids": [row.get("binding_id") for row in revoked_bindings],
                "revoked_session_ids": [row.get("session_id") for row in revoked_sessions],
                "disabled_ui_user_logins": [row.get("user_login") for row in disabled_ui_users],
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
async def handle_web_admin_registry_ui_user_disable(request: web.Request) -> web.Response:
    user_login = str(request.match_info.get("user_login") or "").strip()
    data = await request.json() if request.can_read_body else {}
    auth_context = request["auth_context"]
    reason = _text(data.get("reason"), max_length=1000)
    if not user_login:
        return web.json_response({"status": "error", "error": "user_login is required", "error_code": "VALIDATION_ERROR"}, status=400)
    if not reason:
        return web.json_response({"status": "error", "error": "reason is required", "error_code": "VALIDATION_ERROR"}, status=400)

    async with get_session() as session:
        user = await session.get(UiUser, user_login)
        if user is None:
            return web.json_response({"status": "error", "error": "ui user not found", "error_code": "NOT_FOUND"}, status=404)
        if user.actor_role != "user":
            return web.json_response(
                {
                    "status": "error",
                    "error": "only requester UI users can be disabled from registry",
                    "error_code": "UNSUPPORTED_ROLE",
                },
                status=409,
            )
        identity = (
            await session.execute(
                select(RegistryPersonIdentity).where(
                    RegistryPersonIdentity.provider == "ui_login",
                    RegistryPersonIdentity.normalized_identifier == user.user_login.lower(),
                )
            )
        ).scalar_one_or_none()
        related_person_id = identity.person_id if identity is not None else None
        result = await _disable_ui_user_access(
            session,
            user,
            actor_id=auth_context.actor_id,
            reason=reason,
            action="disabled_by_admin",
            related_person_id=related_person_id,
        )
        await RegistryAdminOperationsService(session).append_event(
            object_type="ui_user",
            object_id=user.user_login,
            event_type="ui_user_disabled",
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
            reason=reason,
            related_person_id=related_person_id,
            payload={
                "ui_user_login": user.user_login,
                "actor_role": user.actor_role,
                "linked_person_id": related_person_id,
                "was_active": result["was_active"],
                "revoked_ui_tokens": result["revoked_ui_tokens"],
            },
        )
        await session.commit()
    return _success({"ui_user": result, "revoked_ui_tokens": result["revoked_ui_tokens"]})


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
    payload = {"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        payload["details"] = details
    return web.json_response(payload, status=400)


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
