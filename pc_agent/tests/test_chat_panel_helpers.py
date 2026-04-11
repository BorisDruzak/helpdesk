import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ui_gui.chat_panel as chat_panel_module

from ui_gui.chat_panel import (  # noqa: E402
    ChatPanel,
    can_user_confirm_close,
    merge_ticket_stream,
    message_visual_role,
    prepend_ticket_stream,
    ticket_matches_query,
    ticket_status_label,
)


def test_ticket_matches_query_checks_multiple_fields():
    ticket = {
        "ticket_code": "ABC-42",
        "title": "Printer is offline",
        "status": "waiting_on_user",
        "requester_display_name": "Ivan Petrov",
    }

    assert ticket_matches_query(ticket, "printer")
    assert ticket_matches_query(ticket, "abc-42")
    assert ticket_matches_query(ticket, "ivan")
    assert not ticket_matches_query(ticket, "network")


def test_message_visual_role_treats_agent_messages_as_outgoing_for_gui():
    assert message_visual_role({"from_role": "agent", "direction": "from_agent"}) == "self"
    assert message_visual_role({"from_role": "support"}) == "support"
    assert message_visual_role({"from_role": "system"}) == "neutral"


def test_can_user_confirm_close_only_for_resolved_ticket():
    assert can_user_confirm_close({"status": "resolved"}) is True
    assert can_user_confirm_close({"status": "in_progress"}) is False


def test_ticket_status_label_is_localized():
    assert ticket_status_label("waiting_on_user") == "Ждёт пользователя"
    assert ticket_status_label("closed") == "Закрыт"


def test_resolve_reply_reference_prefers_message_index_and_fallback_author():
    panel = ChatPanel.__new__(ChatPanel)
    resolved = panel._resolve_reply_reference(
        {"parent_message_id": "msg-1"},
        {
            "msg-1": {
                "text": "Support answer",
                "from_role": "support",
            }
        },
    )

    assert resolved == {
        "parent_message_id": "msg-1",
        "preview": "Support answer",
        "sender_role": "support",
        "sender_display_name": "Поддержка",
        "ts": "",
    }


def test_merge_ticket_stream_appends_only_new_items():
    merged = merge_ticket_stream(
        [{"id": 1, "text": "first"}],
        [{"id": 1, "text": "duplicate"}, {"id": 2, "text": "second"}],
        key_fields=("id",),
    )

    assert merged == [
        {"id": 1, "text": "first"},
        {"id": 2, "text": "second"},
    ]


def test_prepend_ticket_stream_inserts_older_items_without_duplicates():
    merged = prepend_ticket_stream(
        [{"id": 3, "text": "third"}, {"id": 4, "text": "fourth"}],
        [{"id": 1, "text": "first"}, {"id": 2, "text": "second"}, {"id": 3, "text": "dup"}],
        key_fields=("id",),
    )

    assert merged == [
        {"id": 1, "text": "first"},
        {"id": 2, "text": "second"},
        {"id": 3, "text": "third"},
        {"id": 4, "text": "fourth"},
    ]


def test_on_timeline_scroll_changed_ignores_range_change_for_follow_flag():
    panel = ChatPanel.__new__(ChatPanel)
    panel._suspend_scroll_tracking = False
    panel._follow_latest_messages = False
    refreshed = []
    panel._refresh_jump_to_latest_button = lambda *_: refreshed.append(True)
    panel._is_timeline_near_bottom = lambda threshold_px=32: True

    panel._on_timeline_scroll_changed(0, 100)

    assert panel._follow_latest_messages is False
    assert refreshed == [True]


def test_ensure_timeline_bottom_follow_restores_now_and_later(monkeypatch):
    panel = ChatPanel.__new__(ChatPanel)
    panel._follow_latest_messages = False
    panel._force_scroll_to_latest_on_next_render = False
    restore_calls = []
    delayed_calls = []
    panel._restore_timeline_scroll = lambda a, b, c: restore_calls.append((a, b, c))

    def fake_single_shot(delay_ms, callback):
        delayed_calls.append(delay_ms)

    monkeypatch.setattr(chat_panel_module.QTimer, "singleShot", staticmethod(fake_single_shot))

    panel._ensure_timeline_bottom_follow()

    assert panel._follow_latest_messages is True
    assert panel._force_scroll_to_latest_on_next_render is True
    assert restore_calls == [(0, 0, True)]
    assert delayed_calls == [80, 180, 320]


