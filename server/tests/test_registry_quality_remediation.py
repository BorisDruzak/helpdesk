from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
    RegistryAdminEvent,
    RegistryAsset,
    RegistryAudienceGroup,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryQualityIssueOverride,
    DeviceUserBinding,
    UiUser,
)
from registry.registration_service import RegistrationService


pytestmark = pytest.mark.db_cleanup("registry_access")

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
async def test_registry_quality_reports_r7_missing_production_context_gaps(test_client, test_engine):
    device_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    department_id = str(uuid.uuid4())
    binding_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(_device(device_id, hostname="quality-r7-context"))
        session.add(
            RegistryAsset(
                asset_id=asset_id,
                asset_type="pc",
                name="quality-r7-context",
                hostname="quality-r7-context",
                device_id=device_id,
                source="manual",
                status="active",
                discovery_payload={},
            )
        )
        session.add(RegistryPerson(person_id=person_id, display_name="R7 Missing Context", source="manual", status="active"))
        session.add(
            RegistryDepartment(
                department_id=department_id,
                code=f"quality_r7_pending_{uuid.uuid4().hex[:8]}",
                name="Quality R7 Pending Department",
                source="manual",
                status="pending",
            )
        )
        await session.flush()
        session.add(
            DeviceUserBinding(
                binding_id=binding_id,
                device_id=device_id,
                person_id=person_id,
                relationship_type="shared_user",
                status="active",
                source="manual",
                confidence=1,
            )
        )
        await session.commit()

    response = await test_client.get("/api/web/admin/registry", headers=ADMIN_HEADERS)
    assert response.status == 200
    issues = (await response.json())["data"]["data_quality"]

    person_department_issue = next(
        item for item in issues
        if item["kind"] == "person_missing_department" and item["object_id"] == person_id
    )
    person_location_issue = next(
        item for item in issues
        if item["kind"] == "person_missing_location" and item["object_id"] == person_id
    )
    device_owner_issue = next(
        item for item in issues
        if item["kind"] == "asset_missing_owner_or_responsible" and item["object_id"] == asset_id
    )
    department_issue = next(
        item for item in issues
        if item["kind"] == "department_pending_confirmation" and item["object_id"] == department_id
    )

    assert person_department_issue["issue_key"] == f"person_missing_department:person:{person_id}"
    assert person_location_issue["issue_key"] == f"person_missing_location:person:{person_id}"
    assert device_owner_issue["issue_key"] == f"asset_missing_owner_or_responsible:asset:{asset_id}"
    assert device_owner_issue["device_id"] == device_id
    assert department_issue["issue_key"] == f"department_pending_confirmation:department:{department_id}"


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


@pytest.mark.asyncio
async def test_registry_quality_issue_resolves_when_binding_fix_removes_root_cause(test_client, test_engine):
    device_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(_device(device_id, hostname="quality-fix-pc"))
        session.add(
            RegistryAsset(
                asset_id=asset_id,
                asset_type="pc",
                name="quality-fix-pc",
                hostname="quality-fix-pc",
                device_id=device_id,
                source="manual",
                status="active",
                discovery_payload={},
            )
        )
        session.add(RegistryPerson(person_id=person_id, display_name="Quality Fix Owner", source="manual", status="active"))
        await session.commit()

    before_response = await test_client.get("/api/web/admin/registry", headers=ADMIN_HEADERS)
    assert before_response.status == 200
    issue = next(
        item for item in (await before_response.json())["data"]["data_quality"]
        if item["kind"] == "asset_missing_confirmed_user" and item["object_id"] == asset_id
    )

    async with session_maker() as session:
        await RegistrationService(session).bind_person_to_device(
            device_id=device_id,
            person_id=person_id,
            relationship_type="primary_user",
            replace_existing=False,
            reviewed_by="admin-test",
            reason="fix quality issue",
        )
        await session.commit()

    after_response = await test_client.get("/api/web/admin/registry", headers=ADMIN_HEADERS)
    assert after_response.status == 200
    after_payload = await after_response.json()
    assert not any(item.get("issue_key") == issue["issue_key"] for item in after_payload["data"]["data_quality"])


