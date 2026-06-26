import re

from aiohttp import web
from loguru import logger
from pydantic import ValidationError

import config as config_module
from access_control.service import resolve_effective_access
from access_control.service import resolve_session_access
from app.db import get_session
from app.repos.access_control_repo import AccessControlRepo
from app.repos.ui_users_repo import VALID_ROLES, UiUsersRepo, normalize_user_login
from auth.middleware import WEB_SESSION_COOKIE_NAME, ensure_server_request_id, extract_auth_context, require_auth
from auth.password_service import PasswordPolicyError, hash_password, validate_password_policy
from auth.rate_limit import check_rate_limit, client_ip, rate_limited_response
from auth.service import AuthService
from config import WEB_SESSION_COOKIE_HTTPONLY, WEB_SESSION_COOKIE_SAMESITE, WEB_SESSION_COOKIE_SECURE
from observer.web_event_writer import write_web_cabinet_observer_event
from registry.browser_pairing_service import BrowserPairingService
from registry.password_reset_service import PasswordResetRequestService
from web_api.dto.common import SuccessResponse, json_model_response
from web_api.dto.session import (
    WebSessionRegisterDeviceLinkPayload,
    WebSessionLoginRequest,
    WebSessionLogoutPayload,
    WebSessionPayload,
    WebSessionRegisterPayload,
    WebSessionRegisterRequest,
)


_LOGIN_RE = re.compile(r"^[A-Za-z0-9._@-]{3,100}$")


def _error(message: str, code: str, *, status: int) -> web.Response:
    return web.json_response({"status": "error", "error": message, "error_code": code}, status=status)


def _normalize_login(value: object) -> str:
    return normalize_user_login(value)


def _password_policy_message(exc: PasswordPolicyError) -> str:
    message = str(exc)
    if "at least" in message:
        return "Пароль должен быть не короче 12 символов."
    if "must not match login" in message:
        return "Пароль не должен совпадать с логином."
    if "too common" in message:
        return "Выберите более надежный пароль."
    if "empty" in message or "whitespace" in message:
        return "Введите пароль."
    return "Пароль не соответствует политике безопасности."


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


def _clean_header(value: object, *, max_length: int = 120) -> str | None:
    text = str(value or "").strip()
    return text[:max_length] if text else None


def _account_session_observer_actor_context(
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
        "request_id": _clean_header(request.headers.get("X-Request-ID")),
        "correlation_id": (
            _clean_header(request.headers.get("X-Request-ID"))
            or _clean_header(request.headers.get("X-Correlation-ID"))
        ),
    }