def test_restore_timeline_scroll_ignores_stale_timer_callbacks(monkeypatch):
    panel = ChatPanel.__new__(ChatPanel)
    panel._timeline_scroll_restore_revision = 0
    apply_calls = []
    callbacks = []
    panel._apply_timeline_scroll = lambda a, b, c: apply_calls.append((a, b, c))

    def fake_single_shot(_delay_ms, callback):
        callbacks.append(callback)

    monkeypatch.setattr(chat_panel_module.QTimer, "singleShot", staticmethod(fake_single_shot))

    panel._restore_timeline_scroll(10, 20, False)
    panel._restore_timeline_scroll(0, 0, True)

    for callback in callbacks:
        callback()

    assert apply_calls == [(0, 0, True), (0, 0, True)]


def test_can_incrementally_append_timeline_when_existing_items_are_prefix():
    assert ChatPanel._can_incrementally_append_timeline(
        ["item-1", "item-2"],
        ["item-1", "item-2", "item-3"],
    ) is True


def test_can_incrementally_append_timeline_rejects_equal_or_changed_prefix():
    assert ChatPanel._can_incrementally_append_timeline(
        ["item-1", "item-2"],
        ["item-1", "item-2"],
    ) is False
    assert ChatPanel._can_incrementally_append_timeline(
        ["item-1", "item-2"],
        ["item-1", "other", "item-3"],
    ) is False


def test_can_incrementally_prepend_timeline_when_existing_items_are_suffix():
    assert ChatPanel._can_incrementally_prepend_timeline(
        ["item-3", "item-4"],
        ["item-1", "item-2", "item-3", "item-4"],
    ) is True


def test_apply_prepend_timeline_scroll_keeps_viewport_anchor():
    class _ScrollBar:
        def __init__(self):
            self._value = 18
            self._maximum = 120

        def value(self):
            return self._value

        def setValue(self, value):
            self._value = value

        def maximum(self):
            return self._maximum

    scroll_bar = _ScrollBar()

    class _ScrollArea:
        def verticalScrollBar(self):
            return scroll_bar

    panel = ChatPanel.__new__(ChatPanel)
    panel.timeline_scroll = _ScrollArea()
    panel._suspend_scroll_tracking = False
    panel._refresh_jump_to_latest_button = lambda *_: None

    panel._apply_prepend_timeline_scroll(previous_value=18, previous_max=80)

    assert scroll_bar.value() == 58


def test_latest_requester_read_event_id_is_blocked_for_partial_history_gap():
    panel = ChatPanel.__new__(ChatPanel)
    panel._has_older_history = True
    panel._oldest_loaded_event_id = 50

    result = panel._latest_requester_read_event_id(
        {
            "chat_counters": {
                "requester_unread_messages": 2,
                "requester_unread_tool_calls": 0,
                "requester_last_read_event_id": 10,
            }
        },
        [{"event_id": 70}],
        [{"id": 71}],
    )

    assert result == 0


def test_latest_requester_read_event_id_uses_loaded_tail_when_gap_is_closed():
    panel = ChatPanel.__new__(ChatPanel)
    panel._has_older_history = False
    panel._oldest_loaded_event_id = 50

    result = panel._latest_requester_read_event_id(
        {
            "chat_counters": {
                "requester_unread_messages": 1,
                "requester_unread_tool_calls": 1,
                "requester_last_read_event_id": 49,
            }
        },
        [{"event_id": 70}],
        [{"id": 71}],
    )

    assert result == 71


def test_on_timeline_scroll_changed_clears_force_scroll_flag():
    panel = ChatPanel.__new__(ChatPanel)
    panel._suspend_scroll_tracking = False
    panel._force_scroll_to_latest_on_next_render = True
    panel._is_timeline_near_bottom = lambda threshold_px=32: False
    panel._refresh_jump_to_latest_button = lambda *_: None

    panel._on_timeline_scroll_changed(10)

    assert panel._follow_latest_messages is False
    assert panel._force_scroll_to_latest_on_next_render is False


def test_on_timeline_scroll_changed_requests_older_history_near_top():
    panel = ChatPanel.__new__(ChatPanel)
    panel._suspend_scroll_tracking = False
    panel._force_scroll_to_latest_on_next_render = True
    panel._has_older_history = True
    panel._loading_older_history = False
    panel.active_ticket_id = "ticket-1"
    panel._is_timeline_near_bottom = lambda threshold_px=32: False
    panel._refresh_jump_to_latest_button = lambda *_: None
    requested = []
    panel._load_older_history_async = lambda: requested.append(True)

    panel._on_timeline_scroll_changed(10)

    assert requested == [True]
