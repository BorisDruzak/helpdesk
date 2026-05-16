import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pc_agent.ui_gui.main_window import MainWindow


class _FakeLabel:
    def __init__(self):
        self.value = ""

    def setText(self, value):
        self.value = value

    def text(self):
        return self.value


class _FakeButton:
    def __init__(self):
        self._text = ""
        self.enabled = True
        self.visible = False

    def setText(self, value):
        self._text = value

    def text(self):
        return self._text

    def setEnabled(self, value):
        self.enabled = value

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def isVisible(self):
        return self.visible


def _build_window(snapshot=None):
    window = MainWindow.__new__(MainWindow)
    window._repair_text = lambda value: value
    window.agent_footer_label = _FakeLabel()
    window.agent_footer_meta = _FakeLabel()
    window.update_agent_btn = _FakeButton()
    window._update_status_snapshot = snapshot or {}
    return window


def test_render_update_status_shows_requested_state_while_waiting_for_delivery():
    window = _build_window(
        {
            "agent_version": "3.1.20",
            "is_release": True,
            "update_available": False,
            "recommended_version": "3.1.21",
            "update_request_state": "requested",
            "update_request_version": "3.1.21",
            "update_request_operation_id": "op-1",
        }
    )

    window._render_update_status()

    assert window.update_agent_btn.isVisible() is True
    assert window.update_agent_btn.enabled is False
    assert "3.1.21" in window.update_agent_btn.text()
    assert "3.1.21" in window.agent_footer_meta.text()
    assert "op-1" in window.agent_footer_meta.text()


def test_render_update_status_shows_pending_restart_state():
    window = _build_window(
        {
            "agent_version": "3.1.20",
            "is_release": True,
            "update_available": False,
            "pending_update_version": "3.1.21",
            "pending_update_operation_id": "op-2",
            "update_request_state": "pending_restart",
            "update_request_version": "3.1.21",
            "update_request_operation_id": "op-2",
        }
    )

    window._render_update_status()

    assert window.update_agent_btn.isVisible() is True
    assert window.update_agent_btn.enabled is False
    assert "3.1.21" in window.update_agent_btn.text()
    assert "3.1.21" in window.agent_footer_meta.text()
    assert "op-2" in window.agent_footer_meta.text()


@pytest.mark.asyncio
async def test_async_trigger_update_sets_requested_state_and_starts_refresh_burst():
    window = _build_window(
        {
            "agent_version": "3.1.20",
            "is_release": True,
            "update_available": True,
            "recommended_version": "3.1.21",
        }
    )
    messages = []
    burst_calls = []
    refresh_calls = []

    async def fake_ui_request(method, path, payload=None, timeout_sec=10):
        assert method == "POST"
        assert path == "/ui/agent/update"
        return {
            "status": "accepted",
            "recommendation": {"recommended_version": "3.1.21"},
            "server_response": {"operation_id": "op-accepted"},
        }

    async def fake_refresh_runtime_snapshot(*, update_panel):
        refresh_calls.append(update_panel)
        return {}

    window._async_ui_request = fake_ui_request
    window._async_refresh_runtime_snapshot = fake_refresh_runtime_snapshot
    window._show_nonblocking_message = lambda *args: messages.append(args)
    window._schedule_update_refresh_burst = lambda: burst_calls.append(True)

    await window._async_trigger_update()

    assert window._update_status_snapshot["update_request_state"] == "requested"
    assert window._update_status_snapshot["update_request_version"] == "3.1.21"
    assert window._update_status_snapshot["update_request_operation_id"] == "op-accepted"
    assert window.update_agent_btn.enabled is False
    assert burst_calls == [True]
    assert refresh_calls == [False]
    assert messages
