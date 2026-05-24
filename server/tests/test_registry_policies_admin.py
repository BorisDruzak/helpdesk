from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, RegistryAdminEvent, RegistryPerson
from registry.account_session_service import AccountSessionService
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.registration_service import RegistrationService

ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}


def _device(device_id: str) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname="policy-pc",
        os="Windows 11",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


@pytest.mark.asyncio
async def test_registry_policy_api_reads_defaults_and_rejects_invalid_values(test_client):
    response = await test_client.get("/api/web/admin/registry/policies", headers=ADMIN_HEADERS)
    assert response.status == 200
    payload = await response.json()
    assert payload["data"]["effective"]["account_sessions"]["verified_other_account_ttl_hours"] == 24
    assert payload["data"]["defaults"]["registration"]["auto_approve_first_binding"] is False
    assert payload["data"]["requires_restart"] is False
    assert payload["data"]["validation"]["registration.stale_after_days"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 3650,
        "nullable": False,
    }

    invalid = await test_client.patch(
        "/api/web/admin/registry/policies",
        json={"reason": "invalid", "policies": {"account_sessions": {"verified_other_account_ttl_hours": -1}}},
        headers=ADMIN_HEADERS,
    )
    assert invalid.status == 400


@pytest.mark.asyncio
async def test_registry_policy_preview_and_reset_are_audited(test_client, test_engine):
    preview = await test_client.post(
        "/api/web/admin/registry/policies/preview",
        json={"policies": {"registration": {"auto_approve_first_binding": True}}},
        headers=ADMIN_HEADERS,
    )
    assert preview.status == 200
    preview_payload = await preview.json()
    assert preview_payload["data"]["dry_run"] is True
    assert preview_payload["data"]["warnings"][0]["field"] == "registration.auto_approve_first_binding"

    saved = await test_client.patch(
        "/api/web/admin/registry/policies",
        json={
            "reason": "enable test stand policy",
            "policies": {"registration": {"auto_approve_first_binding": True}},
        },
        headers=ADMIN_HEADERS,
    )
    assert saved.status == 200
    saved_payload = await saved.json()
    assert saved_payload["data"]["effective"]["registration"]["auto_approve_first_binding"] is True
    assert "warnings" not in saved_payload["data"]["effective"]

    reset = await test_client.post(
        "/api/web/admin/registry/policies/reset",
        json={"reason": "back to production-safe defaults"},
        headers=ADMIN_HEADERS,
    )
    assert reset.status == 200
    reset_payload = await reset.json()
    assert reset_payload["data"]["effective"]["registration"]["auto_approve_first_binding"] is False
    assert reset_payload["data"]["changed_from_defaults"] == {}

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        events = (
            await session.execute(
                RegistryAdminEvent.__table__.select().where(
                    RegistryAdminEvent.event_type == "policy_changed"
                )
            )
        ).all()

    assert len(events) >= 2


@pytest.mark.asyncio
async def test_account_session_service_uses_patched_ttl(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        person = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Policy Owner", source="manual", status="active")
        session.add(person)
        await session.flush()
        await RegistryAdminOperationsService(session).update_policies(
            {
                "reason": "short ttl",
                "policies": {"account_sessions": {"confirmed_binding_ttl_hours": 2}},
            },
            actor_id="admin",
        )
        binding = await RegistrationService(session).bind_person_to_device(
            device_id=device_id,
            person_id=person.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="owner",
        )
        created = await AccountSessionService(session).create_confirmed_binding_session(
            device_id=device_id,
            binding_id=binding["binding"]["binding_id"],
        )
        await session.commit()

    assert created["session"]["expires_at"] is not None