async def _write_account_session_observer_event(
    request: web.Request,
    *,
    event_type: str,
    severity: str,
    result: str,
    actor_id: str | None = None,
    actor_role: str | None = None,
    error_code: str | None = None,
    payload: dict | None = None,
) -> None:
    try:
        async with get_session() as session:
            await write_web_cabinet_observer_event(
                session,
                source="account_session",
                event_type=event_type,
                severity=severity,
                route=request.path,
                actor_context=_account_session_observer_actor_context(
                    request,
                    actor_id=actor_id,
                    actor_role=actor_role,
                ),
                result=result,
                error_code=error_code,
                payload=payload,
            )
    except Exception as exc:
        logger.warning(f"[account_session_observer] failed to write {event_type}: {exc}")


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

    login = _normalize_login(payload.login)
    auth_service = AuthService(request.app["state"])
    if not check_rate_limit("web_session_login", f"{client_ip(request)}:{login}", limit=10, window_seconds=60):
        return rate_limited_response()
    try:
        ok, actor_role = await auth_service.authenticate(login, payload.password)
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
        await _write_account_session_observer_event(
            request,
            event_type="role_mismatch",
            severity="warning",
            result="failed",
            actor_id=login,
            actor_role=actor_role,
            error_code="ROLE_MISMATCH",
            payload={
                "expected_role": expected_role,
                "actual_role": actor_role,
            },
        )
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
            user_login=login,
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
    session_payload = await _build_effective_session_payload(
        user_login=login,
        actor_role=actor_role,
        auth_type="ui_token",
    )
    await _write_account_session_observer_event(
        request,
        event_type="login_succeeded",
        severity="info",
        result="succeeded",
        actor_id=login,
        actor_role=actor_role,
        payload={
            "auth_type": "ui_token",
            "default_workspace": session_payload.default_workspace,
            "available_workspace_count": len(session_payload.available_workspaces),
        },
    )
    response = json_model_response(
        SuccessResponse[WebSessionPayload](
            data=session_payload
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


async def handle_web_session_password_reset_request(request):
    try:
        data = await request.json()
    except Exception:
        return _error("Некорректные данные заявки", "VALIDATION_ERROR", status=400)

    login = _normalize_login(data.get("login"))
    if not login:
        return _error("Введите логин для восстановления.", "VALIDATION_ERROR", status=400)
    if not check_rate_limit("web_session_password_reset", f"{client_ip(request)}:{login.lower()}", limit=5, window_seconds=60):
        return rate_limited_response()

    try:
        async with get_session() as session:
            await PasswordResetRequestService(session).create_request(
                login=login,
                client_ip=client_ip(request),
                user_agent=request.headers.get("User-Agent"),
            )
            commit = getattr(session, "commit", None)
            if commit:
                await commit()
    except Exception as exc:
        logger.warning(f"[web_session_password_reset] failed to create request: {exc}")
        return _error("Не удалось отправить заявку. Повторите попытку позже.", "PASSWORD_RESET_REQUEST_FAILED", status=503)

    return json_model_response(SuccessResponse[dict[str, bool]](data={"accepted": True}))


async def handle_web_session_register(request):
    if not getattr(config_module, "WEB_SELF_REGISTRATION_ENABLED", False):
        return _error(
            "Самостоятельная регистрация временно недоступна. Обратитесь к администратору.",
            "SELF_REGISTRATION_DISABLED",
            status=403,
        )

    try:
        payload = WebSessionRegisterRequest.model_validate(await request.json())
    except (ValidationError, ValueError):
        return _error("Некорректные данные регистрации", "VALIDATION_ERROR", status=400)

    login = _normalize_login(payload.login)
    if not _LOGIN_RE.match(login):
        return _error(
            "Логин должен содержать от 3 до 100 символов: латиницу, цифры, точку, дефис, подчеркивание или @.",
            "VALIDATION_ERROR",
            status=400,
        )
    if payload.password != payload.password_repeat:
        return _error("Пароли не совпадают.", "PASSWORD_REPEAT_MISMATCH", status=400)
    try:
        validate_password_policy(payload.password, login=login)
    except PasswordPolicyError as exc:
        return _error(_password_policy_message(exc), "PASSWORD_POLICY_ERROR", status=400)

    if not check_rate_limit("web_session_register", f"{client_ip(request)}:{login}", limit=5, window_seconds=60):
        return rate_limited_response()

    device_link_payload: WebSessionRegisterDeviceLinkPayload | None = None
    async with get_session() as session:
        device_link_code = str(payload.device_link_code or "").strip()
        if device_link_code:
            pairing = await BrowserPairingService(session).lookup_by_pairing_code(device_link_code)
            if not pairing or pairing.get("purpose") != "registration":
                return _error("Код подключения не найден или истек.", "DEVICE_LINK_CODE_INVALID", status=400)
            device_link_payload = WebSessionRegisterDeviceLinkPayload(
                accepted=True,
                purpose="registration",
                expires_at=pairing.get("expires_at"),
            )

        try:
            user = await UiUsersRepo(session).create_user(
                login,
                hash_password(payload.password),
                actor_role="user",
                actor_id=login,
            )
        except ValueError as exc:
            if "already exists" in str(exc).lower():
                return _error("Пользователь с таким логином уже существует.", "LOGIN_ALREADY_EXISTS", status=409)
            return _error("Не удалось создать аккаунт.", "VALIDATION_ERROR", status=400)

    await _write_account_session_observer_event(
        request,
        event_type="register_succeeded",
        severity="info",
        result="succeeded",
        actor_id=login,
        actor_role="user",
        payload={
            "next_path": "/app/login?registered=1",
            "device_link_accepted": bool(device_link_payload and device_link_payload.accepted),
            "device_link_purpose": device_link_payload.purpose if device_link_payload else None,
        },
    )
    return json_model_response(
        SuccessResponse[WebSessionRegisterPayload](
            data=WebSessionRegisterPayload(
                user_login=user.user_login,
                actor_role="user",
                next_path="/app/login?registered=1",
                device_link=device_link_payload,
            )
        ),
        status=201,
    )


@require_auth("admin", "support", "auditor", "user")
async def handle_web_session_logout(request):
    auth_context = request["auth_context"]
    auth_service = AuthService(request.app["state"])
    token_revoked = False
    if auth_context.token:
        token_revoked = await auth_service.revoke_ui_token(auth_context.token)
    auth_type = getattr(auth_context.auth_type, "value", str(auth_context.auth_type))
    await _write_account_session_observer_event(
        request,
        event_type="logout_succeeded",
        severity="info",
        result="succeeded",
        actor_id=auth_context.actor_id,
        actor_role=auth_context.actor_role,
        payload={
            "auth_type": auth_type,
            "credential_seen": bool(auth_context.token),
            "revoked": bool(token_revoked),
        },
    )

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
