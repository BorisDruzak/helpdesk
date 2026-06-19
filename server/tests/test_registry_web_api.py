from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
import uuid

from app.db.models import Device, DeviceAccountSession, DeviceUserBinding, RegistryAdminEvent, RegistryPerson
from registry.service import RegistryIngestionService
from tests.conftest import TEST_UI_ADMIN_TOKEN


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


def _user_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-user:registry-picker-user"}


@pytest.mark.asyncio
async def test_web_admin_registry_returns_snapshot_for_reestr_ui(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.2.0",
                hostname="DOC-214-02",
                os="Windows 11",
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
                capabilities={},
                device_metadata={},
            )
        )
        service = RegistryIngestionService(session)
        await service.ingest_agent_handshake(
            device_id=device_id,
            hostname="DOC-214-02",
            os_name="Windows 11",
            agent_version="1.2.0",
            metadata={},
        )
        await service.ingest_requester_profile(
            device_id=device_id,
            requester_id="agent-profile:petrova",
            display_name="Петрова Анна",
            profile={
                "full_name": "Петрова Анна",
                "building": "Здание 2",
                "room": "305",
                "phone": "123-45",
                "department": "Документооборот",
            },
        )
        await session.commit()

    response = await test_client.get("/api/web/admin/registry", headers=_admin_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    data = payload["data"]
    assert data["summary"]["assets_count"] == 1
    assert data["summary"]["people_count"] == 1
    assert data["summary"]["locations_count"] == 1
    assert data["summary"]["data_quality_issue_count"] >= 1
    assert data["assets"][0]["device_id"] == device_id
    assert data["assets"][0]["assigned_person_display_name"] is None
    assert data["assets"][0]["registration_status"] == "pending"
    assert data["locations"][0]["building"] == "Здание 2"
    assert data["people"][0]["department_name"] == "Документооборот"


@pytest.mark.asyncio
async def test_web_admin_registry_person_update_writes_production_context_metadata(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    manager_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(RegistryPerson(person_id=manager_id, display_name="R7 Manager", source="manual", status="active"))
        session.add(RegistryPerson(person_id=person_id, display_name="R7 User", source="manual", status="active"))
        await session.commit()

    response = await test_client.patch(
        f"/api/web/admin/registry/people/{person_id}",
        headers=_admin_headers(),
        json={
            "display_name": "R7 User",
            "position": "Lead Engineer",
            "workplace_label": "Desk 12",
            "internal_extension": "4567",
            "manager_person_id": manager_id,
            "reason": "R7 production context",
        },
    )
    assert response.status == 200, await response.text()

    registry_response = await test_client.get("/api/web/admin/registry", headers=_admin_headers())
    assert registry_response.status == 200
    registry = (await registry_response.json())["data"]
    person = next(item for item in registry["people"] if item["person_id"] == person_id)
    assert person["position"] == "Lead Engineer"
    assert person["workplace_label"] == "Desk 12"
    assert person["internal_extension"] == "4567"
    assert person["manager_person_id"] == manager_id
    assert person["manager_name"] == "R7 Manager"

    async with session_maker() as session:
        row = await session.get(RegistryPerson, person_id)
        event = (
            await session.execute(
                select(RegistryAdminEvent).where(
                    RegistryAdminEvent.object_id == person_id,
                    RegistryAdminEvent.event_type == "person_updated",
                )
            )
        ).scalar_one()

    assert row.metadata_json["position"] == "Lead Engineer"
    assert row.metadata_json["workplace_label"] == "Desk 12"
    assert row.metadata_json["internal_extension"] == "4567"
    assert row.metadata_json["manager_person_id"] == manager_id
    assert event.payload["after"]["position"] == "Lead Engineer"


@pytest.mark.asyncio
async def test_web_admin_registry_person_archive_revokes_access_and_audits(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    person_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    binding_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.70",
                hostname="ARCHIVE-PC",
                os="Windows",
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
                capabilities={},
                device_metadata={},
            )
        )
        session.add(RegistryPerson(person_id=person_id, display_name="Archive User", source="manual", status="active"))
        await session.flush()
        session.add(
            DeviceUserBinding(
                binding_id=binding_id,
                device_id=device_id,
                person_id=person_id,
                relationship_type="primary_user",
                status="active",
                source="manual",
            )
        )
        await session.flush()
        session.add(
            DeviceAccountSession(
                session_id=session_id,
                device_id=device_id,
                person_id=person_id,
                binding_id=binding_id,
                account_mode="confirmed_binding",
                verification_status="verified",
                declared_account={},
                metadata_json={},
            )
        )
        await session.commit()

    response = await test_client.post(
        f"/api/web/admin/registry/people/{person_id}/archive",
        headers=_admin_headers(),
        json={"reason": "test archive"},
    )
    assert response.status == 200, await response.text()
    payload = (await response.json())["data"]
    assert payload["person"]["status"] == "archived"
    assert payload["revoked_bindings"][0]["binding_id"] == binding_id
    assert payload["revoked_sessions"][0]["session_id"] == session_id

    async with session_maker() as session:
        person = await session.get(RegistryPerson, person_id)
        binding = await session.get(DeviceUserBinding, binding_id)
        account_session = await session.get(DeviceAccountSession, session_id)
        event = (
            await session.execute(
                select(RegistryAdminEvent).where(
                    RegistryAdminEvent.object_id == person_id,
                    RegistryAdminEvent.event_type == "person_archived",
                )
            )
        ).scalar_one()

    assert person.status == "archived"
    assert binding.status == "revoked"
    assert account_session.verification_status == "revoked"
    assert event.reason == "test archive"
    assert event.payload["revoked_binding_ids"] == [binding_id]
    assert event.payload["revoked_session_ids"] == [session_id]


@pytest.mark.asyncio
async def test_registry_profile_endpoint_syncs_agent_profile(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.2.0",
                hostname="PROF-101",
                os="Windows 11",
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
                capabilities={},
                device_metadata={},
            )
        )
        await session.commit()

    response = await test_client.post(
        "/api/registry/profile",
        headers=_admin_headers(),
        json={
            "device_id": device_id,
            "requester_id": "agent-profile:sidorov",
            "display_name": "Сидоров Сергей",
            "profile": {
                "full_name": "Сидоров Сергей",
                "building": "Здание 3",
                "room": "101",
                "phone": "555",
                "department": "ИТ",
            },
        },
    )
    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["person"]["display_name"] == "Сидоров Сергей"
    assert payload["data"]["location"]["building"] == "Здание 3"
    assert payload["data"]["asset"]["device_id"] == device_id


