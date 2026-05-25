from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, RegistryAdminEvent, RegistryAsset, RegistryQualityIssueOverride


ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}


def _device(device_id: str, *, hostname: str = "quality-pc") -> Device:
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


@pytest.mark.asyncio
async def test_registry_quality_issue_ignore_hides_issue_and_writes_audit(test_client, test_engine):
    device_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(_device(device_id))
        session.add(
            RegistryAsset(
                asset_id=asset_id,
                asset_type="pc",
                name="quality-pc",
                hostname="quality-pc",
                device_id=device_id,
                source="manual",
                status="active",
                discovery_payload={},
            )
        )
        await session.commit()

    before_response = await test_client.get("/api/web/admin/registry", headers=ADMIN_HEADERS)
    assert before_response.status == 200
    before_payload = await before_response.json()
    issue = next(
        item for item in before_payload["data"]["data_quality"]
        if item["kind"] == "asset_missing_confirmed_user" and item["object_id"] == asset_id
    )
    assert issue["issue_key"] == f"asset_missing_confirmed_user:asset:{asset_id}"

    ignore_response = await test_client.post(
        f"/api/web/admin/registry/quality/{issue['issue_key']}/ignore",
        json={"reason": "accepted lab workstation"},
        headers=ADMIN_HEADERS,
    )
    assert ignore_response.status == 200
    ignore_payload = await ignore_response.json()
    assert ignore_payload["data"]["override"]["status"] == "ignored"

    after_response = await test_client.get("/api/web/admin/registry", headers=ADMIN_HEADERS)
    assert after_response.status == 200
    after_payload = await after_response.json()
    assert not any(item.get("issue_key") == issue["issue_key"] for item in after_payload["data"]["data_quality"])

    async with session_maker() as session:
        override = await session.get(RegistryQualityIssueOverride, issue["issue_key"])
        event = (
            await session.execute(
                select(RegistryAdminEvent).where(
                    RegistryAdminEvent.event_type == "quality_issue_ignored",
                    RegistryAdminEvent.object_id == issue["issue_key"],
                )
            )
        ).scalar_one()

    assert override.status == "ignored"
    assert override.reason == "accepted lab workstation"
    assert event.reason == "accepted lab workstation"
    assert event.payload["issue_kind"] == "asset_missing_confirmed_user"


@pytest.mark.asyncio
async def test_registry_quality_issue_snooze_hides_until_future_date(test_client, test_engine):
    device_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(_device(device_id, hostname="quality-snooze-pc"))
        session.add(
            RegistryAsset(
                asset_id=asset_id,
                asset_type="pc",
                name="quality-snooze-pc",
                hostname="quality-snooze-pc",
                device_id=device_id,
                source="manual",
                status="active",
                discovery_payload={},
            )
        )
        await session.commit()

    before_response = await test_client.get("/api/web/admin/registry", headers=ADMIN_HEADERS)
    issue = next(
        item for item in (await before_response.json())["data"]["data_quality"]
        if item["kind"] == "asset_missing_confirmed_user" and item["object_id"] == asset_id
    )

    snooze_response = await test_client.post(
        f"/api/web/admin/registry/quality/{issue['issue_key']}/snooze",
        json={"reason": "waiting for owner", "days": 7},
        headers=ADMIN_HEADERS,
    )
    assert snooze_response.status == 200
    snooze_payload = await snooze_response.json()
    assert snooze_payload["data"]["override"]["status"] == "snoozed"
    assert snooze_payload["data"]["override"]["snoozed_until"]

    after_response = await test_client.get("/api/web/admin/registry", headers=ADMIN_HEADERS)
    after_payload = await after_response.json()
    assert not any(item.get("issue_key") == issue["issue_key"] for item in after_payload["data"]["data_quality"])
