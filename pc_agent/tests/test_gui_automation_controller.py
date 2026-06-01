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
        self.run_tool_calls: list[dict] = []
        self.send_message_calls: list[dict] = []
        self.close_ticket_calls: list[dict] = []
        self.get_ticket_calls: list[dict] = []

    async def create_ticket(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    async def run_tool(self, **kwargs):
        self.run_tool_calls.append(kwargs)
        return {"status": "accepted", "operation_id": "op-1"}

    async def send_message(self, *args, **kwargs):
        self.send_message_calls.append({"args": args, **kwargs})
        return {"status": "ok", "message_id": "message-1"}

    async def close_ticket(self, *args, **kwargs):
        self.close_ticket_calls.append({"args": args, **kwargs})
        return {"status": "ok"}

    async def get_ticket(self, *args, **kwargs):
        self.get_ticket_calls.append({"args": args, **kwargs})
        return {"ticket": {"ticket_id": args[0] if args else "ticket-1"}, "messages": [], "events": []}


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
        self.device_id = "device-1"
        self.active_ticket_id = None
        self.tickets_cache = []
        self._profiles_data = {"active_profile_id": "profile-1", "profiles": [{"id": "profile-1"}]}
        self._ticket_detail_timer = _Timer()
        self._last_timeline_html = None
        self._last_detail_header_sig = None
        self._pending_ticket_snapshot = None
        self.attach_calls: list[dict] = []
        self.detail_refresh_account_sessions: list[dict | None] = []

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

    async def _async_attach_files(self, *_args, **_kwargs) -> None:
        self.attach_calls.append(
            {
                "args": _args,
                "kwargs": _kwargs,
                "account_session": self._current_account_session(),
            }
        )

    def _reset_active_ticket_cache(self) -> None:
        pass

    async def _async_refresh_ticket_list(self) -> None:
        pass

    async def _async_refresh_ticket_detail(self) -> None:
        self.detail_refresh_account_sessions.append(self._current_account_session())

    def _show_chat_screen(self) -> None:
        pass

    def _ensure_timeline_bottom_follow(self) -> None:
        pass

    def _refresh_ticket_detail_async(self) -> None:
        pass

    def _refresh_ticket_list_async(self) -> None:
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
async def test_automation_create_ticket_forwards_service_catalog_selection():
    account_session = {"account_session_id": "session-1", "session_token": "token-1"}
    chat_panel = _ChatPanel(account_session=account_session)
    controller = GuiAutomationController(_Window(chat_panel))

    result = await controller._create_ticket(
        {
            "title": "Live Check",
            "description": "Access request from automation",
            "form_key": "live_check",
            "request_template_key": "live_check",
            "service_code": "access",
            "offering_code": "live_check",
            "offering_full_code": "access.live_check",
            "form_payload": {"system": "resource"},
        },
        trace_parent_action_id="action-catalog",
    )

    assert result["status"] == "ok"
    call = chat_panel.ticket_client.calls[0]
    assert call["form_key"] == "live_check"
    assert call["request_template_key"] == "live_check"
    assert call["service_code"] == "access"
    assert call["offering_code"] == "live_check"
    assert call["offering_full_code"] == "access.live_check"


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


@pytest.mark.asyncio
async def test_automation_run_tool_sends_active_account_session():
    account_session = {"account_session_id": "session-1", "session_token": "token-1"}
    chat_panel = _ChatPanel(account_session=account_session)
    controller = GuiAutomationController(_Window(chat_panel))

    result = await controller._run_ticket_tool(
        {
            "ticket_id": "ticket-1",
            "tool_name": "system.collect",
            "params": {"preset": "basic"},
        },
        trace_parent_action_id="action-tool",
    )

    assert result["status"] == "ok"
    assert result["ticket_id"] == "ticket-1"
    call = chat_panel.ticket_client.run_tool_calls[0]
    assert call["account_session"] == account_session
    assert call["trace_parent_action_id"] == "action-tool"


@pytest.mark.asyncio
async def test_automation_capture_video_sends_active_account_session():
    account_session = {"account_session_id": "session-1", "session_token": "token-1"}
    chat_panel = _ChatPanel(account_session=account_session)
    controller = GuiAutomationController(_Window(chat_panel))

    result = await controller.run_action(
        {
            "action": "ticket.capture_video",
            "ticket_id": "ticket-1",
            "duration_sec": 5,
        }
    )

    assert result["status"] == "ok"
    call = chat_panel.ticket_client.run_tool_calls[0]
    assert call["tool_name"] == "screen.record"
    assert call["params"] == {"duration_sec": 5}
    assert call["account_session"] == account_session


@pytest.mark.asyncio
async def test_automation_capture_screenshot_sends_active_account_session():
    account_session = {"account_session_id": "session-1", "session_token": "token-1"}
    chat_panel = _ChatPanel(account_session=account_session)
    controller = GuiAutomationController(_Window(chat_panel))

    result = await controller.run_action(
        {
            "action": "ticket.capture_screenshot",
            "ticket_id": "ticket-1",
        }
    )

    assert result["status"] == "ok"
    call = chat_panel.ticket_client.run_tool_calls[0]
    assert call["tool_name"] == "screen.collect"
    assert call["account_session"] == account_session


@pytest.mark.asyncio
async def test_automation_send_message_sends_active_account_session():
    account_session = {"account_session_id": "session-1", "session_token": "token-1"}
    chat_panel = _ChatPanel(account_session=account_session)
    controller = GuiAutomationController(_Window(chat_panel))

    result = await controller._send_message(
        {"ticket_id": "ticket-1", "text": "hello"},
        trace_parent_action_id="action-message",
    )

    assert result["status"] == "ok"
    call = chat_panel.ticket_client.send_message_calls[0]
    assert call["args"][:2] == ("ticket-1", "hello")
    assert call["account_session"] == account_session
    assert call["trace_parent_action_id"] == "action-message"


@pytest.mark.asyncio
async def test_automation_confirm_resolution_sends_active_account_session():
    account_session = {"account_session_id": "session-1", "session_token": "token-1"}
    chat_panel = _ChatPanel(account_session=account_session)
    controller = GuiAutomationController(_Window(chat_panel))

    result = await controller._confirm_resolution(
        {"ticket_id": "ticket-1", "reason": "requester_confirmed_resolution"},
        trace_parent_action_id="action-close",
    )

    assert result["status"] == "ok"
    call = chat_panel.ticket_client.close_ticket_calls[0]
    assert call["args"][0] == "ticket-1"
    assert call["account_session"] == account_session
    assert call["trace_parent_action_id"] == "action-close"


@pytest.mark.asyncio
async def test_automation_snapshot_sends_active_account_session():
    account_session = {"account_session_id": "session-1", "session_token": "token-1"}
    chat_panel = _ChatPanel(account_session=account_session)
    controller = GuiAutomationController(_Window(chat_panel))

    result = await controller._ticket_snapshot(
        {"ticket_id": "ticket-1", "limit": 10},
        trace_parent_action_id="action-snapshot",
    )

    assert result["status"] == "ok"
    call = chat_panel.ticket_client.get_ticket_calls[0]
    assert call["args"][0] == "ticket-1"
    assert call["limit"] == 10
    assert call["account_session"] == account_session
    assert call["trace_parent_action_id"] == "action-snapshot"


@pytest.mark.asyncio
async def test_automation_open_ticket_refreshes_detail_with_active_account_session():
    account_session = {"account_session_id": "session-1", "session_token": "token-1"}
    chat_panel = _ChatPanel(account_session=account_session)
    controller = GuiAutomationController(_Window(chat_panel))

    result = await controller._open_ticket({"ticket_id": "ticket-1"})

    assert result["status"] == "ok"
    assert chat_panel.detail_refresh_account_sessions[-1] == account_session


@pytest.mark.asyncio
async def test_automation_attach_files_uses_gui_account_session_helper(tmp_path):
    account_session = {"account_session_id": "session-1", "session_token": "token-1"}
    chat_panel = _ChatPanel(account_session=account_session)
    controller = GuiAutomationController(_Window(chat_panel))
    attachment = tmp_path / "note.txt"
    attachment.write_text("hello", encoding="utf-8")

    result = await controller._attach_files(
        {"ticket_id": "ticket-1", "file_paths": [str(attachment)]},
        trace_parent_action_id="action-attach",
    )

    assert result["status"] == "ok"
    assert chat_panel.attach_calls[0]["account_session"] == account_session
    assert chat_panel.attach_calls[0]["kwargs"]["trace_parent_action_id"] == "action-attach"


@pytest.mark.asyncio
async def test_automation_run_tool_without_account_keeps_deterministic_server_denial_path():
    chat_panel = _ChatPanel(account_session=None)
    controller = GuiAutomationController(_Window(chat_panel))

    await controller._run_ticket_tool(
        {
            "ticket_id": "ticket-1",
            "tool_name": "screen.collect",
        },
        trace_parent_action_id="action-no-account",
    )

    call = chat_panel.ticket_client.run_tool_calls[0]
    assert call["account_session"] is None
