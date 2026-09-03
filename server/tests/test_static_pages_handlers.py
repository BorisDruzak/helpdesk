import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from routes import setup_routes
from static_pages.handlers import (
    handle_admin_page,
    handle_help_page,
    handle_login_page,
    handle_support_page,
    handle_ticket_page,
    handle_ticket_page_by_id,
)
import static_pages.webapp_assets as webapp_assets_module
from static_pages.webapp_assets import (
    handle_webapp_asset,
    handle_webapp_page,
    handle_webapp_public_asset,
)
@pytest.mark.no_db
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "request_path", "match_info", "expected_location"),
    [
        (handle_login_page, "/login?legacy=1&_shell=old&next=%2Fsupport", {}, "/app/login?next=/support"),
        (handle_admin_page, "/admin?legacy=1&_shell=old&tab=queue", {}, "/app/admin?tab=queue"),
        (handle_support_page, "/support?legacy=1&_shell=old&scope=mine", {}, "/app/support?scope=mine"),
        (
            handle_support_page,
            "/support?scope=mine&scope=team&legacy=1&_shell=old",
            {},
            "/app/support?scope=mine&scope=team",
        ),
        (handle_help_page, "/help?legacy=1&_shell=old&source=qr", {}, "/app/help?source=qr"),
        (handle_ticket_page, "/ticket.html?legacy=1&_shell=old&code=A1B2C3", {}, "/app/ticket?code=A1B2C3"),
        (
            handle_ticket_page_by_id,
            "/ticket/T-100?legacy=1&_shell=old&code=A1B2C3",
            {"ticket_id": "T-100"},
            "/app/ticket/T-100?code=A1B2C3",
        ),
    ],
)
async def test_retired_shell_routes_redirect_to_react_and_strip_legacy_query(
    handler,
    request_path,
    match_info,
    expected_location,
):
    request = make_mocked_request("GET", request_path, match_info=match_info)

    with pytest.raises(web.HTTPPermanentRedirect) as exc_info:
        await handler(request)

    assert exc_info.value.location == expected_location


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_retired_shell_assets_and_workbenches_are_unregistered():
    app = web.Application()
    setup_routes(app)

    for path in (
        "/admin.css",
        "/admin.js",
        "/support.css",
        "/support.js",
        "/login.css",
        "/login.js",
        "/help.css",
        "/help.js",
        "/ticket.css",
        "/ticket.js",
        "/web_shared.js",
        "/admin_modules_workbench.html",
        "/admin_modules_workbench.js",
        "/endpoint_module_workbench.js",
        "/admin_ticket_forms_builder.html",
        "/admin_ticket_forms_builder.js",
    ):
        resolved = await app.router.resolve(make_mocked_request("GET", path))

        assert resolved.http_exception is not None
        assert resolved.http_exception.status == 404


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_webapp_page_serves_dist_index(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text(
        "<!doctype html><html lang='ru'><head><title>pc_client</title></head>"
        "<body><div id='root'></div><script type='module' src='/assets/app.js'></script></body></html>",
        encoding="utf-8",
    )
    monkeypatch.setattr(webapp_assets_module, "WEBAPP_DIST_DIR", dist_dir)

    request = make_mocked_request("GET", "/app/support")
    response = await handle_webapp_page(request)

    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store, no-cache, must-revalidate"
    assert "lang='ru'" in response.text
    assert "/assets/app.js" in response.text


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_webapp_page_returns_503_when_dist_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp_assets_module, "WEBAPP_DIST_DIR", tmp_path / "missing-dist")

    request = make_mocked_request("GET", "/app/admin")
    response = await handle_webapp_page(request)

    assert response.status == 503
    assert "webapp" in response.text
    assert "pnpm --dir webapp run build" in response.text


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_webapp_asset_and_public_asset_are_served_from_dist(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "app.js").write_text("console.log('app bundle');", encoding="utf-8")
    (dist_dir / "favicon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
    monkeypatch.setattr(webapp_assets_module, "WEBAPP_DIST_DIR", dist_dir)

    asset_request = make_mocked_request("GET", "/assets/app.js", match_info={"asset_path": "app.js"})
    asset_response = await handle_webapp_asset(asset_request)

    assert asset_response.status == 200
    assert asset_response.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert "app bundle" in asset_response.text

    public_request = make_mocked_request("GET", "/favicon.svg", match_info={"asset_name": "favicon.svg"})
    public_response = await handle_webapp_public_asset(public_request)

    assert public_response.status == 200
    assert public_response.content_type == "image/svg+xml"
    assert "<svg" in public_response.text


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_webapp_public_asset_supports_direct_favicon_route_without_match_info(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "favicon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
    monkeypatch.setattr(webapp_assets_module, "WEBAPP_DIST_DIR", dist_dir)

    request = make_mocked_request("GET", "/favicon.svg")
    response = await handle_webapp_public_asset(request)

    assert response.status == 200
    assert response.content_type == "image/svg+xml"
    assert "<svg" in response.text
