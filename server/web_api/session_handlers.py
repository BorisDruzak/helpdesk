from aiohttp import web
from pydantic import ValidationError

from access_control.service import resolve_effective_access
from access_control.service import resolve_session_access
from app.db import get_session
from app.repos.access_control_repo import AccessControlRepo
from auth.middleware import WEB_SESSION_COOKIE_NAME, extract_auth_context, require_auth
from auth.rate_limit import check_rate_limit, client_ip, rate_limited_response
from auth.service import AuthService
from app.repos.ui_users_repo import VALID_ROLES
from config import WEB_SESSION_COOKIE_HTTPONLY, WEB_SESSION_COOKIE_SAMESITE, WEB_SESSION_COOKIE_SECURE
from web_api.dto.common import SuccessResponse, json_model_response
from web_api.dto.session import (
    WebSessionLoginRequest,
    WebSessionLogoutPayload,
    WebSessionPayload,
)


def _resolve_workspace_access(actor_role: str) -> tuple[str | None, list[str]]:
    default_workspace, available_workspaces, _permissions, _permissions_version = resolve_session_access(actor_role)
    return default_workspace, available_workspaces


def _build_session_payload(*, user_login: str, actor_role: str, auth_type: str) -> WebSessionPayload:
    default_workspace, available_workspaces, permissions, permissions_version = resolve_session_access(actor_role)
    return WebSessionPayload(
        user_login=user_login,
        actor_role=actor_role,
        auth_type=auth_type,
        default_workspace=default_workspace,
        available_workspaces=available_workspaces,
        permissions=permissions,
        permissions_version=permissions_version,
    )


async def _build_effective_session_payload(*, user_login: str, actor_role: str, auth_type: str) -> WebSessionPayload:
    try:
        async with get_session() as session:
            repo = AccessControlRepo(session)
            group_permissions = await repo.get_actor_group_permissions(user_login)
            groups = await repo.get_actor_group_codes(user_login)
        effective = resolve_effective_access(
            actor_id=user_login,
            actor_role=actor_role,
            groups=groups,
            group_permissions=group_permissions,
        )
        return WebSessionPayload(
            user_login=user_login,
            actor_role=actor_role,
            auth_type=auth_type,
            default_workspace=effective.workspaces[0] if effective.workspaces else None,
            available_workspaces=effective.workspaces,
            permissions=effective.permissions,
            permissions_version=resolve_session_access(actor_role)[3],
        )
    except Exception:
        return _build_session_payload(user_login=user_login, actor_role=actor_role, auth_type=auth_type)


async def handle_web_session_login(request):
    try:
        payload = WebSessionLoginRequest.model_validate(await request.json())
    except (ValidationError, ValueError):
        return web.json_response(
            {
                "status": "error",
                "error": "Некорректные данные входа",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    auth_service = AuthService(request.app["state"])
    if not check_rate_limit("web_session_login", f"{client_ip(request)}:{payload.login}", limit=10, window_seconds=60):
        return rate_limited_response()
    try:
        ok, actor_role = await auth_service.authenticate(payload.login, payload.password)
    except Exception:
        return web.json_response(
            {
                "status": "error",
                "error": "Authentication backend unavailable",
                "error_code": "AUTH_BACKEND_UNAVAILABLE",
            },
            status=503,
        )
    if not ok:
        return web.json_response(
            {
                "status": "error",
                "error": "Неверный логин или пароль",
                "error_code": "INVALID_CREDENTIALS",
            },
            status=401,
        )
    if actor_role not in VALID_ROLES:
        return web.json_response(
            {"status": "error", "error": "Invalid account role", "error_code": "ROLE_INVALID"},
            status=403,
        )
    expected_role = str(payload.expected_role or "").strip().lower()
    if expected_role and expected_role in VALID_ROLES and actor_role != expected_role:
        return web.json_response(
            {
                "status": "error",
                "error": f"Account role mismatch: expected {expected_role}, got {actor_role}",
                "error_code": "ROLE_MISMATCH",
                "actor_role": actor_role,
            },
            status=403,
        )

    try:
        token = await auth_service.generate_ui_token(
            user_login=payload.login,
            actor_role=actor_role,
            expires_hours=24,
        )
    except Exception:
        return web.json_response(
            {
                "status": "error",
                "error": "Authentication backend unavailable",
                "error_code": "AUTH_BACKEND_UNAVAILABLE",
            },
            status=503,
        )
    response = json_model_response(
        SuccessResponse[WebSessionPayload](
            data=await _build_effective_session_payload(
                user_login=payload.login,
                actor_role=actor_role,
                auth_type="ui_token",
            )
        )
    )
    response.set_cookie(
        WEB_SESSION_COOKIE_NAME,
        token,
        httponly=WEB_SESSION_COOKIE_HTTPONLY,
        max_age=24 * 60 * 60,
        path="/",
        samesite=WEB_SESSION_COOKIE_SAMESITE,
        secure=WEB_SESSION_COOKIE_SECURE,
    )
    return response


@require_auth("admin", "support", "auditor", "user")
async def handle_web_session_logout(request):
    auth_context = request["auth_context"]
    auth_service = AuthService(request.app["state"])
    if auth_context.token:
        await auth_service.revoke_ui_token(auth_context.token)

    response = json_model_response(
        SuccessResponse[WebSessionLogoutPayload](data=WebSessionLogoutPayload(cleared=True))
    )
    response.del_cookie(WEB_SESSION_COOKIE_NAME, path="/")
    return response


async def handle_web_session_me(request):
    auth_context = request.get("auth_context") or await extract_auth_context(request)
    if not auth_context:
        return json_model_response(SuccessResponse[WebSessionPayload | None](data=None))

    payload = await _build_effective_session_payload(
        user_login=auth_context.actor_id,
        actor_role=auth_context.actor_role,
        auth_type=auth_context.auth_type.value,
    )
    return json_model_response(SuccessResponse[WebSessionPayload](data=payload))
