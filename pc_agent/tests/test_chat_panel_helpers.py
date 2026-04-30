import sys
import inspect
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ui_gui.chat_panel as chat_panel_module
import ui_gui.main_window as main_window_module

from PySide6.QtWidgets import QApplication, QComboBox, QListWidget, QLineEdit  # noqa: E402

from ui_gui.chat_panel import (  # noqa: E402
    ChatPanel,
    build_request_creation_preview,
    build_diagnostic_consent_payload,
    build_default_ticket_form_pack,
    build_priority_facts_payload,
    build_priority_facts_payload_from_form,
    build_ticket_sla_user_summary,
    can_user_confirm_close,
    diagnostic_consent_required,
    merge_ticket_stream,
    message_visual_role,
    normalize_ticket_form_pack,
    prepend_ticket_stream,
    ticket_form_priority_field_keys,
    ticket_request_form_summary_rows,
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


def test_ticket_request_form_summary_rows_extracts_form_title_and_fields():
    rows = ticket_request_form_summary_rows(
        {
            "custom_fields": {
                "request_form_title": "Поломка",
                "request_form_summary": [
                    {"label": "Что сломалось", "value": "МФУ"},
                    {"label": "Кабинет", "value": "4"},
                ],
            }
        }
    )

    assert rows == [
        ("Форма", "Поломка"),
        ("Что сломалось", "МФУ"),
        ("Кабинет", "4"),
    ]


def test_ticket_creation_user_microcopy_uses_request_wording():
    creation_source = "\n".join(
        [
            inspect.getsource(chat_panel_module.TicketCreateDialog),
            inspect.getsource(chat_panel_module.TicketCreateWizardWidget),
            inspect.getsource(chat_panel_module.TicketsSidebarWidget),
            inspect.getsource(chat_panel_module.ChatPanel._async_create_ticket),
            inspect.getsource(main_window_module.MainWindow._build_dashboard_page),
            inspect.getsource(main_window_module.MainWindow._refresh_sidebar_labels),
        ]
    )

    forbidden_visible_fragments = [
        "Создать тикет",
        "Создание тикета",
        "Тип заявки",
        "Загружаю формы создания тикета",
        "Создаю тикет",
        "Тикет создан",
        "После создания тикета",
        "Нельзя создать тикет",
        "Перейти к тикетам",
    ]
    for fragment in forbidden_visible_fragments:
        assert fragment not in creation_source

    assert "Создать обращение" in creation_source
    assert "Шаблон обращения" in creation_source
    assert "Обращение создано" in creation_source


def test_ticket_create_wizard_uses_server_backed_preview():
    source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget)

    assert "preview_ticket_create" in source
    assert "server_preview=self._server_creation_preview" in source


def test_agent_default_forms_carry_process_type_and_priority_policy():
    pack = build_default_ticket_form_pack()
    forms = {item["key"]: item for item in pack["forms"]}

    assert forms["breakage"]["request_template_key"] == "breakage"
    assert forms["breakage"]["request_template_title"] == "Поломка"
    assert forms["breakage"]["ticket_type"] == "incident"
    assert forms["access"]["ticket_type"] == "access_request"
    assert forms["software_install"]["ticket_type"] == "service_request"
    assert forms["site_system"]["priority_policy"]["impact_field"] == "impact_scope"
    assert forms["site_system"]["priority_policy"]["urgency_field"] == "work_continuity"
    assert {"impact_scope", "work_continuity", "business_importance"}.issubset(
        {field["key"] for field in forms["site_system"]["fields"]}
    )
    assert "priority_field" in forms["site_system"]["field_roles"]["impact_scope"]


def test_agent_normalizes_request_template_identity_from_server_pack():
    pack = normalize_ticket_form_pack(
        {
            "pack_key": "request_forms",
            "version": "2.0.0",
            "title": "Каталог обращений",
            "forms": [
                {
                    "key": "website_form",
                    "request_template_key": "website_unavailable",
                    "request_template_title": "Не открывается сайт",
                    "request_kind": "website_unavailable",
                    "ticket_type": "incident",
                    "title": "Не открывается сайт",
                    "description": "Проверим адрес и симптомы.",
                    "fields": [
                        {"key": "url", "label": "Адрес сайта", "type": "text", "required": True},
                    ],
                }
            ],
        }
    )

    form = pack["forms"][0]
    assert form["key"] == "website_form"
    assert form["request_template_key"] == "website_unavailable"
    assert form["request_template_title"] == "Не открывается сайт"


