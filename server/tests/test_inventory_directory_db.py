from datetime import datetime, timedelta, timezone
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
    now = datetime.now(timezone.utc)
    fixture["observed_at"] = now.isoformat()
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
    fixture["observed_at"] = (now + timedelta(seconds=1)).isoformat()
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
        return inventory_directory.InventoryProfile.model_validate({**snapshot(), "observed_at": datetime.now(timezone.utc).isoformat()})

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


async def test_auto_binding_reconciles_authoritative_inventory_without_replacing_manual_owner(test_engine):
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from app.db.models import DeviceUserBinding, RegistryInventoryLink, RegistryEndpointDeviceMapping
    from domain_ports.endpoint import EndpointDeviceProjection
    from app.repos.inventory_binding_authority import INVENTORY_ACTIVE
    from registry.inventory_device_binding import InventoryDeviceBindingService, SOURCE
    from registry.registration_service import RegistrationService

    first, first_login, _ = await create_account(test_engine)
    second, _, _ = await create_account(test_engine)
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    fixture = snapshot()
    fixture["observed_at"] = datetime.now(timezone.utc).isoformat()
    profile = inventory_directory.InventoryProfile.model_validate(fixture)
    ref = str(profile.assignments[0].endpoint_device_id)

    async def read_device(device):
        return EndpointDeviceProjection(device=device, display_name="Fixture workstation", retired=False, last_seen_at=None)

    async with maker.begin() as session:
        link = RegistryInventoryLink(person_id=first, user_login=first_login, inventory_person_id=str(PERSON),
            approval_id=str(uuid4()))
        session.add(link)
        await session.flush()
        service = InventoryDeviceBindingService(session, SimpleNamespace(read_device=read_device))
        result = await service.reconcile(link, profile)
        assert result[str(profile.assignments[0].assignment_id)]["state"] == "bound"
        assert await session.get(RegistryEndpointDeviceMapping, ref) is not None
        existing = await session.scalar(select(DeviceUserBinding).where(DeviceUserBinding.device_id == ref))
        assert existing.source == SOURCE and existing.person_id == first
        assert existing.status == INVENTORY_ACTIVE
        legacy = await session.scalar(select(DeviceUserBinding).where(
            DeviceUserBinding.device_id == ref, DeviceUserBinding.status == "active",
        ))
        assert legacy is None
        original_id = existing.binding_id
        assert (await service.reconcile(link, profile))[str(profile.assignments[0].assignment_id)]["device_id"] == ref
        await RegistrationService(session).revoke_binding(original_id, revoked_by="fixture-admin", reason="fixture")
        assert existing.status == "revoked"
        assert (await service.reconcile(link, profile))[str(profile.assignments[0].assignment_id)]["state"] == "conflict"
        manual = DeviceUserBinding(device_id=ref, person_id=second, relationship_type="primary_user",
                                   status="active", source="admin_manual")
        session.add(manual)
        await session.flush()
        replacement_assignment = profile.assignments[0].model_copy(update={"assignment_id": uuid4()})
        conflict = await service.reconcile(link, profile.model_copy(update={"assignments": [replacement_assignment]}))
        assert conflict[str(replacement_assignment.assignment_id)]["state"] == "conflict"
        assert manual.status == "active" and manual.person_id == second
        assert await session.get(DeviceUserBinding, original_id) is not None


