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



async def test_inventory_invitation_endpoint_discloses_only_the_selected_employee(test_client, test_engine, monkeypatch):
    import config
    from app.db.models import RegistryDepartment, RegistryInventoryInvite
    from auth.inventory_invitation import invite_digest

    monkeypatch.setenv("HELPDESK_INVENTORY_BASE_URL", "https://fixture.invalid")
    monkeypatch.setattr(config, "WEB_SELF_REGISTRATION_ENABLED", True)
    department_id = str(uuid4())
    async with async_sessionmaker(test_engine).begin() as session:
        session.add(RegistryDepartment(department_id=department_id, name="Fixture department", status="active"))

    async def fetch(person_id):
        assert person_id == PERSON
        return inventory_directory.InventoryProfile.model_validate(snapshot())

    monkeypatch.setattr(inventory_directory, "fetch_person", fetch)
    issue_path = "/api/web/admin/registry/inventory-invitations"
    preview_path = "/api/web/session/registration-invitation"
    payload = {"inventory_person_id": str(PERSON), "department_id": department_id, "reason": "Fixture confirmed"}
    assert (await test_client.post(issue_path, json=payload)).status == 403
    issued = await test_client.post(issue_path, headers=ADMIN, json=payload)
    assert issued.status == 201
    assert issued.headers["Cache-Control"] == "no-store"
    code = (await issued.json())["data"]["code"]
    assert len(code) == 43
    async with async_sessionmaker(test_engine)() as session:
        stored = await session.get(RegistryInventoryInvite, str(PERSON))
        assert stored.code_digest == invite_digest(code) != code
    assert (await test_client.post(preview_path, headers={"Origin": "https://invalid.example"}, json={"code": code})).status == 403
    origin = str(test_client.make_url("/").origin())
    headers = {"Origin": origin}
    preview = await test_client.post(preview_path, headers=headers, json={"code": code})
    assert preview.status == 200
    assert (await preview.json())["data"] == {
        "full_name": "Fixture employee", "department": "Fixture department", "department_id": department_id,
    }
    assert preview.headers["Cache-Control"] == "no-store"
    replacement = await test_client.post(issue_path, headers=ADMIN, json=payload)
    assert replacement.status == 201
    second_code = (await replacement.json())["data"]["code"]
    assert (await test_client.post(preview_path, headers=headers, json={"code": code})).status == 409

    person_id, login, _ = await create_account(test_engine)
    link_path = f"/api/web/admin/registry/people/{person_id}/inventory-link"
    confirmation = {"inventory_person_id": str(PERSON), "user_login": login, "reason": "Fixture confirmed manually"}
    assert (await test_client.put(link_path, headers=ADMIN, json=confirmation)).status == 200
    assert (await test_client.delete(link_path, headers=ADMIN, json={"reason": "Fixture removed"})).status == 200
    assert (await test_client.post(preview_path, headers=headers, json={"code": second_code})).status == 409

    def issue():
        return test_client.post(issue_path, headers=ADMIN, json=payload)

    active = await issue()
    third_code = (await active.json())["data"]["code"]
    revoked = await test_client.delete(f"{issue_path}/{PERSON}", headers=ADMIN, json={"reason": "Fixture revoke"})
    assert (await revoked.json())["data"]["revoked"] is True
    assert (await test_client.post(preview_path, headers=headers, json={"code": third_code})).status == 409

    issued_again = await issue()
    final_code = (await issued_again.json())["data"]["code"]
    registration = {
        "request_id": str(uuid4()), "first_name": "employee", "last_name": "Fixture",
        "department_id": department_id, "phone": "1234", "inventory_invite_code": final_code,
        "password": "Long-fixture-password-43!", "password_repeat": "Long-fixture-password-43!",
    }
    response = await test_client.post("/api/web/session/register-requester", headers=headers, json=registration)
    assert response.status == 201
    requester = (await response.json())["data"]["user_login"]
    result = await test_client.get(READ_PATH, headers={"Authorization": f"Bearer test-ui-user:{requester}"})
    assert result.status == 200
    assert (await result.json())["data"]["assignments"][0]["name"] == "Fixture workstation"