def test_ticket_form_priority_field_keys_use_policy_modifiers_and_roles():
    form = {
        "fields": [
            {"key": "who"},
            {"key": "can_work"},
            {"key": "deadline"},
            {"key": "critical_service"},
            {"key": "route_only"},
        ],
        "priority_policy": {
            "impact_field": "who",
            "urgency_field": "can_work",
            "importance_field": "deadline",
            "modifier_fields": {"critical_service": "critical_service"},
        },
        "field_roles": {
            "route_only": ["routing_field"],
            "deadline": ["priority_field"],
        },
    }

    assert ticket_form_priority_field_keys(form) == ["who", "can_work", "deadline", "critical_service"]


def test_build_priority_facts_payload_from_server_driven_form_policy():
    form = {
        "priority_policy": {
            "impact_field": "affected_users",
            "urgency_field": "continuity",
            "importance_field": "deadline_pressure",
        }
    }

    payload = build_priority_facts_payload_from_form(
        form,
        {
            "affected_users": "department",
            "continuity": "work_stopped_no_workaround",
            "deadline_pressure": "deadline_today",
        },
    )

    assert payload["urgency"] is True
    assert payload["importance"] is True
    assert payload["form_payload"] == {
        "impact_scope": "department",
        "work_continuity": "work_stopped_no_workaround",
        "business_importance": "deadline_today",
    }


def test_dynamic_fields_widget_supports_extended_field_types():
    app = QApplication.instance() or QApplication([])
    assert app is not None
    widget = chat_panel_module.TicketDynamicFieldsWidget()
    widget.set_form(
        {
            "fields": [
                {
                    "key": "symptoms",
                    "label": "Симптомы",
                    "type": "multi_select",
                    "required": True,
                    "options": [
                        {"value": "dns", "label": "DNS"},
                        {"value": "proxy", "label": "Прокси"},
                    ],
                },
                {"key": "started_at", "label": "Когда началось", "type": "datetime", "required": True},
                {"key": "target_url", "label": "Адрес", "type": "url", "required": True},
                {"key": "owner", "label": "Владелец", "type": "user_picker", "required": False},
                {"key": "contact_phone", "label": "Телефон", "type": "phone", "required": False},
            ]
        },
        values={
            "symptoms": ["dns", "proxy"],
            "started_at": "2026-05-01T09:30",
            "target_url": "https://example.test",
            "owner": "ivan.petrov",
            "contact_phone": "+7 900 000-00-00",
        },
    )

    assert isinstance(widget._widgets["symptoms"], QListWidget)
    assert isinstance(widget._widgets["started_at"], QLineEdit)
    assert widget.values() == {
        "symptoms": ["dns", "proxy"],
        "started_at": "2026-05-01T09:30",
        "target_url": "https://example.test",
        "owner": "ivan.petrov",
        "contact_phone": "+7 900 000-00-00",
    }
    assert widget.missing_required_labels() == []


def test_dynamic_fields_widget_uses_registry_options_for_picker_fields():
    app = QApplication.instance() or QApplication([])
    assert app is not None
    widget = chat_panel_module.TicketDynamicFieldsWidget()
    widget.set_form(
        {
            "fields": [
                {"key": "department_id", "label": "Подразделение", "type": "department_picker", "required": True},
                {"key": "location_id", "label": "Кабинет", "type": "location_picker", "required": True},
                {"key": "device_id", "label": "Устройство", "type": "device_picker", "required": False},
                {"key": "service_id", "label": "Сервис", "type": "service_picker", "required": False},
                {"key": "owner_id", "label": "Пользователь", "type": "user_picker", "required": False},
            ]
        },
        registry_options={
            "departments": [{"value": "dep-1", "label": "ИТ"}],
            "locations": [{"value": "loc-1", "label": "Здание 4 / 214"}],
            "devices": [{"value": "dev-1", "label": "OPT-214"}],
            "services": [{"value": "svc-1", "label": "Почта"}],
            "users": [{"value": "person-1", "label": "Иван Иванов"}],
        },
    )

    department_widget = widget._widgets["department_id"]
    assert isinstance(department_widget, QComboBox)
    department_widget.setCurrentIndex(department_widget.findData("dep-1"))
    widget._widgets["location_id"].setCurrentIndex(widget._widgets["location_id"].findData("loc-1"))
    widget._widgets["device_id"].setCurrentIndex(widget._widgets["device_id"].findData("dev-1"))
    widget._widgets["service_id"].setCurrentIndex(widget._widgets["service_id"].findData("svc-1"))
    widget._widgets["owner_id"].setCurrentIndex(widget._widgets["owner_id"].findData("person-1"))

    assert widget.values() == {
        "department_id": "dep-1",
        "location_id": "loc-1",
        "device_id": "dev-1",
        "service_id": "svc-1",
        "owner_id": "person-1",
    }