@pytest.mark.asyncio
async def test_registry_options_available_to_agent_request_forms_without_full_snapshot(test_client, test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.2.0",
                hostname="OPT-214",
                os="Windows 11",
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
                capabilities={},
                device_metadata={},
            )
        )
        service = RegistryIngestionService(session)
        await service.ingest_agent_handshake(
            device_id=device_id,
            hostname="OPT-214",
            os_name="Windows 11",
            agent_version="1.2.0",
            metadata={},
        )
        await service.ingest_requester_profile(
            device_id=device_id,
            requester_id="agent-profile:options",
            display_name="Иван Иванов",
            profile={
                "full_name": "Иван Иванов",
                "building": "Здание 4",
                "room": "214",
                "phone": "555",
                "department": "ИТ",
            },
        )
        await session.commit()

    async def fail_snapshot(*_args, **_kwargs):
        raise AssertionError("registry options must not build full admin snapshot")

    monkeypatch.setattr("web_api.registry_handlers.RegistrySnapshotService.build_snapshot", fail_snapshot)
    response = await test_client.get("/api/registry/options", headers=_user_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    data = payload["data"]
    assert {"value": device_id, "label": "OPT-214"} in data["devices"]
    assert any(item["label"] == "Иван Иванов" for item in data["users"])
    assert any(item["label"] == "ИТ" for item in data["departments"])
    assert any(item["label"] == "Здание 4 / 214" for item in data["locations"])
