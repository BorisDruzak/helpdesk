import pytest
from aiohttp.test_utils import make_mocked_request

from auth.context import AuthContext, AuthType
from auth.handlers import handle_ui_session


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ui_session_requires_ui_token_context():
    request = make_mocked_request("GET", "/api/ui_session")

    response = await handle_ui_session(request)

    assert response.status == 401
    assert response.text


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ui_session_returns_actor_from_ui_token():
    request = make_mocked_request("GET", "/api/ui_session")
    request["auth_context"] = AuthContext(
        actor_id="support1",
        actor_role="support",
        auth_type=AuthType.UI_TOKEN,
        token="test-token",
    )

    response = await handle_ui_session(request)

    assert response.status == 200
    assert '"status": "success"' in response.text
    assert '"user_login": "support1"' in response.text
    assert '"actor_role": "support"' in response.text