def test_dynamic_fields_widget_returns_file_metadata_for_file_field(tmp_path):
    app = QApplication.instance() or QApplication([])
    assert app is not None
    file_path = tmp_path / "error.log"
    file_path.write_text("trace", encoding="utf-8")

    widget = chat_panel_module.TicketDynamicFieldsWidget()
    widget.set_form({"fields": [{"key": "evidence", "label": "Файл", "type": "file", "required": True}]})
    widget.set_file_field_path("evidence", str(file_path))

    assert widget.values() == {
        "evidence": {
            "path": str(file_path),
            "filename": "error.log",
        }
    }
    assert widget.file_attachment_paths() == [str(file_path)]
    assert widget.missing_required_labels() == []


def test_build_request_creation_preview_uses_template_policies():
    preview = build_request_creation_preview(
        {
            "request_template_title": "Не открывается сайт",
            "routing_policy": {
                "default_queue": "networks",
            },
            "approval_policy": {
                "required": True,
            },
            "diagnostic_policy": {
                "consent": {"required_for_requester_device": True},
            },
            "sla_policy": {
                "targets": {
                    "first_response": {"P1": "1h"},
                    "resolution": {"P1": "4h"},
                }
            },
        },
        priority_class="P1",
    )

    assert "Шаблон: Не открывается сайт" in preview
    assert "Предварительно попадёт в очередь: networks" in preview
    assert "Потребуется согласование" in preview
    assert "Перед диагностикой потребуется ваше согласие" in preview
    assert "Вам должны ответить примерно за 1 ч" in preview
    assert "Решение или обходной вариант ожидается примерно за 4 ч" in preview


def test_build_request_creation_preview_prefers_server_effective_preview():
    preview = build_request_creation_preview(
        {
            "request_template_title": "Локальный шаблон",
            "routing_policy": {"default_queue": "local"},
        },
        server_preview={
            "request_template_title": "Печать / принтер",
            "routing": {"target_queue_name": "ServiceDesk L1"},
            "sla": {"first_response_minutes": 60, "resolution_minutes": 1440},
            "approval_required": True,
            "diagnostic_consent_required": True,
        },
    )

    assert "Шаблон: Печать / принтер" in preview
    assert "Предварительно попадёт в очередь: ServiceDesk L1" in preview
    assert "Потребуется согласование." in preview
    assert "Перед диагностикой потребуется ваше согласие." in preview
    assert "Вам должны ответить примерно за 1 ч." in preview
    assert "Решение или обходной вариант ожидается примерно за 1 дн." in preview
    assert "SLA" not in preview


def test_diagnostic_consent_payload_marks_requester_device_decision():
    form = {
        "request_template_key": "website_unavailable",
        "diagnostic_policy": {
            "consent": {"required_for_requester_device": True},
        },
    }

    assert diagnostic_consent_required(form) is True
    assert build_diagnostic_consent_payload(form, granted=True) == {
        "required": True,
        "granted": True,
        "scope": "requester_device",
        "source": "pc_agent_create",
        "request_template_key": "website_unavailable",
    }
    assert build_diagnostic_consent_payload({}, granted=True) is None


def test_build_priority_facts_payload_keeps_legacy_booleans_and_structured_facts():
    payload = build_priority_facts_payload(
        impact_scope="department",
        work_continuity="work_stopped_no_workaround",
        business_importance="deadline_today",
        urgency_reason="Отдел не может работать",
        importance_reason="Сегодня крайний срок",
    )

    assert payload["urgency"] is True
    assert payload["importance"] is True
    assert payload["form_payload"] == {
        "impact_scope": "department",
        "work_continuity": "work_stopped_no_workaround",
        "business_importance": "deadline_today",
    }
    assert payload["urgency_reason"] == "Отдел не может работать"
    assert payload["importance_reason"] == "Сегодня крайний срок"


