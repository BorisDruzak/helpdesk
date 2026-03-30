import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from static_pages.handlers import (
    ADMIN_SHELL_VERSION,
    SUPPORT_SHELL_VERSION,
    handle_admin_page,
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
    assert "/admin.js?v=20260324b" in response.text
    assert "data-tab=\"workbench\"" in response.text
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
    assert "/support.js?v=20260330a" in response.text
    assert "Support Workspace" in response.text
    assert "id=\"ticketInbox\"" in response.text
    assert "id=\"workbenchDrawer\"" in response.text
