from __future__ import annotations

import json

import pytest

from pc_agent.ui_gui.automation_controller import GuiAutomationController


pytestmark = pytest.mark.no_db


class _Timer:
    def interval(self) -> int:
        return 100

    def start(self, _interval: int) -> None:
        pass


class _Stack:
    def currentWidget(self):
        return None


class _TicketClient:
    def __init__(self, response: dict):
        self.response = response
        self.calls: list[dict] = []

    async def create_ticket(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _ChatPanel:
    def __init__(self, *, account_session: dict | None, response: dict | None = None):
        self.account_session = account_session
        self.ticket_client = _TicketClient(
            response
            or {
                "status": "ok",
                "ticket": {"ticket_id": "ticket-1"},
                "public_access_code": "CODE-1",
                "public_access_url": "https://example.test/ticket-1",
            }
        )
        self.active_ticket_id = None
        self.tickets_cache = []
        self._profiles_data = {"active_profile_id": "profile-1", "profiles": [{"id": "profile-1"}]}
        self._ticket_detail_timer = _Timer()
        self._last_timeline_html = None
        self._last_detail_header_sig = None
        self._pending_ticket_snapshot = None

    def has_active_profile(self) -> bool:
        return True

    def _profiles(self) -> list[dict]:
        return list(self._profiles_data["profiles"])

    async def _async_refresh_ticket_form_pack(self, *, force: bool = True) -> None:
        pass

    def ticket_form_pack(self) -> dict:
        return {}

    def _current_requester_payload(self) -> tuple[dict, str]:
        return {"display_name": "Requester"}, "Requester"

    def _current_account_session(self) -> dict | None:
        return self.account_session

    async def _async_send_created_ticket_attachments(self, *_args, **_kwargs) -> None:
        pass

    def _reset_active_ticket_cache(self) -> None:
        pass

    async def _async_refresh_ticket_list(self) -> None:
        pass

    async def _async_refresh_ticket_detail(self) -> None:
        pass

    def _show_chat_screen(self) -> None:
        pass

    def _ensure_timeline_bottom_follow(self) -> None:
        pass


class _Window:
    def __init__(self, chat_panel: _ChatPanel):
        self.chat_panel = chat_panel
        self.main_content_stack = _Stack()
        self.tickets_sidebar = object()
        self.profile_sidebar = object()
        self.settings_page = object()
        self.selected_views: list[str] = []

    def isVisible(self) -> bool:
        return True

    def isMinimized(self) -> bool:
        return False

    def isActiveWindow(self) -> bool:
        return True

    def _select_sidebar_view(self, view_name: str, *, expand: bool = True) -> None:
        self.selected_views.append(view_name)


@pytest.mark.asyncio
async def test_automation_create_ticket_sends_active_account_session():
    account_session = {"account_session_id": "session-1", "session_token": "token-1"}
    chat_panel = _ChatPanel(account_session=account_session)
    controller = GuiAutomationController(_Window(chat_panel))

    result = await controller._create_ticket(
        {"title": "Live regression", "description": "Created through automation"},
        trace_parent_action_id="action-1",
    )

    assert result["status"] == "ok"
    assert result["ticket_id"] == "ticket-1"
    call = chat_panel.ticket_client.calls[0]
    assert call["requester_account"] == account_session
    assert call["trace_parent_action_id"] == "action-1"


@pytest.mark.asyncio
async def test_automation_create_ticket_without_account_still_returns_server_denial():
    chat_panel = _ChatPanel(
        account_session=None,
        response={
            "status": "error",
            "error_code": "ACCOUNT_SESSION_REQUIRED",
            "error": "account_session_invalid",
        },
    )
    controller = GuiAutomationController(_Window(chat_panel))

    with pytest.raises(RuntimeError) as exc_info:
        await controller._create_ticket(
            {"title": "Denied", "description": "No account session"},
            trace_parent_action_id="action-2",
        )

    payload = json.loads(str(exc_info.value))
    assert payload["error_code"] == "ACCOUNT_SESSION_REQUIRED"
    assert chat_panel.ticket_client.calls[0]["requester_account"] is None
