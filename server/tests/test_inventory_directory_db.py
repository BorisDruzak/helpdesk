from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RegistryAdminEvent, RegistryPerson, RegistryPersonIdentity, UiUser
from registry import inventory_directory
from tests.test_inventory_directory_no_db import PERSON, snapshot

pytestmark = [pytest.mark.asyncio, pytest.mark.db_cleanup("registry_access")]
ADMIN = {"Authorization": "Bearer test-ui-admin-token"}
READ_PATH = "/api/web/requester/inventory-devices"


async def create_account(test_engine, login=None):
    login = login or "fixture-" + uuid4().hex
    token = f"test-ui-user:{login}"
    person_id = str(uuid4())
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker.begin() as session:
        session.add(RegistryPerson(person_id=person_id, display_name="Fixture employee", status="active"))
        session.add(UiUser(user_login=login, password_hash="fixture", actor_role="user", is_active=True))
        await session.flush()
        session.add(RegistryPersonIdentity(person_id=person_id, provider="ui_login",
            identifier=login, normalized_identifier=login, verified=True))
    return person_id, login, {"Authorization": f"Bearer {token}"}


async def test_linked_inventory_projection_remains_scoped_audited_and_available_during_outage(
    test_client, test_engine, monkeypatch,
):
    first_id, first_login, first_headers = await create_account(test_engine)
    second_id, second_login, second_headers = await create_account(test_engine)
    url = f"/api/web/admin/registry/people/{first_id}/inventory-link"
    other_url = f"/api/web/admin/registry/people/{second_id}/inventory-link"
    data = {"inventory_person_id": str(PERSON), "user_login": first_login, "reason": "Fixture employee confirmed"}
    fixture = snapshot()
    unavailable = False

    async def fetch(person_id):
        assert person_id == PERSON
        if unavailable:
            raise inventory_directory.InventoryUnavailable("fixture unavailable")
        return inventory_directory.InventoryProfile.model_validate(fixture)

    monkeypatch.setattr(inventory_directory, "fetch_person", fetch)
    monkeypatch.delenv("HELPDESK_INVENTORY_BASE_URL", raising=False)
    response = await test_client.get(READ_PATH, headers=first_headers)
    assert (await response.json())["data"]["sync_state"] == "disabled"
    monkeypatch.setenv("HELPDESK_INVENTORY_BASE_URL", "https://fixture.invalid")
    assert (await test_client.get(READ_PATH, headers={"Authorization": "Bearer test-ui-support-token"})).status == 403
    assert (await test_client.put(url, headers=first_headers, json=data)).status == 403
    assert (await test_client.put(url, headers=ADMIN, json={**data, "user_login": second_login})).status == 409
    assert (await test_client.put(url, headers=ADMIN, json=data)).status == 200
    assert (await test_client.put(url, headers=ADMIN, json=data)).status == 200
    assert (await test_client.put(other_url, headers=ADMIN, json={**data, "user_login": second_login})).status == 409
    assert (await (await test_client.get(READ_PATH, headers=second_headers)).json())["data"]["assignments"] == []
    response = await test_client.get(READ_PATH, headers=first_headers)
    assert response.headers["Cache-Control"] == "no-store"
    current = await response.json()
    assert current["data"]["sync_state"] == "current"
    assert current["data"]["assignments"][0]["endpoint_status"] == "offline"
    unavailable = True
    response = await test_client.get(READ_PATH, headers=first_headers)
    stale = await response.json()
    assert stale["data"]["sync_state"] == "stale"
    assert stale["data"]["assignments"][0]["endpoint_status"] == "unknown"
    unavailable = False
    fixture["observed_at"] = "2026-11-11T10:06:00Z"
    fixture["assignments"] = []
    assert (await (await test_client.get(READ_PATH, headers=first_headers)).json())["data"]["assignments"] == []
    assert (await test_client.delete(url, headers=ADMIN, json={"reason": "fixture ended"})).status == 200
    assert (await (await test_client.get(READ_PATH, headers=first_headers)).json())["data"]["sync_state"] == "unlinked"
    async with async_sessionmaker(test_engine)() as session:
        events = list(await session.scalars(select(RegistryAdminEvent.event_type)
            .where(RegistryAdminEvent.object_id == first_id).order_by(RegistryAdminEvent.event_at)))
        assert events == ["inventory_link_confirmed", "inventory_link_removed"]


async def test_alias_with_conflict_or_a_different_account_does_not_prove_ownership(test_client, test_engine, monkeypatch):
    first_id, first_login, first_headers = await create_account(test_engine, "same login")
    _, second_login, _ = await create_account(test_engine, "same  login")
    monkeypatch.setenv("HELPDESK_INVENTORY_BASE_URL", "https://fixture.invalid")

    async def fetch(_):
        return inventory_directory.InventoryProfile.model_validate(snapshot())

    monkeypatch.setattr(inventory_directory, "fetch_person", fetch)
    url = f"/api/web/admin/registry/people/{first_id}/inventory-link"
    data = {"inventory_person_id": str(PERSON), "user_login": first_login, "reason": "Fixture verified"}
    assert (await test_client.put(url, headers=ADMIN, json={**data, "user_login": second_login})).status == 409
    assert (await test_client.put(url, headers=ADMIN, json=data)).status == 200
    async with async_sessionmaker(test_engine).begin() as session:
        alias = await session.scalar(select(RegistryPersonIdentity).where(RegistryPersonIdentity.person_id == first_id))
        alias.metadata_json = {"collision_person_id": str(uuid4())}
    response = await test_client.get(READ_PATH, headers=first_headers)
    assert (await response.json())["data"]["sync_state"] == "unlinked"
    assert (await test_client.put(url, headers=ADMIN, json=data)).status == 409
