from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from static_pages.cutover import (
    CUTOVER_REASON_BUNDLE_MISSING,
    CUTOVER_REASON_FLAG_DISABLED,
    CUTOVER_REASON_LOGIN_REQUIRED,
    build_webapp_cutover_state,
)
from static_pages.handlers import (
    ADMIN_SHELL_VERSION,
    LOGIN_SHELL_VERSION,
    SUPPORT_SHELL_VERSION,
    handle_admin_page,
    handle_help_page,
    handle_login_page,
    handle_support_page,
    handle_ticket_page_by_id,
)
import static_pages.handlers as static_handlers_module
import static_pages.webapp_assets as webapp_assets_module
from static_pages.webapp_assets import (
    handle_webapp_asset,
    handle_webapp_page,
    handle_webapp_public_asset,
)


def _install_built_webapp_bundle(tmp_path, monkeypatch) -> None:
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<!doctype html><html lang='ru'><body><div id='root'></div></body></html>",
        encoding="utf-8",
    )
    (assets_dir / "app.js").write_text("console.log('bundle ready');", encoding="utf-8")
    monkeypatch.setattr(static_handlers_module, "WEBAPP_DIST_DIR", dist_dir)
    monkeypatch.setattr(webapp_assets_module, "WEBAPP_DIST_DIR", dist_dir)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_admin_page_redirects_to_versioned_shell(monkeypatch):
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_LOGIN_ENABLED", False)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_ADMIN_ENABLED", False)
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
async def test_support_page_redirects_to_versioned_shell(monkeypatch):
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_LOGIN_ENABLED", False)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_SUPPORT_ENABLED", False)
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
async def test_support_page_redirects_to_new_app_when_cutover_enabled(tmp_path, monkeypatch):
    _install_built_webapp_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_LOGIN_ENABLED", True)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_SUPPORT_ENABLED", True)
    request = make_mocked_request("GET", "/support")

    with pytest.raises(web.HTTPFound) as exc_info:
        await handle_support_page(request)

    assert exc_info.value.location == "/app/support"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_support_page_keeps_legacy_escape_when_cutover_enabled(tmp_path, monkeypatch):
    _install_built_webapp_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_LOGIN_ENABLED", True)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_SUPPORT_ENABLED", True)
    request = make_mocked_request("GET", "/support?legacy=1")

    with pytest.raises(web.HTTPFound) as exc_info:
        await handle_support_page(request)

    assert exc_info.value.location == f"/support?legacy=1&_shell={SUPPORT_SHELL_VERSION}"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_help_page_redirects_to_react_when_requester_cutover_enabled(tmp_path, monkeypatch):
    _install_built_webapp_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_HELP_ENABLED", True)
    request = make_mocked_request("GET", "/help?source=qr")

    with pytest.raises(web.HTTPFound) as exc_info:
        await handle_help_page(request)

    assert exc_info.value.location == "/app/help?source=qr"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ticket_page_redirects_to_react_when_requester_cutover_enabled(tmp_path, monkeypatch):
    _install_built_webapp_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_TICKET_ENABLED", True)
    request = make_mocked_request("GET", "/ticket/T-100?code=A1B2C3", match_info={"ticket_id": "T-100"})

    with pytest.raises(web.HTTPFound) as exc_info:
        await handle_ticket_page_by_id(request)

    assert exc_info.value.location == "/app/ticket/T-100?code=A1B2C3"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_help_and_ticket_keep_legacy_escape_when_requester_cutover_enabled(tmp_path, monkeypatch):
    _install_built_webapp_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_HELP_ENABLED", True)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_TICKET_ENABLED", True)

    help_response = await handle_help_page(make_mocked_request("GET", "/help?legacy=1"))
    ticket_response = await handle_ticket_page_by_id(
        make_mocked_request("GET", "/ticket/T-100?legacy=1", match_info={"ticket_id": "T-100"})
    )

    assert help_response.status == 200
    assert ticket_response.status == 200


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_login_page_redirects_to_versioned_shell(monkeypatch):
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_LOGIN_ENABLED", False)
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
async def test_login_page_redirects_to_new_app_when_cutover_enabled(tmp_path, monkeypatch):
    _install_built_webapp_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_LOGIN_ENABLED", True)
    request = make_mocked_request("GET", "/login?next=%2Fsupport")

    with pytest.raises(web.HTTPFound) as exc_info:
        await handle_login_page(request)

    assert exc_info.value.location == "/app/login?next=/support"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_admin_page_redirects_to_new_app_when_cutover_is_ready(tmp_path, monkeypatch):
    _install_built_webapp_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_LOGIN_ENABLED", True)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_ADMIN_ENABLED", True)
    request = make_mocked_request("GET", "/admin")

    with pytest.raises(web.HTTPFound) as exc_info:
        await handle_admin_page(request)

    assert exc_info.value.location == "/app/admin"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_support_page_stays_on_legacy_when_login_cutover_is_disabled(tmp_path, monkeypatch):
    _install_built_webapp_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_LOGIN_ENABLED", False)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_SUPPORT_ENABLED", True)
    request = make_mocked_request("GET", "/support")

    with pytest.raises(web.HTTPFound) as exc_info:
        await handle_support_page(request)

    assert exc_info.value.location == f"/support?_shell={SUPPORT_SHELL_VERSION}"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_login_page_stays_on_legacy_when_bundle_is_missing(tmp_path, monkeypatch):
    missing_dist = tmp_path / "missing-dist"
    monkeypatch.setattr(static_handlers_module, "WEBAPP_DIST_DIR", missing_dist)
    monkeypatch.setattr(static_handlers_module, "WEBAPP_CUTOVER_LOGIN_ENABLED", True)
    request = make_mocked_request("GET", "/login")

    with pytest.raises(web.HTTPFound) as exc_info:
        await handle_login_page(request)

    assert exc_info.value.location == f"/login?_shell={LOGIN_SHELL_VERSION}"


@pytest.mark.no_db
def test_cutover_state_requires_bundle_and_login(tmp_path):
    missing_dist = Path("C:/missing-webapp-dist")
    state = build_webapp_cutover_state(
        dist_dir=missing_dist,
        login_enabled=False,
        support_enabled=True,
        admin_enabled=True,
    )

    assert state.bundle_ready is False
    assert state.login.reason == CUTOVER_REASON_FLAG_DISABLED
    assert state.support.reason == CUTOVER_REASON_BUNDLE_MISSING
    assert state.admin.reason == CUTOVER_REASON_BUNDLE_MISSING

    ready_dist = tmp_path / "ready-dist"
    assets_dir = ready_dist / "assets"
    assets_dir.mkdir(parents=True)
    (ready_dist / "index.html").write_text("<html></html>", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")
    ready_state = build_webapp_cutover_state(
        dist_dir=ready_dist,
        login_enabled=False,
        support_enabled=True,
        admin_enabled=True,
    )
    assert ready_state.support.reason == CUTOVER_REASON_LOGIN_REQUIRED
    assert ready_state.admin.reason == CUTOVER_REASON_LOGIN_REQUIRED


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
