import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from static_pages.handlers import (
    ADMIN_SHELL_VERSION,
    LOGIN_SHELL_VERSION,
    SUPPORT_SHELL_VERSION,
    handle_admin_page,
    handle_login_page,
    handle_support_page,
)
import static_pages.webapp_assets as webapp_assets_module
from static_pages.webapp_assets import (
    handle_webapp_asset,
    handle_webapp_page,
    handle_webapp_public_asset,
)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_admin_page_redirects_to_versioned_shell():
    request = make_mocked_request("GET", "/admin")

    with pytest.raises(web.HTTPFound) as exc_info:
        await handle_admin_page(request)

    assert exc_info.value.location == f"/admin?_shell={ADMIN_SHELL_VERSION}"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_admin_page_serves_html_for_current_shell_version():
    request = make_mocked_request("GET", f"/admin?_shell={ADMIN_SHELL_VERSION}")

    response = await handle_admin_page(request)

    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store, no-cache, must-revalidate"
    assert "/web_shared.js?v=20260414a" in response.text
    assert "/admin.js?v=20260419a" in response.text
    assert "id=\"adminSessionBar\"" in response.text
    assert "Support Workspace" not in response.text
    assert "data-tab=\"tech\"" in response.text


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_support_page_redirects_to_versioned_shell():
    request = make_mocked_request("GET", "/support")

    with pytest.raises(web.HTTPFound) as exc_info:
        await handle_support_page(request)

    assert exc_info.value.location == f"/support?_shell={SUPPORT_SHELL_VERSION}"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_support_page_serves_workspace_shell():
    request = make_mocked_request("GET", f"/support?_shell={SUPPORT_SHELL_VERSION}")

    response = await handle_support_page(request)

    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store, no-cache, must-revalidate"
    assert "/web_shared.js?v=20260414a" in response.text
    assert "/support.js?v=20260419a" in response.text
    assert "Support Workspace" in response.text
    assert "id=\"workspaceShell\"" in response.text
    assert "id=\"workspaceModeSwitch\"" in response.text
    assert "id=\"queueHeadScopeDock\"" in response.text
    assert "id=\"selectedTicketTitle\"" in response.text
    assert "id=\"queueDesk\"" in response.text
    assert "id=\"queueBoardList\"" in response.text
    assert "id=\"ticketWorkbench\"" in response.text
    assert "id=\"embeddedTicketFrame\"" in response.text


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_login_page_redirects_to_versioned_shell():
    request = make_mocked_request("GET", "/login")

    with pytest.raises(web.HTTPFound) as exc_info:
        await handle_login_page(request)

    assert exc_info.value.location == f"/login?_shell={LOGIN_SHELL_VERSION}"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_login_page_serves_role_selector():
    request = make_mocked_request("GET", f"/login?_shell={LOGIN_SHELL_VERSION}")

    response = await handle_login_page(request)

    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store, no-cache, must-revalidate"
    assert "/login.js?v=20260330a" in response.text
    assert "id=\"roleSwitch\"" in response.text
    assert "data-target=\"support\"" in response.text


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
