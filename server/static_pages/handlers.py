from pathlib import Path

from aiohttp import web
from config import (
    WEBAPP_CUTOVER_ADMIN_ENABLED,
    WEBAPP_CUTOVER_HELP_ENABLED,
    WEBAPP_CUTOVER_LOGIN_ENABLED,
    WEBAPP_CUTOVER_SUPPORT_ENABLED,
    WEBAPP_CUTOVER_TICKET_ENABLED,
)
from static_pages.cutover import build_webapp_cutover_state
from static_pages.webapp_assets import WEBAPP_DIST_DIR


BASE_DIR = Path(__file__).parent.parent
ADMIN_SHELL_VERSION = "20260419a"
SUPPORT_SHELL_VERSION = "20260419a"
LOGIN_SHELL_VERSION = "20260330a"


# Запрет кэширования админки, чтобы после деплоя всегда подгружалась новая версия.
_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _text_file_response(path: Path, content_type: str, *, no_cache: bool = False) -> web.Response:
    response = web.Response(
        text=path.read_text(encoding="utf-8"),
        content_type=content_type,
        charset="utf-8",
    )
    if no_cache:
        response.headers.update(_NO_CACHE_HEADERS)
    return response


def _versioned_self_redirect(request: web.Request, version: str) -> web.HTTPFound | None:
    if request.query.get("_shell") == version:
        return None
    query = dict(request.query)
    query["_shell"] = version
    return web.HTTPFound(location=str(request.rel_url.with_query(query)))


def _legacy_shell_requested(request: web.Request) -> bool:
    return request.query.get("legacy") == "1" or "_shell" in request.query


def _webapp_cutover_redirect(
    request: web.Request,
    *,
    enabled: bool,
    target_path: str,
) -> web.HTTPFound | None:
    if not enabled or _legacy_shell_requested(request):
        return None
    query = {
        key: value
        for key, value in request.query.items()
        if key not in {"_shell", "legacy"}
    }
    return web.HTTPFound(location=str(request.rel_url.with_path(target_path).with_query(query)))


def _webapp_ticket_target_path(request: web.Request) -> str:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    if not ticket_id:
        return "/app/ticket"
    return f"/app/ticket/{ticket_id}"


async def handle_index(request):
    return _text_file_response(BASE_DIR / "web_interface.html", "text/html")


async def handle_admin_page(request):
    cutover_state = build_webapp_cutover_state(
        dist_dir=WEBAPP_DIST_DIR,
        login_enabled=WEBAPP_CUTOVER_LOGIN_ENABLED,
        support_enabled=WEBAPP_CUTOVER_SUPPORT_ENABLED,
        admin_enabled=WEBAPP_CUTOVER_ADMIN_ENABLED,
    )
    redirect = _webapp_cutover_redirect(
        request,
        enabled=cutover_state.admin.active,
        target_path=cutover_state.admin.target_path,
    )
    if redirect is not None:
        raise redirect
    redirect = _versioned_self_redirect(request, ADMIN_SHELL_VERSION)
    if redirect is not None:
        raise redirect
    return _text_file_response(BASE_DIR / "admin.html", "text/html", no_cache=True)


async def handle_support_page(request):
    cutover_state = build_webapp_cutover_state(
        dist_dir=WEBAPP_DIST_DIR,
        login_enabled=WEBAPP_CUTOVER_LOGIN_ENABLED,
        support_enabled=WEBAPP_CUTOVER_SUPPORT_ENABLED,
        admin_enabled=WEBAPP_CUTOVER_ADMIN_ENABLED,
    )
    redirect = _webapp_cutover_redirect(
        request,
        enabled=cutover_state.support.active,
        target_path=cutover_state.support.target_path,
    )
    if redirect is not None:
        raise redirect
    redirect = _versioned_self_redirect(request, SUPPORT_SHELL_VERSION)
    if redirect is not None:
        raise redirect
    return _text_file_response(BASE_DIR / "support.html", "text/html", no_cache=True)


async def handle_login_page(request):
    cutover_state = build_webapp_cutover_state(
        dist_dir=WEBAPP_DIST_DIR,
        login_enabled=WEBAPP_CUTOVER_LOGIN_ENABLED,
        support_enabled=WEBAPP_CUTOVER_SUPPORT_ENABLED,
        admin_enabled=WEBAPP_CUTOVER_ADMIN_ENABLED,
    )
    redirect = _webapp_cutover_redirect(
        request,
        enabled=cutover_state.login.active,
        target_path=cutover_state.login.target_path,
    )
    if redirect is not None:
        raise redirect
    redirect = _versioned_self_redirect(request, LOGIN_SHELL_VERSION)
    if redirect is not None:
        raise redirect
    return _text_file_response(BASE_DIR / "login.html", "text/html", no_cache=True)


async def handle_favicon(request):
    """Отдаём 204 No Content, чтобы браузер не получал 404 по /favicon.ico."""
    return web.Response(status=204)


async def handle_admin_css(request):
    return _text_file_response(BASE_DIR / "admin.css", "text/css", no_cache=True)


async def handle_admin_js(request):
    return _text_file_response(BASE_DIR / "admin.js", "application/javascript", no_cache=True)


async def handle_admin_modules_workbench_html(request):
    return _text_file_response(BASE_DIR / "admin_modules_workbench.html", "text/html", no_cache=True)


async def handle_admin_modules_workbench_js(request):
    return _text_file_response(BASE_DIR / "admin_modules_workbench.js", "application/javascript", no_cache=True)


