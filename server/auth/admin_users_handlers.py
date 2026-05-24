"""
Stage 10: HTTP handlers для Admin Users API (управление ui_users).
RBAC: только admin. Требуется AUTH_UI_DB_USERS_ENABLED.
"""
from typing import Optional

from aiohttp import web
from loguru import logger

from config import AUTH_UI_DB_USERS_ENABLED
from auth.middleware import require_auth
from app.db import get_session
from app.repos.ui_users_repo import DEFAULT_USER_ROLE, VALID_ROLES, UiUsersRepo
from app.repos import TicketEventsRepo
from auth.password_service import PasswordPolicyError, hash_password, validate_password_policy


def _check_db_users_enabled() -> Optional[web.Response]:
    if not AUTH_UI_DB_USERS_ENABLED:
        return web.json_response(
            {"status": "error", "error": "DB users API disabled", "error_code": "API_DISABLED"},
            status=404,
        )
    return None


def _auth_context(request: web.Request):
    return request.get("auth_context")


@require_auth("admin")
async def handle_admin_users_list(request: web.Request) -> web.Response:
    """GET /api/admin/users?include_inactive=false&limit=500&offset=0"""
    r = _check_db_users_enabled()
    if r:
        return r
    include_inactive = request.query.get("include_inactive", "false").lower() == "true"
    limit = min(500, max(1, int(request.query.get("limit", "500"))))
    offset = max(0, int(request.query.get("offset", "0")))
    async with get_session() as session:
        repo = UiUsersRepo(session)
        users = await repo.list_users(include_inactive=include_inactive, limit=limit, offset=offset)
        ticket_repo = TicketEventsRepo(session)
        operator_loads = {
            item["user_login"]: item
            for item in await ticket_repo.list_assignable_users_with_load()
        }
    items = [
        {
            "user_login": u.user_login,
            "actor_role": u.actor_role,
            "is_active": u.is_active,
            "failed_attempts": u.failed_attempts,
            "locked_until": u.locked_until.isoformat() if u.locked_until else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "last_ticket_assigned_at": u.last_ticket_assigned_at.isoformat() if u.last_ticket_assigned_at else None,
            "active_count": int(operator_loads.get(u.user_login, {}).get("active_count") or 0),
            "assignment_available": bool(int(operator_loads.get(u.user_login, {}).get("active_count") or 0) < 3),
            "created_at": u.created_at.isoformat(),
            "updated_at": u.updated_at.isoformat(),
        }
        for u in users
    ]
    return web.json_response({"status": "ok", "users": items})


