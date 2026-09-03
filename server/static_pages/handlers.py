from pathlib import Path

from aiohttp import web


BASE_DIR = Path(__file__).parent.parent


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


def _retired_shell_redirect(request: web.Request, target_path: str) -> web.HTTPPermanentRedirect:
    query = [
        (key, value)
        for key, value in request.query.items()
        if key not in {"_shell", "legacy"}
    ]
    return web.HTTPPermanentRedirect(location=str(request.rel_url.with_path(target_path).with_query(query)))


def _webapp_ticket_target_path(request: web.Request) -> str:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    if not ticket_id:
        return "/app/ticket"
    return f"/app/ticket/{ticket_id}"


async def handle_index(request):
    raise _retired_shell_redirect(request, "/app/support")


async def handle_admin_page(request):
    raise _retired_shell_redirect(request, "/app/admin")


async def handle_support_page(request):
    raise _retired_shell_redirect(request, "/app/support")


async def handle_login_page(request):
    raise _retired_shell_redirect(request, "/app/login")


async def handle_favicon(request):
    """Отдаём 204 No Content, чтобы браузер не получал 404 по /favicon.ico."""
    return web.Response(status=204)


async def handle_ticket_page(request):
    raise _retired_shell_redirect(request, "/app/ticket")


async def handle_ticket_page_by_id(request):
    raise _retired_shell_redirect(request, _webapp_ticket_target_path(request))


async def handle_ws_ui_test(request):
    return _text_file_response(BASE_DIR / "ws_ui_test.html", "text/html")


async def handle_public_queue_page(request):
    """Stage 10.2: публичная страница очереди (без авторизации)."""
    return _text_file_response(BASE_DIR / "public_queue.html", "text/html", no_cache=True)


async def handle_public_queue_css(request):
    return _text_file_response(BASE_DIR / "public_queue.css", "text/css", no_cache=True)


async def handle_public_queue_js(request):
    return _text_file_response(BASE_DIR / "public_queue.js", "application/javascript", no_cache=True)


async def handle_help_page(request):
    raise _retired_shell_redirect(request, "/app/help")
