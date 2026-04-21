from __future__ import annotations

import mimetypes
from pathlib import Path

from aiohttp import web


REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_DIST_DIR = REPO_ROOT / "webapp" / "dist"

_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}
_IMMUTABLE_CACHE_HEADERS = {
    "Cache-Control": "public, max-age=31536000, immutable",
}


def _read_text_response(path: Path, content_type: str, *, no_cache: bool = False) -> web.Response:
    response = web.Response(
        text=path.read_text(encoding="utf-8"),
        content_type=content_type,
        charset="utf-8",
    )
    if no_cache:
        response.headers.update(_NO_CACHE_HEADERS)
    return response


def _read_binary_response(path: Path) -> web.Response:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    response = web.Response(
        body=path.read_bytes(),
        content_type=content_type,
    )
    response.headers.update(_IMMUTABLE_CACHE_HEADERS)
    return response


def _ensure_relative_path(path_value: str) -> Path | None:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return None
    if any(part == ".." for part in candidate.parts):
        return None
    return candidate


def _resolve_public_asset_relative_path(request: web.Request) -> Path | None:
    asset_name = request.match_info.get("asset_name")
    if not asset_name:
        asset_name = Path(request.path).name
    if not asset_name:
        return None
    return _ensure_relative_path(asset_name)


def _missing_bundle_response() -> web.Response:
    response = web.Response(
        text=(
            "Новый webapp ещё не собран. Сначала выполните "
            "`python scripts/bootstrap_web_toolchain.py`, затем "
            "`pnpm --dir webapp run build`."
        ),
        content_type="text/plain",
        charset="utf-8",
        status=503,
    )
    response.headers.update(_NO_CACHE_HEADERS)
    return response


async def handle_webapp_page(request: web.Request) -> web.Response:
    index_path = WEBAPP_DIST_DIR / "index.html"
    if not index_path.exists():
        return _missing_bundle_response()
    return _read_text_response(index_path, "text/html", no_cache=True)


async def handle_webapp_asset(request: web.Request) -> web.Response:
    relative_path = _ensure_relative_path(request.match_info["asset_path"])
    if relative_path is None:
        raise web.HTTPNotFound()

    asset_path = WEBAPP_DIST_DIR / "assets" / relative_path
    if not asset_path.exists() or not asset_path.is_file():
        raise web.HTTPNotFound()
    return _read_binary_response(asset_path)


async def handle_webapp_public_asset(request: web.Request) -> web.Response:
    relative_path = _resolve_public_asset_relative_path(request)
    if relative_path is None:
        raise web.HTTPNotFound()

    asset_path = WEBAPP_DIST_DIR / relative_path
    if not asset_path.exists() or not asset_path.is_file():
        raise web.HTTPNotFound()
    return _read_binary_response(asset_path)
