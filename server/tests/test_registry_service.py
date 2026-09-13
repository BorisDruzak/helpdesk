from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceRegistrationClaim
from app.repos.registry_repo import RegistryRepo
from registry.service import RegistryIngestionService


pytestmark = pytest.mark.db_cleanup("registry_access")


@pytest.mark.asyncio
async def test_registry_profile_upsert_creates_person_location_and_registration_claim(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = "00000000-0000-4000-8000-000000000202"

    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="DOC-214-01",
                os="Windows 11",
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
                capabilities={},
                device_metadata={},
            )
        )
        await RegistryRepo(session).upsert_agent_asset(
            device_id=device_id,
            hostname="DOC-214-01",
            os_name="Windows 11",
            agent_version="1.0.0",
            metadata={},
        )
        service = RegistryIngestionService(session)
        result = await service.ingest_requester_profile(
            device_id=device_id,
            requester_id="agent-profile:ivanov",
            display_name="Ivan Ivanov",
            profile={
                "full_name": "Ivan Ivanov",
                "building": "Building 1",
                "room": "214",
                "phone": "+7 000 000-00-00",
                "department": "Accounting",
            },
        )
        await session.commit()

    async with session_maker() as session:
        repo = RegistryRepo(session)
        person = await repo.get_person(result.person_id)
        asset = await repo.get_asset_by_device_id(device_id)
        location = await repo.get_location(result.location_id)
        department = await repo.get_department(result.department_id)
        claim = (
            await session.execute(select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.device_id == device_id))
        ).scalar_one_or_none()

    assert person is not None
    assert person.display_name == "Ivan Ivanov"
    assert person.phone == "+7 000 000-00-00"
    assert person.source == "agent_profile"
    assert person.status == "self_reported"
    assert asset is not None
    assert asset.assigned_person_id is None
    assert claim is not None
    assert claim.person_id == person.person_id
    assert result.registration["claim_id"] == claim.claim_id
    assert location.building == "Building 1"
    assert location.room == "214"
    assert location.status == "pending"
    assert department.name == "Accounting"
