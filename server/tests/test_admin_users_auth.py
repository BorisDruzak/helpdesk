import pytest

from tests.conftest import TEST_UI_ADMIN_TOKEN


def _admin_headers():
    return {"Authorization": "Bearer " + TEST_UI_ADMIN_TOKEN}


@pytest.mark.asyncio
async def test_admin_users_reject_invalid_actor_role(test_client):
    response = await test_client.post(
        "/api/admin/users",
        headers=_admin_headers(),
        json={"login": "role-root", "password": "LongEnoughPassword1", "actor_role": "root"},
    )
    payload = await response.json()

    assert response.status == 400
    assert payload["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_admin_users_default_role_is_user_not_admin(test_client):
    response = await test_client.post(
        "/api/admin/users",
        headers=_admin_headers(),
        json={"login": "default-role", "password": "LongEnoughPassword1"},
    )
    payload = await response.json()

    assert response.status == 201
    assert payload["actor_role"] == "user"


@pytest.mark.asyncio
async def test_admin_users_reject_common_password(test_client):
    response = await test_client.post(
        "/api/admin/users",
        headers=_admin_headers(),
        json={"login": "weak-password", "password": "admin123", "actor_role": "support"},
    )
    payload = await response.json()

    assert response.status == 400
    assert payload["error_code"] == "PASSWORD_POLICY_ERROR"
