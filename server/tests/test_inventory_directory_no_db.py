import json
from uuid import UUID

import pytest

from registry import inventory_directory

pytestmark = pytest.mark.no_db


PERSON = UUID("07473193-5bd4-4b38-bbc9-7035d19c6760")
ASSET = "a48bca5e-dd70-4d76-a7d8-7601a9e5430c"
DEVICE = "e8110173-e0ba-4fb7-9ba0-0ddbbf813721"


def snapshot():
    return {
        "inventory_person_id": str(PERSON),
        "full_name": "Fixture employee",
        "department": "Fixture department",
        "profile_updated_at": "2026-11-11T10:00:00Z",
        "observed_at": "2026-11-11T10:05:00Z",
        "assignments": [{
            "inventory_asset_id": ASSET,
            "assignment_id": "37e57c8a-69aa-4f4d-b5f6-008c8bcb2dd7",
            "role": "primary", "assigned_at": "2026-11-11T10:00:00Z",
            "name": "Fixture workstation", "inventory_number": "42", "os_name": "ALT",
            "endpoint_binding_state": "confirmed",
            "endpoint_binding_id": "c35e95a5-5bfd-4cfb-82b5-4e20a6744e27",
            "endpoint_device_id": DEVICE,
            "endpoint_status": "offline", "last_seen_at": "2026-11-11T10:00:00Z",
            "agent_version": "3.2.183", "internal_raw_field": "never forward",
        }],
    }


def test_confirmed_devices_are_display_only_and_stale_cache_masks_presence():
    profile = inventory_directory.decode_snapshot(json.dumps(snapshot()).encode(), PERSON)
    fresh = inventory_directory.display_assignments(profile, stale=False)
    stale = inventory_directory.display_assignments(profile, stale=True)
    assert fresh[0]["endpoint_status"] == "offline"
    assert stale[0]["endpoint_status"] == "unknown"
    assert stale[0]["endpoint_device_id"] == DEVICE
    assert fresh[0]["inventory_asset_id"] == ASSET
    assert "internal_raw_field" not in fresh[0]
    assert "diagnostics_allowed" not in fresh[0]


@pytest.mark.parametrize("corrupt", ["other-person", "unconfirmed-uuid", "duplicated-asset", "naive-timestamp"])
def test_provider_payload_inconsistency_rejects_whole_snapshot(corrupt):
    payload = snapshot()
    if corrupt == "other-person":
        payload["inventory_person_id"] = ASSET
    elif corrupt == "unconfirmed-uuid":
        payload["assignments"][0]["endpoint_binding_state"] = "review"
    elif corrupt == "duplicated-asset":
        payload["assignments"].append(dict(payload["assignments"][0]))
    else:
        payload["observed_at"] = "2026-11-11T10:05:00"
    with pytest.raises(inventory_directory.InventoryUnavailable):
        inventory_directory.decode_snapshot(json.dumps(payload).encode(), PERSON)


@pytest.mark.asyncio
async def test_insecure_provider_origin_is_rejected_before_connecting(monkeypatch):
    monkeypatch.setenv("HELPDESK_INVENTORY_BASE_URL", "http://localhost")
    with pytest.raises(inventory_directory.InventoryUnavailable):
        await inventory_directory.fetch_person(PERSON)


@pytest.mark.parametrize("raw,exception", [
    (b'{"detail":"Not Found"}', inventory_directory.InventoryUnavailable),
    (b'{"detail":{"code":"inventory_person_not_found"}}', inventory_directory.InventoryPersonMissing),
])
def test_only_the_provider_not_found_marker_is_authoritative(raw, exception):
    with pytest.raises(exception) as error:
        inventory_directory.decode_response(404, raw, PERSON)
    assert type(error.value) is exception
