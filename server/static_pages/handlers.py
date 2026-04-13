from pathlib import Path

from aiohttp import web


BASE_DIR = Path(__file__).parent.parent
ADMIN_SHELL_VERSION = "20260331e"
SUPPORT_SHELL_VERSION = "20260413b"
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


async def handle_index(request):
    return _text_file_response(BASE_DIR / "web_interface.html", "text/html")


async def handle_admin_page(request):
    redirect = _versioned_self_redirect(request, ADMIN_SHELL_VERSION)
    if redirect is not None:
        raise redirect
    return _text_file_response(BASE_DIR / "admin.html", "text/html", no_cache=True)


async def handle_support_page(request):
    redirect = _versioned_self_redirect(request, SUPPORT_SHELL_VERSION)
    if redirect is not None:
        raise redirect
    return _text_file_response(BASE_DIR / "support.html", "text/html", no_cache=True)


async def handle_login_page(request):
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


async def handle_support_css(request):
    return _text_file_response(BASE_DIR / "support.css", "text/css", no_cache=True)


async def handle_support_js(request):
    return _text_file_response(BASE_DIR / "support.js", "application/javascript", no_cache=True)


async def handle_login_css(request):
    return _text_file_response(BASE_DIR / "login.css", "text/css", no_cache=True)


async def handle_login_js(request):
    return _text_file_response(BASE_DIR / "login.js", "application/javascript", no_cache=True)


async def handle_ticket_page(request):
    return _text_file_response(BASE_DIR / "ticket.html", "text/html", no_cache=True)


async def handle_ticket_page_by_id(request):
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
