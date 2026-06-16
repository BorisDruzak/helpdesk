from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from pc_agent.ui_gui.account_gate import AccountGateWidget, account_gate_view_state
from pc_agent.ui_gui.main_window import MainWindow


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
    assert state["show_browser_login"] is True
    assert state["show_gui_password_login"] is True
    assert state["show_register"] is False
    assert state["show_login_other"] is True


def test_account_gate_widget_emits_gui_password_login_and_clears_password():
    app = QApplication.instance() or QApplication([])
    widget = AccountGateWidget()
    events: list[tuple[str, str]] = []
    widget.guiPasswordLoginRequested.connect(lambda login, password: events.append((login, password)))

    widget.render(
        {
            "accounts": [
                {
                    "account_mode": "confirmed_binding",
                    "display_name": "Registered User",
                    "binding_id": "binding-1",
                    "can_login": True,
                }
            ],
            "registration": {"status": "admin_confirmed"},
        }
    )
    widget.show()
    app.processEvents()

    assert widget.gui_login_frame.isVisible()
    widget.gui_login_input.setText("owner@example.test")
    widget.gui_password_input.setText("RawPasswordMustNotPersist123!")
    widget.gui_password_login_button.click()

    assert events == [("owner@example.test", "RawPasswordMustNotPersist123!")]
    assert widget.gui_password_input.text() == ""


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


def test_account_gate_no_binding_state_uses_browser_registration_only_by_default():
    state = account_gate_view_state(
        {
            "accounts": [],
            "can_register": True,
            "can_login_other_account": False,
            "registration": {"status": "unregistered"},
        }
    )

    assert state["mode"] == "unregistered"
    assert state["show_register"] is False
    assert state["show_browser_register"] is True
    assert state["show_login_other"] is False


def test_account_gate_legacy_registration_flag_does_not_expose_local_registration():
    state = account_gate_view_state(
        {
            "accounts": [],
            "can_register": True,
            "can_login_other_account": False,
            "registration": {"status": "unregistered"},
        },
        legacy_registration_enabled=True,
    )

    assert state["mode"] == "unregistered"
    assert state["show_register"] is False
    assert state["show_browser_register"] is True


def test_account_gate_browser_pairing_code_can_be_copied():
    state = account_gate_view_state(
        {
            "accounts": [],
            "can_register": True,
            "can_login_other_account": False,
            "registration": {"status": "unregistered"},
            "browser_pairing_code": "ABCD-1234",
        }
    )

    assert state["browser_pairing_code"] == "ABCD-1234"
    assert state["show_copy_pairing_code"] is True


def test_account_gate_unregistered_fallback_shows_browser_registration_only():
    state = account_gate_view_state(
        {
            "accounts": [],
            "can_register": False,
            "can_login_other_account": False,
            "registration": {"status": "unregistered"},
        }
    )

    assert state["mode"] == "unregistered"
    assert state["show_register"] is False
    assert state["show_browser_register"] is True
    assert state["show_login_other"] is False


def test_account_gate_unknown_state_does_not_offer_account_actions():
    state = account_gate_view_state({})

    assert state["mode"] == "unregistered"
    assert state["show_register"] is False
    assert state["show_login_other"] is False


def test_account_gate_pending_state_hides_legacy_confirm_by_default():
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
    assert state["show_register"] is False
    assert state["show_confirm"] is False
    assert state["show_login_other"] is False


def test_account_gate_pending_state_never_shows_local_confirm_action():
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
        },
        legacy_registration_enabled=True,
    )

    assert state["mode"] == "pending"
    assert state["show_confirm"] is False


def test_account_gate_widget_has_no_local_registration_controls():
    source = inspect.getsource(AccountGateWidget)

    assert "registerRequested" not in source
    assert "confirmRegistrationRequested" not in source
    assert "self.register_button" not in source
    assert "self.confirm_button" not in source


def test_main_window_does_not_treat_registration_pending_as_ticket_login():
    window = MainWindow.__new__(MainWindow)
    window._account_session = {"account_mode": "registration_pending", "account_session_id": "pending-session"}

    assert window._active_account_session_for_tickets() is None


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


def test_account_gate_terminal_pending_other_account_request_falls_back_to_account_state():
    state = account_gate_view_state(
        {
            "accounts": [
                {
                    "account_mode": "confirmed_binding",
                    "binding_id": "binding-1",
                    "display_name": "Registered Owner",
                    "can_login": True,
                }
            ],
            "registration": {"status": "admin_confirmed"},
            "can_request_other_account_login": True,
        },
        local_session={
            "account_mode": "pending_other_account_request",
            "pending_login_request_id": "request-1",
            "pending_login_request_status": "canceled",
            "display_name": "Guest User",
        },
    )

    assert state["mode"] == "registered"
    assert state["show_check_pending_request"] is False
    assert state["primary_account"]["display_name"] == "Registered Owner"


