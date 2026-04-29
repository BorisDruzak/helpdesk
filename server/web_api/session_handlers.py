from aiohttp import web
from pydantic import ValidationError

from access_control.service import resolve_session_access
from auth.middleware import WEB_SESSION_COOKIE_NAME, extract_auth_context, require_auth
from auth.service import AuthService
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
    ok, actor_role = await auth_service.authenticate(payload.login, payload.password)
    if not ok:
        return web.json_response(
            {
                "status": "error",
                "error": "Неверный логин или пароль",
                "error_code": "INVALID_CREDENTIALS",
            },
            status=401,
        )

    token = await auth_service.generate_ui_token(
        user_login=payload.login,
        actor_role=actor_role,
        expires_hours=24,
    )
    response = json_model_response(
        SuccessResponse[WebSessionPayload](
            data=_build_session_payload(
                user_login=payload.login,
                actor_role=actor_role,
                auth_type="ui_token",
            )
        )
    )
    response.set_cookie(
        WEB_SESSION_COOKIE_NAME,
        token,
        httponly=True,
        max_age=24 * 60 * 60,
        path="/",
        samesite="Lax",
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

    payload = _build_session_payload(
        user_login=auth_context.actor_id,
        actor_role=auth_context.actor_role,
        auth_type=auth_context.auth_type.value,
    )
    return json_model_response(SuccessResponse[WebSessionPayload](data=payload))
