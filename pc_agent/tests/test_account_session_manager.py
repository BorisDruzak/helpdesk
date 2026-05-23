from __future__ import annotations

from pc_agent.core.account_session import AccountSessionManager


def test_account_session_manager_save_load_clear(tmp_path):
    manager = AccountSessionManager(data_root=tmp_path)

    saved = manager.save(
        {
            "account_mode": "confirmed_binding",
            "device_id": "device-1",
            "person_id": "person-1",
            "binding_id": "binding-1",
            "display_name": "  Alice   User  ",
            "email": "Alice@Example.Test",
            "unsafe": "ignored",
        }
    )

    assert saved["display_name"] == "Alice User"
    assert saved["email"] == "alice@example.test"
    assert saved["account_mode"] == "confirmed_binding"
    assert "unsafe" not in saved
    assert manager.is_logged_in()
    assert manager.load()["binding_id"] == "binding-1"

    manager.clear()
    assert not manager.is_logged_in()


def test_confirmed_binding_session_shape(tmp_path):
    manager = AccountSessionManager(data_root=tmp_path)

    session = manager.build_confirmed_binding_session(
        {
            "person_id": "person-1",
            "binding_id": "binding-1",
            "display_name": "Alice",
            "full_name": "Alice User",
            "login": "DOMAIN\\Alice",
            "email": "alice@example.test",
            "registration_status": "admin_confirmed",
        },
        device_id="device-1",
    )

    assert session["account_mode"] == "confirmed_binding"
    assert session["device_id"] == "device-1"
    assert session["person_id"] == "person-1"
    assert session["binding_id"] == "binding-1"
    assert session["registration_status"] == "admin_confirmed"
    assert session["other_account"] is False


def test_registration_pending_session_shape(tmp_path):
    manager = AccountSessionManager(data_root=tmp_path)

    session = manager.build_registration_pending_session(
        {"full_name": "Pending User", "login": "pending"},
        {"claim_id": "claim-1", "status": "pending_admin_review"},
        device_id="device-1",
    )

    assert session["account_mode"] == "registration_pending"
    assert session["registration_status"] == "pending_admin_review"
    assert session["metadata"]["claim_id"] == "claim-1"
    assert session["display_name"] == "Pending User"


def test_other_account_session_preserves_base_binding(tmp_path):
    manager = AccountSessionManager(data_root=tmp_path)

    session = manager.build_other_account_session(
        {"full_name": "Other User", "login": "other", "email": "other@example.test"},
        {
            "binding_id": "binding-registered",
            "person_id": "person-registered",
            "display_name": "Registered User",
        },
        device_id="device-1",
    )

    assert session["account_mode"] == "other_account"
    assert session["created_from_other_account"] is True
    assert session["other_account"] is True
    assert session["base_binding_id"] == "binding-registered"
    assert session["base_person_id"] == "person-registered"
    assert session["base_display_name"] == "Registered User"
