from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device
from app.repos.registry_repo import RegistryRepo
from registry.service import RegistryIngestionService


@pytest.mark.asyncio
async def test_registry_ingests_agent_handshake_as_unverified_pc_asset(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add(
            Device(
                device_id="device-registry-1",
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="BUH-214-03",
                os="Windows 11",
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
                capabilities={},
                device_metadata={"machine_id": "device-registry-1"},
            )
        )
        await session.commit()

    async with session_maker() as session:
        service = RegistryIngestionService(session)
        asset = await service.ingest_agent_handshake(
            device_id="device-registry-1",
            hostname="BUH-214-03",
            os_name="Windows 11",
            agent_version="1.0.0",
            metadata={"machine_id": "device-registry-1", "source": "handshake"},
        )
        await session.commit()

    async with session_maker() as session:
        repo = RegistryRepo(session)
        stored = await repo.get_asset_by_device_id("device-registry-1")

    assert asset.asset_type == "pc"
    assert stored is not None
    assert stored.name == "BUH-214-03"
    assert stored.hostname == "BUH-214-03"
    assert stored.device_id == "device-registry-1"
    assert stored.source == "agent"
    assert stored.status == "unverified"
    assert stored.discovery_payload["os"] == "Windows 11"


@pytest.mark.asyncio
async def test_registry_profile_upsert_creates_person_location_and_links_device(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        service = RegistryIngestionService(session)
        await service.ingest_agent_handshake(
            device_id="device-registry-2",
            hostname="DOC-214-01",
            os_name="Windows 11",
            agent_version="1.0.0",
            metadata={},
        )
        result = await service.ingest_requester_profile(
            device_id="device-registry-2",
            requester_id="agent-profile:ivanov",
            display_name="Иванов Иван",
            profile={
                "full_name": "Иванов Иван",
                "building": "Здание 1",
                "room": "214",
                "phone": "+7 000 000-00-00",
                "department": "Бухгалтерия",
            },
        )
        await session.commit()

    async with session_maker() as session:
        repo = RegistryRepo(session)
        person = await repo.get_person(result.person_id)
        asset = await repo.get_asset_by_device_id("device-registry-2")
        location = await repo.get_location(result.location_id)
        department = await repo.get_department(result.department_id)

    assert person is not None
    assert person.display_name == "Иванов Иван"
    assert person.phone == "+7 000 000-00-00"
    assert person.source == "agent_profile"
    assert person.status == "self_reported"
    assert asset is not None
    assert asset.assigned_person_id == person.person_id
    assert asset.location_id == location.location_id
    assert location.building == "Здание 1"
    assert location.room == "214"
    assert location.status == "pending"
    assert department.name == "Бухгалтерия"
