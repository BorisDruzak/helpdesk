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
    assert state["show_login_other"] is True


def test_account_gate_unregistered_fallback_shows_registration_and_other_login():
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
    assert state["show_login_other"] is True


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


def test_account_gate_other_account_warning():
    state = account_gate_view_state(
        {"accounts": [], "registration": {"status": "admin_confirmed"}},
        local_session={"account_mode": "other_account", "created_from_other_account": True},
    )

    assert state["warning"] == "other_account"
