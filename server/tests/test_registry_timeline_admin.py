from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceRegistrationClaim, DeviceUserBinding
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.policy_service import RegistryPolicyService
from registry.registration_service import RegistrationService


pytestmark = pytest.mark.db_cleanup("registry_access")

ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}


def _device(device_id: str, *, hostname: str = "timeline-pc") -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname=hostname,
        os="Windows 11",
        capabilities={},
        device_metadata={"machine_id": device_id},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


async def _person_from_claim(
    service: RegistrationService,
    *,
    device_id: str,
    requester_id: str,
    display_name: str,
) -> str:
    await RegistryPolicyService(service.session).update_policies(
        {"registration": {"require_admin_confirmation": True}},
        actor_id="admin-test",
    )
    result = await service.submit_agent_profile_claim(
        device_id=device_id,
        requester_id=requester_id,
        display_name=display_name,
        profile={
            "full_name": display_name,
            "email": f"{requester_id}@example.test",
            "login": requester_id,
            "department": "IT",
            "building": "HQ",
            "room": "401",
            "user_confirmed": True,
        },
    )
    return result["person"]["person_id"]


def _assert_timeline_item_shape(item: dict[str, object]) -> None:
    assert item["event_id"]
    assert item["source"] in {"registry_admin", "registration", "account"}
    assert item["event_type"]
    assert item["event_at"]
    assert isinstance(item["payload"], dict)
    assert isinstance(item["related"], dict)
    assert "summary" in item
    assert "changes" in item


@pytest.mark.asyncio
async def test_person_timeline_records_admin_and_identity_events(test_client):
    create_response = await test_client.post(
        "/api/web/admin/registry/people",
        json={
            "display_name": "Timeline User",
            "full_name": "Timeline User Full",
            "email": "timeline@example.test",
            "reason": "создание для проверки timeline",
        },
        headers=ADMIN_HEADERS,
    )
    assert create_response.status == 200
    person_id = (await create_response.json())["data"]["person"]["person_id"]

    update_response = await test_client.patch(
        f"/api/web/admin/registry/people/{person_id}",
        json={"phone": "+70000000001", "reason": "уточнили телефон"},
        headers=ADMIN_HEADERS,
    )
    assert update_response.status == 200

    identity_response = await test_client.post(
        f"/api/web/admin/registry/people/{person_id}/identities",
        json={"provider": "email", "identifier": "Timeline@Example.Test", "verified": False, "reason": "добавлен email"},
        headers=ADMIN_HEADERS,
    )
    assert identity_response.status == 200
    identity_id = (await identity_response.json())["data"]["identity"]["identity_id"]

    verify_response = await test_client.patch(
        f"/api/web/admin/registry/identities/{identity_id}",
        json={"verified": True, "reason": "email проверен вручную"},
        headers=ADMIN_HEADERS,
    )
    assert verify_response.status == 200

    delete_response = await test_client.delete(
        f"/api/web/admin/registry/identities/{identity_id}",
        json={"reason": "ошибочно заведенный identity"},
        headers=ADMIN_HEADERS,
    )
    assert delete_response.status == 200

    timeline_response = await test_client.get(
        f"/api/web/admin/registry/timeline/person/{person_id}",
        headers=ADMIN_HEADERS,
    )
    assert timeline_response.status == 200
    items = (await timeline_response.json())["data"]["items"]
    by_type = {item["event_type"]: item for item in items}

    assert {"person_created", "person_updated", "identity_added", "identity_verified", "identity_deleted"} <= set(by_type)
    for event_type in ("person_created", "person_updated", "identity_added", "identity_verified", "identity_deleted"):
        item = by_type[event_type]
        _assert_timeline_item_shape(item)
        assert item["actor_id"] == "admin-test"
        assert item["actor_role"] == "admin"
        assert item["related"]["person_id"] == person_id

    assert by_type["person_updated"]["reason"] == "уточнили телефон"
    assert by_type["person_updated"]["changes"]
    assert by_type["identity_deleted"]["related"]["identity_id"] == identity_id


@pytest.mark.asyncio
async def test_unified_timeline_covers_device_binding_and_claim(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        registration = RegistrationService(session)
        person_id = await _person_from_claim(
            registration,
            device_id=device_id,
            requester_id="timeline-owner",
            display_name="Timeline Owner",
        )
        result = await registration.bind_person_to_device(
            device_id=device_id,
            person_id=person_id,
            relationship_type="primary_user",
            replace_existing=False,
            reviewed_by="admin-test",
            reason="timeline bind reason",
        )
        binding_id = result["binding"]["binding_id"]
        binding = await session.get(DeviceUserBinding, binding_id)
        claim = (
            await session.execute(
                select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.claim_id == binding.source_claim_id)
            )
        ).scalar_one()
        await session.commit()
        claim_id = claim.claim_id

    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        device_items = await service.list_timeline(object_type="device", object_id=device_id)
        binding_items = await service.list_timeline(object_type="binding", object_id=binding_id)
        claim_items = await service.list_timeline(object_type="claim", object_id=claim_id)

    for collection in (device_items, binding_items, claim_items):
        assert collection
        for item in collection:
            _assert_timeline_item_shape(item)

    assert any(item["event_type"] == "admin_binding_created" and item["source"] == "registration" for item in device_items)
    assert any(item["related"]["binding_id"] == binding_id for item in binding_items)
    assert any(item["related"]["claim_id"] == claim_id for item in claim_items)
    assert any(item["reason"] == "timeline bind reason" for item in binding_items)


@pytest.mark.asyncio
async def test_transfer_timeline_explains_actor_reason_changes_and_related_entities(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id, hostname="timeline-transfer-pc"))
        registration = RegistrationService(session)
        old_person_id = await _person_from_claim(
            registration,
            device_id=device_id,
            requester_id="timeline-transfer-old",
            display_name="Timeline Transfer Old",
        )
        new_person_id = await _person_from_claim(
            registration,
            device_id=device_id,
            requester_id="timeline-transfer-new",
            display_name="Timeline Transfer New",
        )
        initial = await registration.bind_person_to_device(
            device_id=device_id,
            person_id=old_person_id,
            relationship_type="primary_user",
            replace_existing=False,
            reviewed_by="admin-test",
            reason="initial transfer owner",
        )
        old_binding_id = initial["binding"]["binding_id"]
        transfer = await registration.transfer_owner(
            device_id=device_id,
            new_person_id=new_person_id,
            old_binding_action="transferred",
            reviewed_by="admin-test",
            reason="owner left department",
        )
        new_binding_id = transfer["binding"]["binding_id"]
        await session.commit()

    async with session_maker() as session:
        items = await RegistryAdminOperationsService(session).list_timeline(object_type="device", object_id=device_id)

    transfer_items = [item for item in items if item["event_type"] == "binding_transferred"]
    assert transfer_items
    transfer_item = next(item for item in transfer_items if item["related"].get("binding_id") == new_binding_id)
    assert transfer_item["actor_id"] == "admin-test"
    assert transfer_item["actor_role"] == "admin"
    assert transfer_item["reason"] == "owner left department"
    assert transfer_item["related"]["device_id"] == device_id
    assert transfer_item["related"]["person_id"] == new_person_id
    assert transfer_item["related"]["binding_id"] == new_binding_id
    assert any(change["field"] == "primary_person_id" and change["before"] == old_person_id and change["after"] == new_person_id for change in transfer_item["changes"])
    assert any(item["related"].get("binding_id") == old_binding_id for item in transfer_items)
