from pathlib import Path

from aiohttp import web


BASE_DIR = Path(__file__).parent.parent


# Запрет кэширования админки, чтобы после деплоя всегда подгружалась новая версия.
_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _html_file_response(path: Path) -> web.FileResponse:
    """Return HTML file with explicit UTF-8 charset to avoid mojibake."""
    return web.FileResponse(
        path,
        headers={"Content-Type": "text/html; charset=utf-8"},
    )


def _static_text_response(path: Path, content_type: str, *, no_cache: bool = False) -> web.FileResponse:
    response = web.FileResponse(
        path,
        headers={"Content-Type": content_type},
    )
    if no_cache:
        response.headers.update(_NO_CACHE_HEADERS)
    return response


async def handle_index(request):
    return _html_file_response(BASE_DIR / "web_interface.html")


async def handle_admin_page(request):
    r = _html_file_response(BASE_DIR / "admin.html")
    r.headers.update(_NO_CACHE_HEADERS)
    return r


async def handle_favicon(request):
    """Отдаём 204 No Content, чтобы браузер не получал 404 по /favicon.ico."""
    return web.Response(status=204)


async def handle_admin_css(request):
    r = web.FileResponse(
        BASE_DIR / "admin.css",
        headers={"Content-Type": "text/css; charset=utf-8"},
    )
    r.headers.update(_NO_CACHE_HEADERS)
    return r


async def handle_admin_js(request):
    r = web.FileResponse(
        BASE_DIR / "admin.js",
        headers={"Content-Type": "application/javascript; charset=utf-8"},
    )
    r.headers.update(_NO_CACHE_HEADERS)
    return r


async def handle_ticket_page(request):
    r = _html_file_response(BASE_DIR / "ticket.html")
    r.headers.update(_NO_CACHE_HEADERS)
    return r


async def handle_ticket_page_by_id(request):
    r = _html_file_response(BASE_DIR / "ticket.html")
    r.headers.update(_NO_CACHE_HEADERS)
    return r


async def handle_chat_debug(request):
    return _html_file_response(BASE_DIR / "chat_debug.html")


async def handle_chat_ws(request):
    return _html_file_response(BASE_DIR / "chat_ws.html")


async def handle_test_simple(request):
    html_path = BASE_DIR / "test_web_simple.html"
    if html_path.exists():
        return _html_file_response(html_path)
    return web.Response(text="Test page not found", status=404)


async def handle_ws_ui_test(request):
    return _html_file_response(BASE_DIR / "ws_ui_test.html")


async def handle_modules_page(request):
    r = _html_file_response(BASE_DIR / "modules.html")
    r.headers.update(_NO_CACHE_HEADERS)
    return r


async def handle_public_queue_page(request):
    """Stage 10.2: публичная страница очереди (без авторизации)."""
    r = _html_file_response(BASE_DIR / "public_queue.html")
    r.headers.update(_NO_CACHE_HEADERS)
    return r


async def handle_public_queue_css(request):
    return _static_text_response(BASE_DIR / "public_queue.css", "text/css; charset=utf-8", no_cache=True)


async def handle_public_queue_js(request):
    return _static_text_response(BASE_DIR / "public_queue.js", "application/javascript; charset=utf-8", no_cache=True)


async def handle_help_page(request):
    r = _html_file_response(BASE_DIR / "help.html")
    r.headers.update(_NO_CACHE_HEADERS)
    return r


async def handle_help_css(request):
    return _static_text_response(BASE_DIR / "help.css", "text/css; charset=utf-8", no_cache=True)


async def handle_help_js(request):
    return _static_text_response(BASE_DIR / "help.js", "application/javascript; charset=utf-8", no_cache=True)


async def handle_ticket_css(request):
    """Stage 10.4: стили страницы тикета (chat-first)."""
    return _static_text_response(BASE_DIR / "ticket.css", "text/css; charset=utf-8", no_cache=True)


async def handle_ticket_js(request):
    """Stage 10.4: скрипт страницы тикета (chat-first, slash-команды, WS)."""
    return _static_text_response(BASE_DIR / "ticket.js", "application/javascript; charset=utf-8", no_cache=True)
