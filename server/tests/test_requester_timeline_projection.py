from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest

from tickets.public_access import build_public_access_message
from tickets.requester_timeline import build_requester_timeline_projection

pytestmark = pytest.mark.no_db


@dataclass
class Event:
    event_type: str
    payload: dict[str, Any]
    created_at: datetime = datetime(2026, 5, 9, tzinfo=timezone.utc)


def project(event_type: str, payload: dict[str, Any] | None = None):
    return build_requester_timeline_projection(Event(event_type, payload or {}))


def test_status_changed_in_progress_has_clear_requester_text():
    projection = project("status_changed", {"new_status": "in_progress"})

    assert projection is not None
    assert projection.kind == "system_event"
    assert projection.text == "Специалист взял обращение в работу."
    assert projection.payload == {"status": "in_progress"}


def test_status_changed_unknown_never_exposes_raw_unknown():
    projection = project("status_changed", {"new_status": "unknown"})

    assert projection is not None
    assert projection.text == "Статус обращения обновлён."
    assert "unknown" not in projection.text.lower()
    assert projection.payload == {}


def test_status_changed_reads_top_level_and_event_details_forms():
    assert (
        build_requester_timeline_projection({"event_type": "status_changed", "status": "waiting_user"}).text
        == "Специалист ждёт ваш ответ."
    )
    assert (
        build_requester_timeline_projection(
            {"type": "status_changed", "event_details": {"new_status": "waiting_internal"}}
        ).text
        == "Обращение передано профильному специалисту."
    )


def test_unknown_and_internal_events_are_hidden_from_requester_timeline():
    hidden_event_types = [
        "ticket_updated",
        "internal_note",
        "worklog_added",
        "message_read",
        "external_notification_delivery",
        "policy_action_dispatched",
        "ticket_hidden_from_workspace",
        "ticket_archived_from_workspace",
        "ola_started",
        "ola_breached",
        "raw_observer_log",
    ]

    for event_type in hidden_event_types:
        assert project(event_type, {"text": "debug raw payload"}) is None


def test_chat_message_maps_public_roles_and_hides_internal_notes():
    user_projection = project("chat_message", {"sender_role": "agent", "visibility": "public", "text": "Не печатает"})
    support_projection = project(
        "chat_message", {"sender_role": "support", "visibility": "public", "text": "Проверим проблему"}
    )
    internal_projection = project(
        "chat_message", {"sender_role": "support", "visibility": "internal", "text": "Внутренняя заметка"}
    )

    assert user_projection is not None
    assert user_projection.kind == "user_message"
    assert user_projection.text == "Не печатает"
    assert support_projection is not None
    assert support_projection.kind == "support_message"
    assert support_projection.text == "Проверим проблему"
    assert internal_projection is None


def test_public_access_code_message_is_system_event_not_support_message():
    projection = project("chat_message", build_public_access_message("RZ76RPDR", "ticket-1"))

    assert projection is not None
    assert projection.kind == "system_event"
    assert projection.text == "Код доступа к заявке сформирован."
    assert projection.payload == {"message_kind": "ticket_public_access_code"}
    assert "RZ76RPDR" not in projection.text
    assert "RZ76RPDR" not in str(projection.payload)


def test_tool_call_result_uses_compact_diagnostic_payload_without_raw_blob():
    projection = project(
        "tool_call_result",
        {
            "operation_id": "op-1",
            "trace_id": "trace-secret",
            "result": {
                "checks": [
                    {
                        "name": "Служба печати",
                        "status": "failed",
                        "summary": "Служба остановлена",
                        "details": "raw token=secret-token trace-secret",
                    },
                    {"title": "Очередь", "ok": True, "message": "Очередь доступна"},
                ],
                "raw_json": {"token": "secret-token"},
            },
        },
    )

    assert projection is not None
    assert projection.kind == "diagnostic_result"
    assert projection.text == "Выполнена диагностика"
    assert projection.payload == {
        "checks": [
            {"label": "Служба печати", "status": "failed", "summary": "Служба остановлена"},
            {"label": "Очередь", "status": "ok", "summary": "Очередь доступна"},
        ]
    }
    assert "result" not in projection.payload
    assert "trace-secret" not in str(projection.payload)
    assert "secret-token" not in str(projection.payload)


def test_ticket_handler_serializers_include_requester_projection_fields():
    from tickets.handlers import _serialize_event_for_agent, _serialize_event_raw

    event = Event("status_changed", {"new_status": "in_progress"})

    raw = _serialize_event_raw(event)
    agent = _serialize_event_for_agent(event)

    assert raw["requester_timeline_text"] == "Специалист взял обращение в работу."
    assert raw["requester_timeline_kind"] == "system_event"
    assert raw["requester_timeline_payload"] == {"status": "in_progress"}
    assert agent["requester_timeline_text"] == "Специалист взял обращение в работу."
    assert agent["requester_timeline_kind"] == "system_event"
    assert agent["requester_timeline_payload"] == {"status": "in_progress"}


def test_ticket_handler_requester_serializer_omits_raw_event_payload():
    from tickets.handlers import _serialize_event_for_requester

    event = Event(
        "routing_applied",
        {
            "actions": {"queue_id": 1},
            "to_queue_id": 1,
            "matched_rule": {"internal": True},
            "routing_source": "fallback_queue",
        },
    )

    requester = _serialize_event_for_requester(event)

    assert requester["type"] == "routing_applied"
    assert requester["requester_timeline_kind"] == "system_event"
    assert "actions" not in requester
    assert "to_queue_id" not in requester
    assert "matched_rule" not in requester
    assert "queue_id" not in str(requester)


def test_ticket_handler_requester_message_sanitizes_public_access_code():
    from tickets.handlers import _serialize_message_for_requester

    event = Event("chat_message", build_public_access_message("RZ76RPDR", "ticket-1"))

    message = _serialize_message_for_requester(event)

    assert message["metadata"] == {"message_kind": "ticket_public_access_code"}
    assert "RZ76RPDR" not in message["text"]
    assert "RZ76RPDR" not in str(message["metadata"])


def test_ticket_handler_requester_visibility_uses_projection_rules():
    from tickets.handlers import _event_visible_to_requester

    assert _event_visible_to_requester(Event("status_changed", {"new_status": "in_progress"})) is True
    assert _event_visible_to_requester(Event("ticket_updated", {"status": "unknown"})) is False
    assert _event_visible_to_requester(Event("internal_note", {"text": "internal"})) is False
    assert (
        _event_visible_to_requester(
            Event("chat_message", {"sender_role": "support", "visibility": "internal", "text": "internal"})
        )
        is False
    )


def test_support_timeline_entry_exposes_same_requester_projection_fields():
    from web_api.support_handlers import _build_timeline_entry

    event = Event("tool_call_result", {"steps": [{"name": "DNS", "status": "ok", "message": "Готово"}]})

    entry = _build_timeline_entry(event)

    assert entry.requester_timeline_text == "Выполнена диагностика"
    assert entry.requester_timeline_kind == "diagnostic_result"
    assert entry.requester_timeline_payload == {"checks": [{"label": "DNS", "status": "ok", "summary": "Готово"}]}