def test_main_window_builds_absolute_browser_pairing_url():
    window = MainWindow.__new__(MainWindow)
    window.chat_panel = SimpleNamespace(ticket_client=SimpleNamespace(base_url="https://example.test/api"))

    assert (
        window._browser_pairing_url("/app/device/login?pairing_id=pair-1")
        == "https://example.test/app/device/login?pairing_id=pair-1"
    )
    assert (
        window._browser_pairing_url("https://helpdesk.example/app/device/login?pairing_id=pair-1")
        == "https://helpdesk.example/app/device/login?pairing_id=pair-1"
    )


def test_main_window_browser_pairing_url_uses_https_stand_origin_for_legacy_api_url():
    window = MainWindow.__new__(MainWindow)
    window.chat_panel = SimpleNamespace(ticket_client=SimpleNamespace(base_url="http://192.168.100.17:8666/api"))

    assert (
        window._browser_pairing_url("/app/device/login?pairing_id=pair-1")
        == "https://192.168.100.17:9443/app/device/login?pairing_id=pair-1"
    )


@pytest.mark.asyncio
async def test_main_window_browser_login_pairing_polls_and_saves_session(monkeypatch):
    opened_urls: list[str] = []
    selected_views: list[str] = []
    rendered: list[dict] = []
    saved_sessions: list[dict] = []

    class FakeClient:
        base_url = "https://example.test/api"
        device_id = "device-1"

        async def create_browser_pairing(self, purpose: str) -> dict:
            assert purpose == "login"
            return {"pairing_id": "pair-1", "browser_url": "/app/device/login?pairing_id=pair-1"}

        async def get_browser_pairing(self, pairing_id: str) -> dict:
            assert pairing_id == "pair-1"
            return {
                "status": "consumed",
                "session_token": "secret-token",
                "session": {
                    "session_id": "session-1",
                    "account_mode": "confirmed_binding",
                    "binding_id": "binding-1",
                    "display_name": "Registered User",
                },
            }

    class FakeSessionManager:
        def build_confirmed_binding_session(self, account: dict, *, device_id: str) -> dict:
            return {**account, "device_id": device_id, "account_mode": "confirmed_binding"}

        def save(self, session: dict) -> dict:
            saved_sessions.append(session)
            return session

    window = MainWindow.__new__(MainWindow)
    window.chat_panel = SimpleNamespace(ticket_client=FakeClient(), device_id="device-1")
    window.account_gate_page = SimpleNamespace(render=lambda state, **kwargs: rendered.append({"state": state, **kwargs}))
    window._account_session_manager = FakeSessionManager()
    window._account_session = {"account_mode": "none"}
    window._account_state = {}
    window._set_account_entry_mode = lambda value: None
    window._render_profile_status = lambda: None
    window._select_sidebar_view = lambda view, **kwargs: selected_views.append(view)
    window._browser_pairing_open_url = lambda url: opened_urls.append(url)

    await window._async_browser_pairing("login", poll_interval_seconds=0.0, max_polls=1)

    assert opened_urls == ["https://example.test/app/device/login?pairing_id=pair-1"]
    assert saved_sessions[0]["session_token"] == "secret-token"
    assert saved_sessions[0]["account_mode"] == "confirmed_binding"
    assert selected_views == ["tickets"]


@pytest.mark.asyncio
async def test_main_window_gui_password_login_saves_session_without_password():
    selected_views: list[str] = []
    rendered: list[dict] = []
    saved_sessions: list[dict] = []

    class FakeClient:
        async def create_gui_password_account_session(self, login: str, password: str) -> dict:
            assert login == "owner@example.test"
            assert password == "RawPasswordMustNotPersist123!"
            return {
                "session_token": "secret-token",
                "session": {
                    "session_id": "session-1",
                    "account_mode": "confirmed_binding",
                    "binding_id": "binding-1",
                    "display_name": "Registered User",
                    "verification_method": "gui_password",
                },
            }

    class FakeSessionManager:
        def build_confirmed_binding_session(self, account: dict, *, device_id: str) -> dict:
            assert account["session_token"] == "secret-token"
            assert "password" not in account
            return {**account, "device_id": device_id, "account_mode": "confirmed_binding"}

        def save(self, session: dict) -> dict:
            saved_sessions.append(session)
            return session

    window = MainWindow.__new__(MainWindow)
    window.chat_panel = SimpleNamespace(ticket_client=FakeClient(), device_id="device-1")
    window.account_gate_page = SimpleNamespace(render=lambda state, **kwargs: rendered.append({"state": state, **kwargs}))
    window._account_session_manager = FakeSessionManager()
    window._account_session = {"account_mode": "none"}
    window._account_state = {}
    window._set_account_entry_mode = lambda value: None
    window._render_profile_status = lambda: None
    window._select_sidebar_view = lambda view, **kwargs: selected_views.append(view)

    await window._async_gui_password_login("owner@example.test", "RawPasswordMustNotPersist123!")

    assert saved_sessions[0]["session_token"] == "secret-token"
    assert saved_sessions[0]["verification_method"] == "gui_password"
    assert "password" not in saved_sessions[0]
    assert selected_views == ["tickets"]