async def handle_endpoint_module_workbench_js(request):
    return _text_file_response(BASE_DIR / "endpoint_module_workbench.js", "application/javascript", no_cache=True)


async def handle_admin_ticket_forms_builder_html(request):
    return _text_file_response(BASE_DIR / "admin_ticket_forms_builder.html", "text/html", no_cache=True)


async def handle_admin_ticket_forms_builder_js(request):
    return _text_file_response(BASE_DIR / "admin_ticket_forms_builder.js", "application/javascript", no_cache=True)


async def handle_web_shared_js(request):
    return _text_file_response(BASE_DIR / "web_shared.js", "application/javascript", no_cache=True)


async def handle_support_css(request):
    return _text_file_response(BASE_DIR / "support.css", "text/css", no_cache=True)


async def handle_support_js(request):
    return _text_file_response(BASE_DIR / "support.js", "application/javascript", no_cache=True)


async def handle_login_css(request):
    return _text_file_response(BASE_DIR / "login.css", "text/css", no_cache=True)


async def handle_login_js(request):
    return _text_file_response(BASE_DIR / "login.js", "application/javascript", no_cache=True)


async def handle_ticket_page(request):
    cutover_state = build_webapp_cutover_state(
        dist_dir=WEBAPP_DIST_DIR,
        login_enabled=WEBAPP_CUTOVER_LOGIN_ENABLED,
        support_enabled=WEBAPP_CUTOVER_SUPPORT_ENABLED,
        admin_enabled=WEBAPP_CUTOVER_ADMIN_ENABLED,
        help_enabled=WEBAPP_CUTOVER_HELP_ENABLED,
        ticket_enabled=WEBAPP_CUTOVER_TICKET_ENABLED,
    )
    redirect = _webapp_cutover_redirect(
        request,
        enabled=cutover_state.ticket.active,
        target_path="/app/ticket",
    )
    if redirect is not None:
        raise redirect
    return _text_file_response(BASE_DIR / "ticket.html", "text/html", no_cache=True)


async def handle_ticket_page_by_id(request):
    cutover_state = build_webapp_cutover_state(
        dist_dir=WEBAPP_DIST_DIR,
        login_enabled=WEBAPP_CUTOVER_LOGIN_ENABLED,
        support_enabled=WEBAPP_CUTOVER_SUPPORT_ENABLED,
        admin_enabled=WEBAPP_CUTOVER_ADMIN_ENABLED,
        help_enabled=WEBAPP_CUTOVER_HELP_ENABLED,
        ticket_enabled=WEBAPP_CUTOVER_TICKET_ENABLED,
    )
    redirect = _webapp_cutover_redirect(
        request,
        enabled=cutover_state.ticket.active,
        target_path=_webapp_ticket_target_path(request),
    )
    if redirect is not None:
        raise redirect
    return _text_file_response(BASE_DIR / "ticket.html", "text/html", no_cache=True)


async def handle_chat_debug(request):
    return _text_file_response(BASE_DIR / "chat_debug.html", "text/html")


async def handle_chat_ws(request):
    return _text_file_response(BASE_DIR / "chat_ws.html", "text/html")


async def handle_test_simple(request):
    html_path = BASE_DIR / "test_web_simple.html"
    if html_path.exists():
        return _text_file_response(html_path, "text/html")
    return web.Response(text="Test page not found", status=404)


async def handle_ws_ui_test(request):
    return _text_file_response(BASE_DIR / "ws_ui_test.html", "text/html")


async def handle_modules_page(request):
    return _text_file_response(BASE_DIR / "modules.html", "text/html", no_cache=True)


async def handle_public_queue_page(request):
    """Stage 10.2: публичная страница очереди (без авторизации)."""
    return _text_file_response(BASE_DIR / "public_queue.html", "text/html", no_cache=True)


async def handle_public_queue_css(request):
    return _text_file_response(BASE_DIR / "public_queue.css", "text/css", no_cache=True)


async def handle_public_queue_js(request):
    return _text_file_response(BASE_DIR / "public_queue.js", "application/javascript", no_cache=True)


async def handle_help_page(request):
    cutover_state = build_webapp_cutover_state(
        dist_dir=WEBAPP_DIST_DIR,
        login_enabled=WEBAPP_CUTOVER_LOGIN_ENABLED,
        support_enabled=WEBAPP_CUTOVER_SUPPORT_ENABLED,
        admin_enabled=WEBAPP_CUTOVER_ADMIN_ENABLED,
        help_enabled=WEBAPP_CUTOVER_HELP_ENABLED,
        ticket_enabled=WEBAPP_CUTOVER_TICKET_ENABLED,
    )
    redirect = _webapp_cutover_redirect(
        request,
        enabled=cutover_state.help.active,
        target_path=cutover_state.help.target_path,
    )
    if redirect is not None:
        raise redirect
    return _text_file_response(BASE_DIR / "help.html", "text/html", no_cache=True)


async def handle_help_css(request):
    return _text_file_response(BASE_DIR / "help.css", "text/css", no_cache=True)


async def handle_help_js(request):
    return _text_file_response(BASE_DIR / "help.js", "application/javascript", no_cache=True)


async def handle_ticket_css(request):
    """Stage 10.4: стили страницы тикета (chat-first)."""
    return _text_file_response(BASE_DIR / "ticket.css", "text/css", no_cache=True)


async def handle_ticket_js(request):
    """Stage 10.4: скрипт страницы тикета (chat-first, slash-команды, WS)."""
    return _text_file_response(BASE_DIR / "ticket.js", "application/javascript", no_cache=True)