@require_auth("admin")
async def handle_admin_users_post(request: web.Request) -> web.Response:
    """POST /api/admin/users — создать пользователя. Body: login, password, actor_role?"""
    r = _check_db_users_enabled()
    if r:
        return r
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    login = (data.get("login") or data.get("user_login") or "").strip()
    password = data.get("password")
    actor_role = (data.get("actor_role") or DEFAULT_USER_ROLE).strip().lower()
    if not login:
        return web.json_response(
            {"status": "error", "error": "login required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    if not password:
        return web.json_response(
            {"status": "error", "error": "password required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    if actor_role not in VALID_ROLES:
        return web.json_response(
            {"status": "error", "error": "invalid actor_role", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        validate_password_policy(password, login=login)
    except PasswordPolicyError as exc:
        return web.json_response(
            {"status": "error", "error": str(exc), "error_code": "PASSWORD_POLICY_ERROR"},
            status=400,
        )
    ctx = _auth_context(request)
    actor_id = ctx.actor_id if ctx else None
    password_hash = hash_password(password)
    async with get_session() as session:
        repo = UiUsersRepo(session)
        try:
            user = await repo.create_user(login, password_hash, actor_role=actor_role, actor_id=actor_id)
        except ValueError as e:
            if "already exists" in str(e).lower():
                return web.json_response(
                    {"status": "error", "error": "User already exists", "error_code": "CONFLICT"},
                    status=409,
                )
            return web.json_response(
                {"status": "error", "error": str(e), "error_code": "VALIDATION_ERROR"},
                status=400,
            )
    return web.json_response(
        {
            "status": "ok",
            "user_login": user.user_login,
            "actor_role": user.actor_role,
            "is_active": user.is_active,
        },
        status=201,
    )


@require_auth("admin")
async def handle_admin_users_get(request: web.Request) -> web.Response:
    """GET /api/admin/users/{user_login} — без password_hash."""
    r = _check_db_users_enabled()
    if r:
        return r
    user_login = request.match_info.get("user_login", "").strip()
    if not user_login:
        return web.json_response(
            {"status": "error", "error": "user_login required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    async with get_session() as session:
        repo = UiUsersRepo(session)
        user = await repo.get_by_login(user_login)
    if not user:
        return web.json_response(
            {"status": "error", "error": "User not found", "error_code": "NOT_FOUND"},
            status=404,
        )
    return web.json_response({
        "status": "ok",
        "user_login": user.user_login,
        "actor_role": user.actor_role,
        "is_active": user.is_active,
        "failed_attempts": user.failed_attempts,
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    })


@require_auth("admin")
async def handle_admin_users_patch(request: web.Request) -> web.Response:
    """PATCH /api/admin/users/{user_login} — обновить actor_role, is_active."""
    r = _check_db_users_enabled()
    if r:
        return r
    user_login = request.match_info.get("user_login", "").strip()
    if not user_login:
        return web.json_response(
            {"status": "error", "error": "user_login required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    actor_role = data.get("actor_role")
    is_active = data.get("is_active")
    if actor_role is None and is_active is None:
        return web.json_response(
            {"status": "error", "error": "actor_role or is_active required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    ctx = _auth_context(request)
    if actor_role is not None and str(actor_role or "").strip().lower() not in VALID_ROLES:
        return web.json_response(
            {"status": "error", "error": "invalid actor_role", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    actor_id = ctx.actor_id if ctx else None
    async with get_session() as session:
        repo = UiUsersRepo(session)
        user = await repo.update_user(user_login, actor_role=actor_role, is_active=is_active, actor_id=actor_id)
    if not user:
        return web.json_response(
            {"status": "error", "error": "User not found", "error_code": "NOT_FOUND"},
            status=404,
        )
    return web.json_response({
        "status": "ok",
        "user_login": user.user_login,
        "actor_role": user.actor_role,
        "is_active": user.is_active,
    })


@require_auth("admin")
async def handle_admin_users_password_post(request: web.Request) -> web.Response:
    """POST /api/admin/users/{user_login}/password — смена пароля админом. Body: password."""
    r = _check_db_users_enabled()
    if r:
        return r
    user_login = request.match_info.get("user_login", "").strip()
    if not user_login:
        return web.json_response(
            {"status": "error", "error": "user_login required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    password = data.get("password")
    if not password:
        return web.json_response(
            {"status": "error", "error": "password required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        validate_password_policy(password, login=user_login)
    except PasswordPolicyError as exc:
        return web.json_response(
            {"status": "error", "error": str(exc), "error_code": "PASSWORD_POLICY_ERROR"},
            status=400,
        )
    ctx = _auth_context(request)
    actor_id = ctx.actor_id if ctx else None
    password_hash = hash_password(password)
    async with get_session() as session:
        repo = UiUsersRepo(session)
        ok = await repo.set_password(user_login, password_hash, actor_id=actor_id)
    if not ok:
        return web.json_response(
            {"status": "error", "error": "User not found", "error_code": "NOT_FOUND"},
            status=404,
        )
    return web.json_response({"status": "ok", "message": "Password updated"})


@require_auth("admin")
async def handle_admin_users_deactivate_post(request: web.Request) -> web.Response:
    """POST /api/admin/users/{user_login}/deactivate — мягкая деактивация."""
    r = _check_db_users_enabled()
    if r:
        return r
    user_login = request.match_info.get("user_login", "").strip()
    if not user_login:
        return web.json_response(
            {"status": "error", "error": "user_login required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    ctx = _auth_context(request)
    actor_id = ctx.actor_id if ctx else None
    async with get_session() as session:
        repo = UiUsersRepo(session)
        ok = await repo.deactivate_user(user_login, actor_id=actor_id)
    if not ok:
        return web.json_response(
            {"status": "error", "error": "User not found", "error_code": "NOT_FOUND"},
            status=404,
        )
    return web.json_response({"status": "ok", "message": "User deactivated"})


@require_auth("admin", "support", "auditor", "user")
async def handle_users_me_password_post(request: web.Request) -> web.Response:
    """POST /api/users/me/password — смена своего пароля. Body: current_password, new_password."""
    r = _check_db_users_enabled()
    if r:
        return r
    ctx = _auth_context(request)
    if not ctx or ctx.actor_role is None:
        return web.json_response(
            {"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"},
            status=401,
        )
    # Для UI токена actor_id = user_login (см. middleware: token_info["user_login"])
    user_login = ctx.actor_id
    if not user_login:
        return web.json_response(
            {"status": "error", "error": "User context required", "error_code": "FORBIDDEN"},
            status=403,
        )
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    current = data.get("current_password")
    new_pass = data.get("new_password")
    if not current or not new_pass:
        return web.json_response(
            {"status": "error", "error": "current_password and new_password required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        validate_password_policy(new_pass, login=user_login)
    except PasswordPolicyError as exc:
        return web.json_response(
            {"status": "error", "error": str(exc), "error_code": "PASSWORD_POLICY_ERROR"},
            status=400,
        )
    from auth.password_service import verify_password
    async with get_session() as session:
        repo = UiUsersRepo(session)
        user = await repo.get_by_login(user_login)
        if not user:
            return web.json_response(
                {"status": "error", "error": "User not found (DB users only)", "error_code": "NOT_FOUND"},
                status=404,
            )
        if not verify_password(current, user.password_hash):
            return web.json_response(
                {"status": "error", "error": "Current password is wrong", "error_code": "INVALID_PASSWORD"},
                status=400,
            )
        ok = await repo.set_password(user_login, hash_password(new_pass), actor_id=user_login)
    if not ok:
        return web.json_response(
            {"status": "error", "error": "Failed to update password", "error_code": "INTERNAL"},
            status=500,
        )
    return web.json_response({"status": "ok", "message": "Password updated"})