@pytest.mark.asyncio
async def test_main_window_gui_password_login_error_keeps_gate_actions_available():
    rendered: list[dict] = []

    class FakeClient:
        async def create_gui_password_account_session(self, login: str, password: str) -> dict:
            return {
                "status": "error",
                "error_code": "ACCOUNT_SESSION_DEVICE_MISMATCH",
                "error": "Этот аккаунт не привязан к текущему агенту.",
            }

    window = MainWindow.__new__(MainWindow)
    window.chat_panel = SimpleNamespace(ticket_client=FakeClient(), device_id="device-1")
    window.account_gate_page = SimpleNamespace(render=lambda state, **kwargs: rendered.append({"state": state, **kwargs}))
    window._account_session = {"account_mode": "none"}
    window._account_state = {
        "accounts": [
            {
                "account_mode": "confirmed_binding",
                "display_name": "Registered User",
                "binding_id": "binding-1",
                "can_login": True,
            }
        ],
        "registration": {"status": "admin_confirmed"},
        "can_request_other_account_login": True,
    }

    await window._async_gui_password_login("other@example.test", "RawPasswordMustNotPersist123!")

    state = account_gate_view_state(rendered[0]["state"], local_session=rendered[0]["local_session"])
    assert "error" not in rendered[0]
    assert "не привязан" in state["message"]
    assert state["show_gui_password_login"] is True
    assert state["show_browser_login"] is True
    assert state["show_login_other"] is True


@pytest.mark.asyncio
async def test_main_window_browser_registration_pairing_refreshes_account_state():
    rendered: list[dict] = []

    class FakeClient:
        base_url = "https://example.test/api"
        device_id = "device-1"

        async def create_browser_pairing(self, purpose: str) -> dict:
            assert purpose == "registration"
            return {
                "pairing_id": "pair-2",
                "pairing_code": "ABCD-1234",
                "browser_url": "/app/device/register?pairing_id=pair-2",
            }

        async def get_browser_pairing(self, pairing_id: str) -> dict:
            assert pairing_id == "pair-2"
            return {"status": "consumed", "claim_id": "claim-1"}

        async def get_account_state(self) -> dict:
            return {"accounts": [], "registration": {"status": "pending_user_confirmation"}}

    window = MainWindow.__new__(MainWindow)
    window.chat_panel = SimpleNamespace(ticket_client=FakeClient(), device_id="device-1")
    window.account_gate_page = SimpleNamespace(render=lambda state, **kwargs: rendered.append({"state": state, **kwargs}))
    window._account_session = {"account_mode": "none"}
    window._account_state = {}
    window._browser_pairing_open_url = lambda url: None

    await window._async_browser_pairing("registration", poll_interval_seconds=0.0, max_polls=1)

    assert any(item["state"].get("browser_pairing_code") == "ABCD-1234" for item in rendered)
    assert rendered[-1]["state"]["registration"]["status"] == "pending_user_confirmation"


@pytest.mark.asyncio
async def test_main_window_refresh_clears_revoked_session_and_returns_to_account_gate():
    rendered: list[dict] = []
    selected_views: list[str] = []
    cleared: list[bool] = []
    profile_refreshes: list[bool] = []

    class FakeClient:
        async def get_account_state(self) -> dict:
            return {
                "accounts": [],
                "registration": {"status": "unregistered"},
                "can_register": True,
            }

        async def validate_account_session(self, session_id: str, session_token: str | None = None) -> dict:
            assert session_id == "session-1"
            assert session_token == "token-1"
            raise RuntimeError("HTTP 403 ACCOUNT_SESSION_REVOKED")

    class FakeSessionManager:
        def clear(self) -> None:
            cleared.append(True)

        def enrich_from_account_state(self, session: dict, state: dict) -> dict:
            raise AssertionError("revoked session must not be enriched")

    window = MainWindow.__new__(MainWindow)
    window.chat_panel = SimpleNamespace(
        ticket_client=FakeClient(),
        tickets_cache=["T-1"],
        active_ticket_id="T-1",
        _ticket_detail_timer=SimpleNamespace(stop=lambda: None),
        _reset_active_ticket_cache=lambda: None,
        _update_tickets_list_ui=lambda: None,
    )
    window.account_gate_page = SimpleNamespace(render=lambda state, **kwargs: rendered.append({"state": state, **kwargs}))
    window._account_session_manager = FakeSessionManager()
    window._account_session = {
        "account_mode": "confirmed_binding",
        "account_session_id": "session-1",
        "session_token": "token-1",
        "binding_id": "binding-1",
    }
    window._account_state = {}
    window._active_sidebar_view = "tickets"
    window._render_profile_status = lambda: profile_refreshes.append(True)
    window._select_sidebar_view = lambda view, **kwargs: selected_views.append(view)

    await window._async_refresh_account_state()

    assert cleared == [True]
    assert window._account_session["account_mode"] == "none"
    assert window.chat_panel.tickets_cache == []
    assert window.chat_panel.active_ticket_id is None
    assert rendered[-1]["state"]["registration"]["status"] == "unregistered"
    assert rendered[-1]["local_session"]["account_mode"] == "none"
    assert rendered[-1]["error"]
    assert selected_views == ["account_gate"]
    assert profile_refreshes == [True]