def test_build_ticket_meta_html_includes_request_form_summary():
    panel = ChatPanel.__new__(ChatPanel)
    panel._format_ts = lambda value: value or ""
    panel._support_presence_text = lambda _ticket: "онлайн"
    panel._escape_html = lambda value: str(value)

    html = panel._build_ticket_meta_html(
        {
            "requester_display_name": "Фигаро",
            "requester_profile": {
                "full_name": "ФФигаро",
                "building": "Фигаро",
                "room": "4",
                "phone": "123",
            },
            "priority_class": "P0",
            "queue_code": "servicedesk_l1",
            "assignee_id": "op1",
            "created_at": "2026-04-16T14:57:09+00:00",
            "updated_at": "2026-04-16T14:58:09+00:00",
            "first_response_due_at": "2026-04-16T15:12:09+00:00",
            "resolution_due_at": "2026-04-16T18:57:09+00:00",
            "resolved_at": None,
            "closed_at": None,
            "description": "Сломался принтер",
            "custom_fields": {
                "request_form_title": "Поломка",
                "request_form_summary": [
                    {"label": "Что сломалось", "value": "МФУ"},
                    {"label": "Инвентарный номер", "value": "939218408214"},
                ],
            },
        }
    )

    assert "Форма" in html
    assert "Поломка" in html
    assert "Что сломалось" in html
    assert "МФУ" in html
    assert "Ответить должны до" in html
    assert "2026-04-16T15:12:09+00:00" in html


def test_build_ticket_sla_user_summary_uses_dynamic_due_dates():
    summary = build_ticket_sla_user_summary(
        {
            "priority_class": "P0",
            "first_response_due_at": "2026-04-16T15:12:09+00:00",
            "resolution_due_at": "2026-04-16T18:57:09+00:00",
        }
    )

    assert "Приоритет: P0" in summary
    assert "Вам должны ответить до 2026-04-16T15:12:09+00:00" in summary
    assert "Решение или обходной вариант ожидается до 2026-04-16T18:57:09+00:00" in summary


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


def test_append_contains_incoming_support_items_detects_support_bubbles():
    assert ChatPanel._append_contains_incoming_support_items(
        [
            (1.0, "event", {"bubble_role": "event"}),
            (2.0, "msg", {"bubble_role": "support"}),
        ]
    ) is True
    assert ChatPanel._append_contains_incoming_support_items(
        [
            (1.0, "msg", {"bubble_role": "self"}),
            (2.0, "event", {"bubble_role": "event"}),
        ]
    ) is False


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


def test_schedule_fill_viewport_with_history_requests_more_when_scrollbar_absent(monkeypatch):
    class _ScrollBar:
        def maximum(self):
            return 0

    class _ScrollArea:
        def verticalScrollBar(self):
            return _ScrollBar()

    panel = ChatPanel.__new__(ChatPanel)
    panel.active_ticket_id = "ticket-1"
    panel._has_older_history = True
    panel._loading_older_history = False
    panel.timeline_scroll = _ScrollArea()
    requested = []
    callbacks = []
    def fake_load():
        requested.append(True)
        panel._loading_older_history = True

    panel._load_older_history_async = fake_load

    def fake_single_shot(_delay_ms, callback):
        callbacks.append(callback)

    monkeypatch.setattr(chat_panel_module.QTimer, "singleShot", staticmethod(fake_single_shot))

    panel._schedule_fill_viewport_with_history()

    for callback in callbacks:
        callback()

    assert requested == [True]


def test_schedule_fill_viewport_with_history_skips_when_scrollbar_exists(monkeypatch):
    class _ScrollBar:
        def maximum(self):
            return 12

    class _ScrollArea:
        def verticalScrollBar(self):
            return _ScrollBar()

    panel = ChatPanel.__new__(ChatPanel)
    panel.active_ticket_id = "ticket-1"
    panel._has_older_history = True
    panel._loading_older_history = False
    panel.timeline_scroll = _ScrollArea()
    requested = []
    callbacks = []
    panel._load_older_history_async = lambda: requested.append(True)

    def fake_single_shot(_delay_ms, callback):
        callbacks.append(callback)

    monkeypatch.setattr(chat_panel_module.QTimer, "singleShot", staticmethod(fake_single_shot))

    panel._schedule_fill_viewport_with_history()

    for callback in callbacks:
        callback()

    assert requested == []
