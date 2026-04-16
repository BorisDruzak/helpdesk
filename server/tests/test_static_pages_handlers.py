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
    assert "/admin.js?v=20260416b" in response.text
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
    assert "/support.js?v=20260414c" in response.text
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
