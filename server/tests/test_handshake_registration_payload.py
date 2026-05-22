import pytest

from websocket.agent_handshake import build_registration_payload_for_handshake


class _FakeSessionFactory:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _RegistrationServiceOk:
    def __init__(self, _session):
        pass

    async def get_device_registration_status(self, device_id: str) -> dict:
        return {
            "device_id": device_id,
            "status": "admin_confirmed",
            "active_person": {"person_id": "person-1", "display_name": "User One"},
            "active_binding": {
                "binding_id": "binding-1",
                "relationship_type": "primary_user",
                "confirmed_at": "2026-05-22T10:00:00+00:00",
            },
            "pending_claim": None,
            "requires_user_action": False,
            "requires_admin_action": False,
            "conflict_reason": None,
        }


class _RegistrationServiceFail:
    def __init__(self, _session):
        pass

    async def get_device_registration_status(self, _device_id: str) -> dict:
        raise RuntimeError("database unavailable")


@pytest.mark.asyncio
async def test_handshake_registration_payload_maps_status():
    payload = await build_registration_payload_for_handshake(
        "00000000-0000-4000-8000-000000000701",
        session_factory=_FakeSessionFactory,
        service_cls=_RegistrationServiceOk,
        db_available=True,
        db_persistence_enabled=True,
    )

    assert payload["status"] == "admin_confirmed"
    assert payload["person"] == {"person_id": "person-1", "display_name": "User One"}
    assert payload["binding"]["binding_id"] == "binding-1"
    assert payload["requires_user_action"] is False


@pytest.mark.asyncio
async def test_handshake_registration_payload_failure_falls_back_to_unknown():
    payload = await build_registration_payload_for_handshake(
        "00000000-0000-4000-8000-000000000702",
        session_factory=_FakeSessionFactory,
        service_cls=_RegistrationServiceFail,
        db_available=True,
        db_persistence_enabled=True,
    )

    assert payload == {
        "status": "unknown",
        "requires_user_action": False,
        "requires_admin_action": False,
    }