@pytest.mark.asyncio
async def test_registry_quality_reports_empty_audience_group(test_client, test_engine):
    group_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            RegistryAudienceGroup(
                audience_group_id=group_id,
                code="phase8_empty_group",
                name="Phase 8 Empty Group",
                source="manual",
                status="active",
            )
        )
        await session.commit()

    response = await test_client.get("/api/web/admin/registry", headers=ADMIN_HEADERS)
    assert response.status == 200
    payload = await response.json()
    issue = next(
        item for item in payload["data"]["data_quality"]
        if item["kind"] == "audience_group_empty" and item["object_id"] == group_id
    )

    assert issue["issue_key"] == f"audience_group_empty:audience_group:{group_id}"
    assert issue["severity"] == "warning"
    assert issue["title"] == "Audience group has no effective members"


@pytest.mark.asyncio
async def test_registry_quality_reports_unlinked_active_ui_user(test_client, test_engine):
    user_login = f"quality-unlinked-{uuid.uuid4().hex[:8]}@example.test"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(UiUser(user_login=user_login, password_hash="hash", actor_role="user", is_active=True))
        await session.commit()

    response = await test_client.get("/api/web/admin/registry", headers=ADMIN_HEADERS)
    assert response.status == 200
    payload = await response.json()
    issue = next(
        item for item in payload["data"]["data_quality"]
        if item["kind"] == "ui_user_unlinked_registry_person" and item["object_id"] == user_login
    )

    assert issue["issue_key"] == f"ui_user_unlinked_registry_person:ui_user:{user_login}"
    assert issue["severity"] == "warning"
    assert issue["user_login"] == user_login


@pytest.mark.asyncio
async def test_registry_quality_reports_person_archived_department_and_location(test_client, test_engine):
    department_id = str(uuid.uuid4())
    location_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            RegistryDepartment(
                department_id=department_id,
                code=f"quality_archived_dept_{uuid.uuid4().hex[:8]}",
                name="Quality Archived Department",
                source="manual",
                status="archived",
            )
        )
        session.add(
            RegistryLocation(
                location_id=location_id,
                building=f"quality-{uuid.uuid4().hex[:8]}",
                floor="1",
                room="101",
                display_name="Quality Archived Location",
                source="manual",
                status="archived",
            )
        )
        session.add(
            RegistryPerson(
                person_id=person_id,
                display_name="Quality Archived Context",
                department_id=department_id,
                location_id=location_id,
                source="manual",
                status="active",
            )
        )
        await session.commit()

    response = await test_client.get("/api/web/admin/registry", headers=ADMIN_HEADERS)
    assert response.status == 200
    payload = await response.json()
    department_issue = next(
        item for item in payload["data"]["data_quality"]
        if item["kind"] == "person_archived_department" and item["object_id"] == person_id
    )
    location_issue = next(
        item for item in payload["data"]["data_quality"]
        if item["kind"] == "person_archived_location" and item["object_id"] == person_id
    )

    assert department_issue["issue_key"] == f"person_archived_department:person:{person_id}"
    assert department_issue["department_id"] == department_id
    assert location_issue["issue_key"] == f"person_archived_location:person:{person_id}"
    assert location_issue["location_id"] == location_id


@pytest.mark.asyncio
async def test_registry_quality_reports_active_binding_to_inactive_person(test_client, test_engine):
    device_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    binding_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(_device(device_id, hostname="quality-inactive-binding"))
        session.add(
            RegistryAsset(
                asset_id=asset_id,
                asset_type="pc",
                name="quality-inactive-binding",
                hostname="quality-inactive-binding",
                device_id=device_id,
                source="manual",
                status="active",
                discovery_payload={},
            )
        )
        session.add(
            RegistryPerson(
                person_id=person_id,
                display_name="Quality Inactive Person",
                source="manual",
                status="inactive",
            )
        )
        await session.flush()
        session.add(
            DeviceUserBinding(
                binding_id=binding_id,
                device_id=device_id,
                person_id=person_id,
                relationship_type="primary_user",
                status="active",
                source="manual",
                confidence=1,
            )
        )
        await session.commit()

    response = await test_client.get("/api/web/admin/registry", headers=ADMIN_HEADERS)
    assert response.status == 200
    payload = await response.json()
    issue = next(
        item for item in payload["data"]["data_quality"]
        if item["kind"] == "binding_inactive_person" and item["object_id"] == binding_id
    )

    assert issue["issue_key"] == f"binding_inactive_person:binding:{binding_id}"
    assert issue["severity"] == "danger"
    assert issue["person_id"] == person_id
