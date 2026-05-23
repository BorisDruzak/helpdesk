from __future__ import annotations

from pc_agent.ui_gui.account_gate import account_gate_view_state


def test_account_gate_registered_state_hides_registration():
    state = account_gate_view_state(
        {
            "accounts": [
                {
                    "account_mode": "confirmed_binding",
                    "display_name": "Registered User",
                    "binding_id": "binding-1",
                    "is_primary": True,
                }
            ],
            "can_register": False,
            "can_login_other_account": True,
            "registration": {"status": "admin_confirmed"},
        }
    )

    assert state["mode"] == "registered"
    assert state["primary_account"]["display_name"] == "Registered User"
    assert state["show_login_confirmed"] is True
    assert state["show_register"] is False
    assert state["show_login_other"] is True


def test_account_gate_approved_other_account_can_be_selected():
    state = account_gate_view_state(
        {
            "accounts": [
                {
                    "account_mode": "confirmed_binding",
                    "display_name": "Registered User",
                    "binding_id": "binding-1",
                    "can_login": True,
                },
                {
                    "account_mode": "verified_other_account",
                    "display_name": "Approved Guest",
                    "session_id": "session-1",
                    "can_login": True,
                },
            ],
            "can_register": False,
            "can_request_other_account_login": True,
            "registration": {"status": "admin_confirmed"},
        }
    )

    assert state["mode"] == "registered"
    assert state["show_login_other"] is True
    assert state["approved_other_account"]["display_name"] == "Approved Guest"


def test_account_gate_no_binding_state_shows_registration():
    state = account_gate_view_state(
        {
            "accounts": [],
            "can_register": True,
            "can_login_other_account": False,
            "registration": {"status": "unregistered"},
        }
    )

    assert state["mode"] == "unregistered"
    assert state["show_register"] is True
    assert state["show_login_other"] is False


def test_account_gate_unregistered_fallback_shows_registration_only():
    state = account_gate_view_state(
        {
            "accounts": [],
            "can_register": False,
            "can_login_other_account": False,
            "registration": {"status": "unregistered"},
        }
    )

    assert state["mode"] == "unregistered"
    assert state["show_register"] is True
    assert state["show_login_other"] is False


def test_account_gate_unknown_state_does_not_offer_account_actions():
    state = account_gate_view_state({})

    assert state["mode"] == "unregistered"
    assert state["show_register"] is False
    assert state["show_login_other"] is False


def test_account_gate_pending_state_shows_continue_registration():
    state = account_gate_view_state(
        {
            "accounts": [
                {
                    "account_mode": "registration_pending",
                    "display_name": "Pending User",
                    "registration_status": "pending_user_confirmation",
                }
            ],
            "can_register": True,
            "can_login_other_account": False,
            "registration": {"status": "self_reported"},
        }
    )

    assert state["mode"] == "pending"
    assert state["show_register"] is True
    assert state["show_confirm"] is True
    assert state["show_login_other"] is False


def test_account_gate_other_account_warning():
    state = account_gate_view_state(
        {"accounts": [], "registration": {"status": "admin_confirmed"}},
        local_session={"account_mode": "other_account", "created_from_other_account": True},
    )

    assert state["warning"] == "other_account"


def test_account_gate_pending_other_account_request_state():
    state = account_gate_view_state(
        {"accounts": [], "registration": {"status": "admin_confirmed"}},
        local_session={
            "account_mode": "pending_other_account_request",
            "pending_login_request_id": "request-1",
            "display_name": "Guest User",
            "login": "guest",
            "reason": "Shift replacement",
        },
    )

    assert state["mode"] == "pending_other_account_request"
    assert state["show_login_other"] is False
    assert state["show_check_pending_request"] is True
    assert state["pending_request_id"] == "request-1"
    assert state["pending_account"]["display_name"] == "Guest User"
