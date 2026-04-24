from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device
from registry.service import RegistryIngestionService
from tests.conftest import TEST_UI_ADMIN_TOKEN


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


@pytest.mark.asyncio
async def test_web_admin_registry_returns_snapshot_for_reestr_ui(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add(
            Device(
                device_id="device-registry-api",
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
            device_id="device-registry-api",
            hostname="DOC-214-02",
            os_name="Windows 11",
            agent_version="1.2.0",
            metadata={},
        )
        await service.ingest_requester_profile(
            device_id="device-registry-api",
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
    assert data["assets"][0]["device_id"] == "device-registry-api"
    assert data["assets"][0]["assigned_person_display_name"] == "Петрова Анна"
    assert data["locations"][0]["building"] == "Здание 2"
    assert data["people"][0]["department_name"] == "Документооборот"


@pytest.mark.asyncio
async def test_registry_profile_endpoint_syncs_agent_profile(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add(
            Device(
                device_id="device-profile-api",
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
            "device_id": "device-profile-api",
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
    assert payload["data"]["asset"]["device_id"] == "device-profile-api"
