from __future__ import annotations

from aiohttp import web
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.services.user_accounts import AccountError, UserAccountsService
from auth.middleware import require_auth
from web_api.dto.user_account import UserAccountUpdate


def _error(message: str, code: str, status: int) -> web.Response:
    return web.json_response({"status": "error", "error": message, "error_code": code}, status=status)


@require_auth("admin")
async def handle_web_admin_user_accounts(request: web.Request) -> web.Response:
    try:
        async with get_session() as session:
            accounts = await UserAccountsService(session).list_accounts(
                request.match_info["person_id"], user_login=request.query.get("user_login"))
        return web.json_response({"status": "success", "data": {"accounts": accounts}}, headers={"Cache-Control": "no-store"})
    except AccountError as exc:
        return _error(str(exc), exc.code, exc.status)
    except Exception:
        # Do not attach DB exception text: parameters can include password hashes.
        logger.error("[user_accounts] account read failed")
        return _error("Не удалось загрузить учетные записи", "ACCOUNT_READ_FAILED", 503)


@require_auth("admin")
async def handle_web_admin_user_account_save(request: web.Request) -> web.Response:
    try:
        payload = UserAccountUpdate.model_validate(await request.json())
    except (ValidationError, ValueError, TypeError):
        return _error("Проверьте логин, роль, очереди, группы и причину изменения", "VALIDATION_ERROR", 400)
    context = request["auth_context"]
    try:
        async with get_session() as session:
            account = await UserAccountsService(session).save(
                request.match_info["person_id"], payload, actor_id=context.actor_id, actor_role=context.actor_role)
        return web.json_response({"status": "success", "data": {"account": account}}, headers={"Cache-Control": "no-store"})
    except AccountError as exc:
        return _error(str(exc), exc.code, exc.status)
    except IntegrityError:
        return _error("Данные уже изменены; обновите карточку и повторите сохранение", "ACCOUNT_CONFLICT", 409)
    except Exception:
        logger.error("[user_accounts] account save failed")
        return _error("Не удалось сохранить учетную запись", "ACCOUNT_SAVE_FAILED", 503)
