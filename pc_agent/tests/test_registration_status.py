from __future__ import annotations

from pc_agent.core.user_profile import UserProfileManager


def apply_registration_status_for_test(manager: UserProfileManager, payload: dict) -> dict:
    profile = manager.load()
    registration = payload.get("registration")
    if isinstance(registration, dict):
        profile["registration_status"] = str(registration.get("status") or "unknown")
        if registration.get("pending_claim_id"):
            profile["last_claim_id"] = str(registration.get("pending_claim_id"))
    return manager.save(profile)


def test_handshake_registration_payload_updates_local_profile_status(tmp_path):
    manager = UserProfileManager(data_root=tmp_path)

    profile = apply_registration_status_for_test(
        manager,
        {"registration": {"status": "pending_admin_review", "pending_claim_id": "claim-1"}},
    )

    assert profile["registration_status"] == "pending_admin_review"
    assert profile["last_claim_id"] == "claim-1"
    assert manager.load()["registration_status"] == "pending_admin_review"
