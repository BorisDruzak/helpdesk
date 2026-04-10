import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_gui.chat_panel import (  # noqa: E402
    ChatPanel,
    can_user_confirm_close,
    merge_ticket_stream,
    message_visual_role,
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