async def test_auto_binding_api_and_worker_revoke_without_profile_open(test_client, test_engine, monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from app.db.models import DeviceUserBinding, RegistryInventoryLink
    from domain_ports.endpoint import EndpointDeviceProjection
    from registry import inventory_binding_refresh
    from app.repos.inventory_binding_authority import INVENTORY_ACTIVE

    monkeypatch.setenv("HELPDESK_INVENTORY_BASE_URL", "https://fixture.invalid")
    monkeypatch.setenv("HELPDESK_INVENTORY_AUTO_BIND_ENABLED", "true")
    person_id, login, requester = await create_account(test_engine)
    fixture = snapshot()
    full_assignments = fixture["assignments"]
    unavailable = False

    async def fetch(_):
        if unavailable:
            raise inventory_directory.InventoryUnavailable()
        return inventory_directory.InventoryProfile.model_validate({
            **fixture, "observed_at": datetime.now(timezone.utc).isoformat(),
        })

    async def read_device(device):
        return EndpointDeviceProjection(device=device, display_name="Fixture workstation", retired=False, last_seen_at=None)

    maker = async_sessionmaker(test_engine, expire_on_commit=False)

    @asynccontextmanager
    async def worker_session():
        async with maker.begin() as session:
            yield session

    monkeypatch.setattr(inventory_directory, "fetch_person", fetch)
    monkeypatch.setattr(inventory_binding_refresh, "get_session", worker_session)
    monkeypatch.setattr(inventory_binding_refresh, "DomainPortContainer", SimpleNamespace(
        from_config=lambda **_: SimpleNamespace(endpoint=SimpleNamespace(read_device=read_device)),
    ))
    path = f"/api/web/admin/registry/people/{person_id}/inventory-link"
    confirmed = await test_client.put(path, headers=ADMIN, json={
        "inventory_person_id": str(PERSON), "user_login": login, "reason": "Fixture verified",
    })
    assert confirmed.status == 200
    response = await test_client.get(READ_PATH, headers=requester)
    item, = (await response.json())["data"]["assignments"]
    assert item["helpdesk_binding_state"] == "bound"
    local_device = item["request_device_id"]
    from registry.service import RegistrySnapshotService
    async with maker() as session:
        snapshot_data = await RegistrySnapshotService(session).build_snapshot()
        visible = next(binding for binding in snapshot_data["active_bindings"] if binding["device_id"] == local_device)
        assert visible["source"] == "inventory_assignment"
    devices = await test_client.get("/api/web/requester/devices", headers=requester)
    assert (await devices.json())["data"]["devices"][0]["device_id"] == local_device

    fixture["assignments"] = []
    await inventory_binding_refresh.refresh_inventory_links()
    devices = await test_client.get("/api/web/requester/devices", headers=requester)
    assert (await devices.json())["data"]["devices"] == []
    async with maker.begin() as session:
        retired = await session.scalar(select(DeviceUserBinding).where(DeviceUserBinding.person_id == person_id))
        assert retired.status == "revoked"

    fixture["assignments"] = full_assignments
    assert (await test_client.get("/api/web/requester/bootstrap", headers=requester)).status == 200
    async with maker.begin() as session:
        active = await session.scalar(select(DeviceUserBinding).where(
            DeviceUserBinding.person_id == person_id, DeviceUserBinding.status == INVENTORY_ACTIVE,
        ))
        assert active is not None
        link = await session.get(RegistryInventoryLink, person_id)
        link.observed_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        active.inventory_verified_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    devices = await test_client.get("/api/web/requester/devices", headers=requester)
    assert (await devices.json())["data"]["devices"] == []
    unavailable = True
    await inventory_binding_refresh.refresh_inventory_links()
    devices = await test_client.get("/api/web/requester/devices", headers=requester)
    assert (await devices.json())["data"]["devices"] == []
    response = await test_client.get(READ_PATH, headers=requester)
    data = (await response.json())["data"]
    assert data["sync_state"] == "stale"
    assert data["assignments"][0]["endpoint_status"] == "unknown"
    assert "request_device_id" not in data["assignments"][0]


    from domain_ports.registry_contracts import EndpointPossessionBindingRequest
    from registry.endpoint_possession_service import EndpointPossessionService

    unavailable = False
    await inventory_binding_refresh.refresh_inventory_links()
    async with maker.begin() as session:
        proof = await EndpointPossessionService(session).bind(EndpointPossessionBindingRequest(
            operation_id=str(uuid4()), endpoint_device_ref=local_device, person_id=person_id,
            actor_id=login, hostname="Fixture workstation", platform="windows",
        ))
        assert proof.status == "applied"
        binding = await session.get(DeviceUserBinding, proof.binding.external_id)
        assert binding.source == "endpoint_possession_proof"
        assert binding.inventory_verified_until is None
    fixture["assignments"] = []
    await inventory_binding_refresh.refresh_inventory_links()
    devices = await test_client.get("/api/web/requester/devices", headers=requester)
    assert (await devices.json())["data"]["devices"][0]["device_id"] == local_device


async def test_operator_inventory_uses_ticket_scope_and_redacts_service_fields(test_client, test_engine, monkeypatch):
    from app.db.models import Ticket
    from tests.test_ticket_queue_routing_contracts import _seed_queue

    person_id, login, requester = await create_account(test_engine)
    visible_id, hidden_id, invalid_id = (str(uuid4()) for _ in range(3))
    fixture = snapshot()
    fixture["observed_at"] = datetime.now(timezone.utc).isoformat()
    ref = fixture["assignments"][0]["endpoint_device_id"]
    asset_id = fixture["assignments"][0]["inventory_asset_id"]
    available = True
    reads = []

    async def fetch(person):
        reads.append(person)
        if not available:
            raise inventory_directory.InventoryUnavailable()
        return inventory_directory.InventoryProfile.model_validate(fixture)

    monkeypatch.setenv("HELPDESK_INVENTORY_BASE_URL", "https://api.fixture.invalid")
    monkeypatch.setenv("HELPDESK_INVENTORY_WEB_URL", "https://web.fixture.invalid")
    monkeypatch.setattr(inventory_directory, "fetch_person", fetch)
    async with async_sessionmaker(test_engine).begin() as session:
        hidden = await _seed_queue(session, code=f"inventory_{uuid4().hex[:8]}", name="Inventory hidden", members=[])
        for ticket_id in (visible_id, hidden_id, invalid_id):
            session.add(Ticket(ticket_id=ticket_id, title="Inventory ticket", description="Fixture",
                status="queued", requester_id=login, requester_person_id=person_id, endpoint_device_ref=ref,
                queue_id=hidden.id if ticket_id == hidden_id else None,
                requester_external_ref=person_id if ticket_id == invalid_id else None))

    link_path = f"/api/web/admin/registry/people/{person_id}/inventory-link"
    person_path = f"/api/web/admin/registry/people/{person_id}/inventory-devices"
    ticket_path = "/api/web/support/tickets/{}/inventory-devices"
    support = {"Authorization": "Bearer test-ui-support-token"}
    assert (await test_client.put(link_path, headers=ADMIN, json={
        "inventory_person_id": str(PERSON), "user_login": login, "reason": "Verified fixture",
    })).status == 200
    before = len(reads)
    assert (await test_client.get(ticket_path.format(visible_id), headers=requester)).status == 403
    assert (await test_client.get(ticket_path.format(hidden_id), headers=support)).status == 403
    assert (await test_client.get(person_path, headers=support)).status == 403
    invalid = await test_client.get(ticket_path.format(invalid_id), headers=support)
    assert (await invalid.json())["data"]["assignments"] == []
    assert len(reads) == before

    response = await test_client.get(ticket_path.format(visible_id), headers=support)
    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store"
    row, = (await response.json())["data"]["assignments"]
    assert row["inventory_url"] == f"https://web.fixture.invalid/inventory/assets/{asset_id}"
    assert row["workstation_url"] == f"https://web.fixture.invalid/inventory/assets/{asset_id}#endpoint-heading"
    assert row["diagnostic_target"] is True
    assert not {"endpoint_binding_id", "endpoint_device_id", "request_device_id"} & row.keys()

    available = False
    response = await test_client.get(person_path, headers=ADMIN)
    data = (await response.json())["data"]
    assert data["sync_state"] == "stale"
    assert data["assignments"][0]["endpoint_status"] == "unknown"
    assert data["assignments"][0]["diagnostic_target"] is False


async def test_service_account_status_only_returns_current_verified_links(test_client, test_engine, monkeypatch):
    import hashlib

    from app.db.models import RegistryInventoryLink

    key = "inventory-status-fixture-key-with-32-bytes"
    monkeypatch.setenv("HELPDESK_INVENTORY_STATUS_TOKEN_HASH", hashlib.sha256(key.encode()).hexdigest())
    ids = [str(uuid4()) for _ in range(4)]
    accounts = [await create_account(test_engine) for _ in range(3)]
    async with async_sessionmaker(test_engine).begin() as session:
        for inventory_id, (person_id, login, _headers) in zip(ids, accounts):
            session.add(RegistryInventoryLink(person_id=person_id, user_login=login,
                inventory_person_id=inventory_id, approval_id=str(uuid4())))
        disabled = await session.get(UiUser, accounts[1][1])
        disabled.is_active = False
        alias = await session.scalar(select(RegistryPersonIdentity).where(RegistryPersonIdentity.person_id == accounts[2][0]))
        alias.metadata_json = {"collision_person_id": str(uuid4())}

    path = "/api/internal/inventory/v1/helpdesk-account-status"
    payload = {"inventory_person_ids": ids}
    headers = {"Authorization": f"Bearer {key}"}
    for unauthorized in (None, ADMIN, accounts[0][2], {"Authorization": "Bearer wrong"}):
        assert (await test_client.post(path, headers=unauthorized, json=payload)).status == 401
    assert (await test_client.post(path, headers=headers, json={"inventory_person_ids": [ids[0]] * 2})).status == 400
    assert (await test_client.post(path, headers=headers, json={"inventory_person_ids": [str(uuid4()) for _ in range(251)]})).status == 400
    response = await test_client.post(path, headers=headers, json=payload)
    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert await response.json() == {"linked": [{
        "inventory_person_id": ids[0], "person_id": accounts[0][0], "user_login": accounts[0][1],
    }]}
    monkeypatch.delenv("HELPDESK_INVENTORY_STATUS_TOKEN_HASH")
    assert (await test_client.post(path, headers=headers, json=payload)).status == 503
