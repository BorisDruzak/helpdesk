from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, RegistryAdminEvent, RegistryPerson
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.registration_service import RegistrationService

pytestmark = pytest.mark.db_cleanup("registry_access")

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
    assert payload["data"]["defaults"]["registration"]["require_admin_confirmation"] is False
    assert payload["data"]["defaults"]["registration"]["auto_approve_first_binding"] is True
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
        json={"policies": {"registration": {"require_admin_confirmation": True, "auto_approve_first_binding": False}}},
        headers=ADMIN_HEADERS,
    )
    assert preview.status == 200
    preview_payload = await preview.json()
    assert preview_payload["data"]["dry_run"] is True
    assert preview_payload["data"]["warnings"] == []
    assert preview_payload["data"]["changed_from_defaults"]["registration.require_admin_confirmation"] == {
        "default": False,
        "effective": True,
    }

    saved = await test_client.patch(
        "/api/web/admin/registry/policies",
        json={
            "reason": "enable manual approval policy",
            "policies": {"registration": {"require_admin_confirmation": True, "auto_approve_first_binding": False}},
        },
        headers=ADMIN_HEADERS,
    )
    assert saved.status == 200
    saved_payload = await saved.json()
    assert saved_payload["data"]["effective"]["registration"]["require_admin_confirmation"] is True
    assert saved_payload["data"]["effective"]["registration"]["auto_approve_first_binding"] is False
    assert "warnings" not in saved_payload["data"]["effective"]

    reset = await test_client.post(
        "/api/web/admin/registry/policies/reset",
        json={"reason": "back to production-safe defaults"},
        headers=ADMIN_HEADERS,
    )
    assert reset.status == 200
    reset_payload = await reset.json()
    assert reset_payload["data"]["effective"]["registration"]["require_admin_confirmation"] is False
    assert reset_payload["data"]["effective"]["registration"]["auto_approve_first_binding"] is True
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
    assert all(event for event in events)
