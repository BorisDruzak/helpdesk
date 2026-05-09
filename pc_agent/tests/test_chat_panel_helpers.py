import sys
import inspect
import os
from pathlib import Path
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ui_gui.chat_panel as chat_panel_module
import ui_gui.main_window as main_window_module

from PySide6.QtWidgets import QApplication, QComboBox, QDateEdit, QDateTimeEdit, QLabel, QListWidget, QLineEdit, QTextEdit  # noqa: E402

from ui_gui.chat_panel import (  # noqa: E402
    ChatPanel,
    build_post_create_process_summary,
    build_post_create_result_labels,
    build_request_creation_preview,
    build_request_template_card_summary,
    build_diagnostic_consent_payload,
    build_diagnostic_consent_requirement_hint,
    build_default_ticket_form_pack,
    build_ticket_deadlines_status_summary,
    build_ticket_diagnostics_user_summary,
    diagnostic_consent_submission_error,
    format_attachment_item_label,
    build_priority_facts_payload,
    build_priority_facts_payload_from_form,
    build_ticket_sla_user_summary,
    can_user_confirm_close,
    diagnostic_consent_required,
    merge_ticket_stream,
    build_ticket_create_error_message,
    message_visual_role,
    normalize_ticket_form_pack,
    prepend_ticket_stream,
    should_apply_ticket_form_pack_update,
    ticket_form_priority_field_keys,
    ticket_request_form_summary_rows,
    ticket_matches_query,
    ticket_status_label,
    validate_create_attachment_paths,
)
from ui_gui import theme  # noqa: E402
from ui_gui.ticket_view_models import (  # noqa: E402
    build_next_action_view_model,
    format_datetime_local,
    format_due_label,
    map_ticket_event_to_user_timeline_item,
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


def test_main_window_has_protected_connection_footer():
    setup_source = inspect.getsource(main_window_module.MainWindow._setup_ui)
    qss = theme.main_window_stylesheet()

    assert "self.security_footer" in setup_source
    assert "SecurityFooter" in setup_source
    assert "Ваше соединение защищено. Все данные передаются в зашифрованном виде." in setup_source
    assert "content_layout.addWidget(self.security_footer" in setup_source
    assert "QFrame#SecurityFooter" in qss
    assert "QLabel#SecurityFooterText" in qss


def test_ticket_create_wizard_uses_server_backed_preview():
    source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget)

    assert "preview_ticket_create" in source
    assert "server_preview=self._server_creation_preview" in source


def test_ticket_create_wizard_has_structured_process_preview_panel():
    source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._build_priority_step)

    assert "process_preview_group" in source
    assert "Что будет после отправки" in source
    assert "preview_label" in source


def test_ticket_create_wizard_has_searchable_template_chooser():
    source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._build_form_step)

    assert "template_search_input" in source
    assert "template_list" in source
    assert "selected_template_card" in source
    assert "Поиск по шаблонам" in source


def test_ticket_create_wizard_has_post_create_result_panel():
    from ui_gui.ticket_create_wizard_widgets import CreateTicketSuccessPanel

    source = "\n".join(
        [
            inspect.getsource(chat_panel_module.TicketCreateWizardWidget),
            inspect.getsource(CreateTicketSuccessPanel),
        ]
    )

    assert "CreateTicketSuccessPanel" in source
    assert "result_group" in source
    assert "Открыть обращение" in source
    assert "Добавить сообщение" in source
    assert "Создать ещё одно" in source
    assert "_show_create_result" in source


def test_create_ticket_success_panel_renders_reference_done_screen():
    from ui_gui.ticket_create_wizard_widgets import CreateTicketSuccessPanel

    app = QApplication.instance() or QApplication([])
    panel = CreateTicketSuccessPanel()
    panel.set_result(
        ticket_number="#T-000521",
        title="Проблема с сайтом",
        access_code="RZ76RPDR",
        next_action="Что дальше: сейчас работает поддержка.",
        deadlines="Вам должны ответить до Сегодня, до 14:15.",
        summary="Обращение отправлено в службу поддержки.",
        has_ticket=True,
    )

    assert app is not None
    assert panel.objectName() == "CreateTicketSuccessPanel"
    assert panel.title_label.text() == "Обращение создано"
    assert panel.ticket_number_label.text() == "#T-000521"
    assert panel.subject_label.text() == "Проблема с сайтом"
    assert panel.access_code_label.text() == "RZ76RPDR"
    assert panel.copy_code_btn.text() == "Скопировать код"
    assert "https://" not in panel.access_code_label.text()
    assert panel.open_created_ticket_btn.isEnabled()
    assert panel.add_message_to_created_ticket_btn.isEnabled()


def test_requester_helpdesk_stylesheet_defines_reference_object_names():
    qss = theme.requester_helpdesk_stylesheet()

    assert "#F6F8FC" in qss
    assert "#4F63F6" in qss
    assert "QFrame#NextActionCard" in qss
    assert "QFrame#InfoCard" in qss
    assert "QLabel#StatusBadge" in qss
    assert "QPushButton#PrimaryButton" in qss
    assert "QPushButton#SecondaryButton" in qss
    assert "QPushButton#TicketTypeCard" in qss
    assert "QFrame#CreateTicketSuccessPanel" in qss
    assert "border-radius: 16px" in qss


def test_requester_helpdesk_stylesheet_is_applied_to_chat_panel_theme():
    source = inspect.getsource(theme.chat_panel_stylesheet)

    assert "requester_helpdesk_stylesheet()" in source


def test_create_ticket_progress_bar_renders_four_human_steps_and_emits_selection():
    from ui_gui.ticket_create_wizard_widgets import CreateTicketProgressBar

    app = QApplication.instance() or QApplication([])
    selected_steps: list[int] = []
    progress = CreateTicketProgressBar(["Тип обращения", "Описание", "Подтверждение", "Готово"])
    progress.stepRequested.connect(selected_steps.append)
    progress.set_state(current_step=2, unlocked_steps={0, 1, 2}, completed_steps={0, 1})

    assert app is not None
    assert progress.objectName() == "CreateTicketProgressBar"
    assert len(progress.step_buttons) == 4
    assert progress.step_buttons[0].text().startswith("✓")
    assert "Тип обращения" in progress.step_buttons[0].text()
    assert progress.step_buttons[2].isChecked()
    assert progress.step_buttons[3].isEnabled() is False

    progress.step_buttons[1].click()

    assert selected_steps == [1]


def test_create_ticket_wizard_cards_use_qss_state_properties_instead_of_inline_styles():
    from ui_gui.ticket_create_wizard_widgets import CreateTicketProgressBar, CreateTicketTypeGrid

    app = QApplication.instance() or QApplication([])
    progress = CreateTicketProgressBar(["Тип обращения", "Описание", "Подтверждение", "Готово"])
    progress.set_state(current_step=1, unlocked_steps={0, 1}, completed_steps={0})
    grid = CreateTicketTypeGrid()
    grid.set_templates(
        [
            {"key": "website", "title": "Проблема с сайтом"},
            {"key": "printer", "title": "Принтер / МФУ"},
        ],
        current_key="website",
    )

    progress_source = inspect.getsource(CreateTicketProgressBar.set_state)
    grid_source = inspect.getsource(CreateTicketTypeGrid.set_selected_key)
    qss = theme.requester_helpdesk_stylesheet()

    assert app is not None
    assert ".setStyleSheet(" not in progress_source
    assert ".setStyleSheet(" not in grid_source
    assert progress.step_buttons[0].property("wizardState") == "completed"
    assert progress.step_buttons[1].property("wizardState") == "current"
    assert progress.step_buttons[3].property("wizardState") == "locked"
    assert grid.card_buttons[0].property("ticketTypeSelected") is True
    assert grid.card_buttons[1].property("ticketTypeSelected") is False
    assert 'wizardState="completed"' in qss
    assert 'ticketTypeSelected="true"' in qss


def test_create_ticket_type_grid_renders_cards_and_emits_template_key():
    from ui_gui.ticket_create_wizard_widgets import CreateTicketTypeGrid

    app = QApplication.instance() or QApplication([])
    selected_keys: list[str] = []
    grid = CreateTicketTypeGrid()
    grid.typeSelected.connect(selected_keys.append)
    grid.set_templates(
        [
            {
                "key": "site_system",
                "title": "Проблема с сайтом",
                "description": "Сайт или веб-сервис не загружается.",
                "category": "website",
            },
            {
                "key": "printer",
                "title": "Принтер / МФУ",
                "description": "Проблемы с печатью или сканированием.",
            },
        ],
        current_key="printer",
    )

    assert app is not None
    assert grid.objectName() == "CreateTicketTypeGrid"
    assert len(grid.card_buttons) == 2
    assert "Проблема с сайтом" in grid.card_buttons[0].text()
    assert "Сайт или веб-сервис" in grid.card_buttons[0].text()
    assert grid.card_buttons[1].isChecked()

    grid.card_buttons[0].click()

    assert selected_keys == ["site_system"]


def test_create_ticket_confirmation_panel_renders_summary_without_inline_checkbox():
    from ui_gui.ticket_create_wizard_widgets import CreateTicketConfirmationPanel

    app = QApplication.instance() or QApplication([])
    panel = CreateTicketConfirmationPanel()
    panel.set_summary(
        category="Проблема с сайтом",
        subject="Не открывается портал",
        requester="Фигаро | Кабинет 501",
        impact="Несколько человек",
        urgency="Работа затруднена",
        description="Ошибка ERR_CONNECTION_TIMED_OUT.",
        attachments=["browser.png", "har_export.har"],
        process_preview="Очередь: IT — Веб-сервисы\nПервый ответ: 2 ч",
    )

    assert app is not None
    assert panel.objectName() == "CreateTicketConfirmationPanel"
    assert panel.category_value.text() == "Проблема с сайтом"
    assert panel.subject_value.text() == "Не открывается портал"
    assert "Фигаро" in panel.requester_value.text()
    assert "browser.png" in panel.attachments_value.text()
    assert not hasattr(panel, "confirm_checkbox")


def test_ticket_create_wizard_uses_progress_bar_component():
    source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget)

    assert "CreateTicketProgressBar" in source
    assert "self.progress_bar" in source
    assert "self.progress_bar.set_state" in source
    assert "stepRequested.connect" in source


def test_ticket_create_wizard_uses_confirmation_panel_before_submit():
    source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget)
    step_ready_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._step_ready)
    submit_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._on_submit_clicked)
    confirm_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._confirm_submit_after_click)

    assert "CreateTicketConfirmationPanel" in source
    assert "self.confirmation_panel" in source
    assert "confirmation_panel.is_confirmed()" not in step_ready_source
    assert "self._confirm_submit_after_click()" in submit_source
    assert "Подтвердите корректность данных" in confirm_source
    assert "Подтверждаю, отправить" in confirm_source


def test_ticket_create_wizard_uses_type_grid_without_changing_form_selector_contract():
    source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget)

    assert "CreateTicketTypeGrid" in source
    assert "self.type_grid" in source
    assert "typeSelected.connect" in source
    assert "_on_type_card_selected" in source
    assert "self.form_selector.findData" in source


def test_ticket_create_wizard_first_step_combines_type_and_profile():
    init_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget.__init__)
    form_step_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._build_form_step)
    ready_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._step_ready)
    caption_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._update_navigation_state)

    assert "_build_profile_step()" not in init_source
    assert "Шаг 1. Тип обращения" in form_step_source
    assert "profile_selector" in form_step_source
    assert "manage_profiles_btn" in form_step_source
    assert "return self._panel.has_active_profile()" not in ready_source
    assert "bool(self._selected_form())" in ready_source
    assert "Выберите тип обращения" in caption_source


def test_ticket_create_wizard_type_step_does_not_render_legacy_template_list_or_dynamic_fields():
    form_step_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._build_form_step)
    description_step_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._build_description_step)
    ready_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._step_ready)
    validation_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._step_validation_error)

    assert "group_layout.addWidget(self.template_search_input)" not in form_step_source
    assert "group_layout.addWidget(self.template_list)" not in form_step_source
    assert "group_layout.addWidget(self.selected_template_card)" not in form_step_source
    assert "group_layout.addWidget(self.dynamic_fields_widget)" not in form_step_source
    assert "description_layout.addWidget(self.form_summary)" in description_step_source
    assert "description_layout.addWidget(self.dynamic_fields_widget)" in description_step_source
    step_zero_block = ready_source.split("if step == 1:", 1)[0]
    assert "dynamic_fields_widget.validate_required_fields" not in step_zero_block
    assert "dynamic_fields_widget.validate_required_fields" in ready_source.split("if step == 1:", 1)[1]
    assert "dynamic_fields_widget.validate_required_fields(show_feedback=True)" in validation_source.split("if step == 1:", 1)[1]


def test_ticket_create_wizard_description_step_wraps_long_forms_in_scroll_area():
    description_step_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._build_description_step)

    assert "self.description_scroll = QScrollArea()" in description_step_source
    assert 'self.description_scroll.setObjectName("CreateTicketDescriptionScroll")' in description_step_source
    assert "self.description_scroll.setWidgetResizable(True)" in description_step_source
    assert "self.description_scroll.setWidget(description_group)" in description_step_source
    assert "layout.addWidget(self.description_scroll, 1)" in description_step_source


def test_ticket_create_wizard_confirmation_step_wraps_long_forms_in_scroll_area():
    priority_step_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._build_priority_step)

    assert "self.confirmation_scroll = QScrollArea()" in priority_step_source
    assert 'self.confirmation_scroll.setObjectName("CreateTicketConfirmationScroll")' in priority_step_source
    assert "self.confirmation_scroll.setWidgetResizable(True)" in priority_step_source
    assert "self.confirmation_scroll.setWidget(confirmation_content)" in priority_step_source
    assert "page_layout.addWidget(self.confirmation_scroll, 1)" in priority_step_source


def test_ticket_create_wizard_submit_uses_gui_task_scheduler():
    submit_click_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._on_submit_clicked)
    scheduler_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._spawn_gui_task)

    assert "asyncio.create_task" not in submit_click_source
    assert 'self._spawn_gui_task(self._async_submit(), name="ticket_create.submit")' in submit_click_source
    assert "loop.create_task(coro, name=name)" in scheduler_source
    assert "done_task.result()" in scheduler_source


def test_ticket_create_wizard_submit_stays_clickable_to_show_validation_feedback():
    nav_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._update_navigation_state)

    assert "self._submit_btn.setVisible(self._current_step == 2)" in nav_source
    assert "self._submit_btn.setEnabled(self._current_step == 2 and not self._submitting)" in nav_source
    assert "self._submit_btn.setEnabled(self._all_required_steps_ready()" not in nav_source


async def test_ticket_create_wizard_submit_click_calls_create_when_ready():
    class _FakeClient:
        async def preview_ticket_create(self, **_kwargs):
            return {}

    class _FakePanel:
        user_display_name = "Tester"

        def __init__(self):
            self.created_payloads: list[dict] = []
            self._ticket_form_pack = build_default_ticket_form_pack()
            self.ticket_client = _FakeClient()
            self._profiles_data = {
                "active_profile_id": "profile-1",
                "profiles": [{"id": "profile-1", "display_name": "Tester"}],
            }

        def ticket_form_pack(self):
            return self._ticket_form_pack

        def registry_options(self):
            return {}

        def _profiles(self):
            return self._profiles_data["profiles"]

        def has_active_profile(self):
            return True

        def current_requester_profile_summary(self):
            return "Tester"

        def _save_profiles(self):
            return None

        async def _async_create_ticket(self, payload, **_kwargs):
            self.created_payloads.append(payload)
            return {
                "ticket": {"ticket_id": "ticket-1", "ticket_code": "T-1", "title": "Test"},
                "public_access_code": "CODE",
            }

    def _fill_dynamic_widget(dynamic_widget) -> None:
        for input_widget in dynamic_widget._widgets.values():
            if isinstance(input_widget, QLineEdit):
                input_widget.setText("значение")
            elif isinstance(input_widget, QTextEdit):
                input_widget.setPlainText("значение")
            elif isinstance(input_widget, QComboBox) and input_widget.count() > 1:
                input_widget.setCurrentIndex(1)

    app = QApplication.instance() or QApplication([])
    panel = _FakePanel()
    wizard = chat_panel_module.TicketCreateWizardWidget(panel)
    assert app is not None

    wizard._on_type_card_selected(wizard.form_selector.itemData(0))
    wizard.description_input.setPlainText("Описание проблемы")
    _fill_dynamic_widget(wizard.dynamic_fields_widget)
    _fill_dynamic_widget(wizard.priority_dynamic_fields_widget)
    wizard._go_to_step(2, force=True)
    wizard._update_navigation_state()
    wizard._confirm_submit_after_click = lambda: True

    assert wizard._submit_btn.isEnabled()
    wizard._submit_btn.click()

    import asyncio

    await asyncio.sleep(0.05)
    assert len(panel.created_payloads) == 1
    assert wizard._current_step == 3


async def test_ticket_create_wizard_submit_confirmation_can_cancel_create():
    class _FakeClient:
        async def preview_ticket_create(self, **_kwargs):
            return {}

    class _FakePanel:
        user_display_name = "Tester"

        def __init__(self):
            self.created_payloads: list[dict] = []
            self._ticket_form_pack = build_default_ticket_form_pack()
            self.ticket_client = _FakeClient()
            self._profiles_data = {
                "active_profile_id": "profile-1",
                "profiles": [{"id": "profile-1", "display_name": "Tester"}],
            }

        def ticket_form_pack(self):
            return self._ticket_form_pack

        def registry_options(self):
            return {}

        def _profiles(self):
            return self._profiles_data["profiles"]

        def has_active_profile(self):
            return True

        def current_requester_profile_summary(self):
            return "Tester"

        def _save_profiles(self):
            return None

        async def _async_create_ticket(self, payload, **_kwargs):
            self.created_payloads.append(payload)
            return {
                "ticket": {"ticket_id": "ticket-1", "ticket_code": "T-1", "title": "Test"},
                "public_access_code": "CODE",
            }

    def _fill_dynamic_widget(dynamic_widget) -> None:
        for input_widget in dynamic_widget._widgets.values():
            if isinstance(input_widget, QLineEdit):
                input_widget.setText("значение")
            elif isinstance(input_widget, QTextEdit):
                input_widget.setPlainText("значение")
            elif isinstance(input_widget, QComboBox) and input_widget.count() > 1:
                input_widget.setCurrentIndex(1)

    app = QApplication.instance() or QApplication([])
    panel = _FakePanel()
    wizard = chat_panel_module.TicketCreateWizardWidget(panel)
    assert app is not None

    wizard._on_type_card_selected(wizard.form_selector.itemData(0))
    wizard.description_input.setPlainText("Описание проблемы")
    _fill_dynamic_widget(wizard.dynamic_fields_widget)
    _fill_dynamic_widget(wizard.priority_dynamic_fields_widget)
    wizard._go_to_step(2, force=True)
    wizard._update_navigation_state()
    wizard._confirm_submit_after_click = lambda: False

    wizard._submit_btn.click()

    import asyncio

    await asyncio.sleep(0.05)
    assert panel.created_payloads == []
    assert wizard._current_step == 2


def test_ticket_create_wizard_has_real_done_step_in_stack():
    init_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget.__init__)
    done_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._build_done_step)
    nav_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._update_navigation_state)
    submit_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._async_submit)

    assert "_build_done_step()" in init_source
    assert "self._stack.addWidget(self.result_group)" in done_source
    assert "self._submit_btn.setVisible(self._current_step == 2" in nav_source
    assert "self._next_btn.setVisible(self._current_step < 2" in nav_source
    assert "self._go_to_step(3, force=True)" in submit_source


def test_ticket_create_wizard_locks_done_step_until_created_ticket_exists():
    nav_source = inspect.getsource(chat_panel_module.TicketCreateWizardWidget._update_navigation_state)

    assert "index < 3 or bool(self._last_created_ticket_id)" in nav_source


def test_open_create_wizard_refreshes_when_form_pack_changes():
    source = inspect.getsource(main_window_module.MainWindow._setup_ui)

    assert "ticketFormPackChanged" in source
    assert "ticket_create_page.refresh_from_panel" in source


def test_build_ticket_create_error_message_uses_user_language():
    assert "Сервер поддержки недоступен" in build_ticket_create_error_message(
        RuntimeError("Cannot connect to host 192.168.100.17:8666")
    )
    assert "Форма обращения изменилась" in build_ticket_create_error_message(
        RuntimeError("FORM_VERSION_CONFLICT")
    )
    assert "Файл слишком большой" in build_ticket_create_error_message(
        RuntimeError("413 Request Entity Too Large")
    )
    assert "Не удалось создать обращение" in build_ticket_create_error_message(RuntimeError("unknown"))
    assert "SLA" not in build_ticket_create_error_message(RuntimeError("SLA failed"))


def test_validate_create_attachment_paths_reports_missing_and_large_files(tmp_path):
    missing_path = tmp_path / "missing.txt"
    large_path = tmp_path / "large.bin"
    large_path.write_bytes(b"x" * 9)

    errors = validate_create_attachment_paths(
        [str(missing_path), str(large_path)],
        max_bytes=8,
    )

    assert "Файл не найден: missing.txt" in errors
    assert any("Файл слишком большой: large.bin" in item for item in errors)


def test_build_request_template_card_summary_surfaces_badges_and_next_steps():
    summary = build_request_template_card_summary(
        {
            "request_template_title": "Не открывается сайт",
            "description": "Поможет собрать адрес сайта, ошибку и масштаб проблемы.",
            "category": "network",
            "fields": [
                {"key": "url", "label": "Адрес сайта", "type": "url", "required": True},
                {"key": "screenshot", "label": "Скриншот", "type": "file", "required": False},
            ],
            "approval_policy": {"required": True},
            "diagnostic_policy": {"suggested_playbooks": ["diagnose.website"]},
            "sla_policy": {"targets": {"first_response": {"P3": "4h"}}},
        },
        priority_class="P3",
    )

    assert "Не открывается сайт" in summary
    assert "Категория: network" in summary
    assert "Поможет собрать адрес сайта" in summary
    assert "Обязательные поля: Адрес сайта" in summary
    assert "Нужно согласование" in summary
    assert "Может быть диагностика" in summary
    assert "Понадобятся файлы" in summary
    assert "Вам должны ответить примерно за 4 ч" in summary


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


def test_agent_normalizes_request_template_schema_and_policy_versions():
    pack = normalize_ticket_form_pack(
        {
            "pack_key": "request_forms",
            "version": "2.1.0",
            "forms": [
                {
                    "key": "website_unavailable",
                    "title": "Не открывается сайт",
                    "ticket_type": "incident",
                    "request_template_version": 4,
                    "form_schema_id": "website_unavailable_form",
                    "form_schema_version": 3,
                    "workflow_profile_id": "incident_default",
                    "priority_policy_code": "incident_priority_policy",
                    "routing_policy_code": "website_routing",
                    "sla_policy_code": "incident_sla",
                    "ola_policy_code": "default_queue_ola",
                    "approval_policy_code": "service_owner_approval",
                    "diagnostic_policy_code": "website_diagnostics",
                    "closure_policy_code": "diagnostic_incident_closure",
                    "visibility_policy_code": "default_public_statuses",
                    "notification_policy_code": "incident_notifications",
                    "reporting_policy_code": "incident_passport",
                    "policy_refs": {
                        "priority": "incident_priority_policy",
                        "routing": "website_routing",
                        "sla": "incident_sla",
                    },
                    "fields": [
                        {"key": "url", "label": "Адрес сайта", "type": "url", "required": True},
                    ],
                }
            ],
        }
    )

    form = pack["forms"][0]
    assert form["request_template_version"] == 4
    assert form["form_schema_id"] == "website_unavailable_form"
    assert form["form_schema_version"] == 3
    assert form["workflow_profile_id"] == "incident_default"
    assert form["priority_policy_code"] == "incident_priority_policy"
    assert form["routing_policy_code"] == "website_routing"
    assert form["sla_policy_code"] == "incident_sla"
    assert form["ola_policy_code"] == "default_queue_ola"
    assert form["approval_policy_code"] == "service_owner_approval"
    assert form["diagnostic_policy_code"] == "website_diagnostics"
    assert form["closure_policy_code"] == "diagnostic_incident_closure"
    assert form["visibility_policy_code"] == "default_public_statuses"
    assert form["notification_policy_code"] == "incident_notifications"
    assert form["reporting_policy_code"] == "incident_passport"
    assert form["policy_refs"]["routing"] == "website_routing"


def test_ticket_form_pack_refresh_decision_detects_policy_ref_change_without_version_bump():
    current = normalize_ticket_form_pack(
        {
            "pack_key": "request_forms",
            "version": "2.1.0",
            "forms": [
                {
                    "key": "website_unavailable",
                    "title": "Не открывается сайт",
                    "routing_policy_code": "website_routing_v1",
                    "fields": [{"key": "url", "label": "Адрес сайта", "type": "url"}],
                }
            ],
        }
    )
    result = {
        "status": "ok",
        "has_update": False,
        "pack": {
            "pack_key": "request_forms",
            "version": "2.1.0",
            "forms": [
                {
                    "key": "website_unavailable",
                    "title": "Не открывается сайт",
                    "routing_policy_code": "website_routing_v2",
                    "fields": [{"key": "url", "label": "Адрес сайта", "type": "url"}],
                }
            ],
        },
    }

    assert should_apply_ticket_form_pack_update(current, result) is True


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
    assert isinstance(widget._widgets["started_at"], QDateTimeEdit)
    assert widget.values() == {
        "symptoms": ["dns", "proxy"],
        "started_at": "2026-05-01T09:30",
        "target_url": "https://example.test",
        "owner": "ivan.petrov",
        "contact_phone": "+7 900 000-00-00",
    }
    assert widget.missing_required_labels() == []


def test_dynamic_fields_widget_hides_internal_process_fields_from_requester():
    app = QApplication.instance() or QApplication([])
    assert app is not None
    normalized = normalize_ticket_form_pack(
        {
            "pack_key": "request_forms",
            "version": "15b",
            "forms": [
                {
                    "key": "website",
                    "title": "Не открывается сайт",
                    "fields": [
                        {
                            "key": "url",
                            "label": "Адрес сайта",
                            "type": "url",
                            "required": True,
                            "visibility": {"visible_to": ["requester", "support"]},
                            "process_mapping": {"roles": ["diagnostic_input"], "diagnostic_param": "target_url"},
                        },
                        {
                            "key": "sla_policy_id",
                            "label": "SLA policy",
                            "type": "select",
                            "required": True,
                            "options": [{"value": "incident_sla", "label": "Incident SLA"}],
                            "visibility": {"visible_to": ["support", "admin"]},
                            "process_mapping": {"roles": ["sla_field"]},
                        },
                        {
                            "key": "ticket_type",
                            "label": "Ticket type",
                            "type": "select",
                            "options": [{"value": "incident", "label": "Incident"}],
                            "visible_to": ["internal"],
                        },
                    ],
                }
            ],
        }
    )

    form = normalized["forms"][0]
    widget = chat_panel_module.TicketDynamicFieldsWidget()
    widget.set_form(form, values={"url": "https://example.test", "sla_policy_id": "incident_sla", "ticket_type": "incident"})

    assert set(widget._widgets) == {"url"}
    assert form["fields"][0]["process_mapping"]["diagnostic_param"] == "target_url"
    assert widget.values() == {"url": "https://example.test"}
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


def test_dynamic_fields_widget_uses_native_date_controls():
    app = QApplication.instance() or QApplication([])
    assert app is not None
    widget = chat_panel_module.TicketDynamicFieldsWidget()
    widget.set_form(
        {
            "fields": [
                {"key": "needed_on", "label": "Нужно к дате", "type": "date", "required": True},
                {"key": "started_at", "label": "Началось", "type": "datetime", "required": True},
            ]
        },
        values={"needed_on": "2026-05-12", "started_at": "2026-05-12T09:30"},
    )

    assert isinstance(widget._widgets["needed_on"], QDateEdit)
    assert isinstance(widget._widgets["started_at"], QDateTimeEdit)
    assert widget.values() == {
        "needed_on": "2026-05-12",
        "started_at": "2026-05-12T09:30",
    }
    assert widget.missing_required_labels() == []


def test_dynamic_fields_widget_can_clear_file_field(tmp_path):
    app = QApplication.instance() or QApplication([])
    assert app is not None
    file_path = tmp_path / "evidence.txt"
    file_path.write_text("proof", encoding="utf-8")

    widget = chat_panel_module.TicketDynamicFieldsWidget()
    widget.set_form({"fields": [{"key": "evidence", "label": "Доказательство", "type": "file", "required": True}]})
    widget.set_file_field_path("evidence", str(file_path))
    assert widget.file_attachment_paths() == [str(file_path)]

    widget.clear_file_field_path("evidence")

    assert widget.values() == {"evidence": {}}
    assert widget.file_attachment_paths() == []
    assert widget.missing_required_labels() == ["Доказательство"]


def test_dynamic_fields_widget_ignores_hidden_required_file_until_condition_matches(tmp_path):
    app = QApplication.instance() or QApplication([])
    assert app is not None
    file_path = tmp_path / "screenshot.png"
    file_path.write_bytes(b"png")

    widget = chat_panel_module.TicketDynamicFieldsWidget()
    widget.set_form(
        {
            "fields": [
                {
                    "key": "problem_area",
                    "label": "Problem area",
                    "type": "select",
                    "required": True,
                    "options": [
                        {"value": "printer", "label": "Printer"},
                        {"value": "website", "label": "Website"},
                    ],
                },
                {
                    "key": "screenshot",
                    "label": "Screenshot",
                    "type": "file",
                    "required": True,
                    "visible_when": {"field": "problem_area", "equals": "website"},
                },
            ]
        },
        values={"problem_area": "printer", "screenshot": {"path": str(file_path)}},
    )

    assert widget.values() == {"problem_area": "printer"}
    assert widget.file_attachment_paths() == []
    assert widget.missing_required_labels() == []

    problem_widget = widget._widgets["problem_area"]
    assert isinstance(problem_widget, QComboBox)
    problem_widget.setCurrentIndex(problem_widget.findData("website"))

    assert widget.values() == {
        "problem_area": "website",
        "screenshot": {"path": str(file_path), "filename": "screenshot.png"},
    }
    assert widget.file_attachment_paths() == [str(file_path)]
    assert widget.missing_required_labels() == []


def test_format_attachment_item_label_includes_file_size(tmp_path):
    file_path = tmp_path / "log.txt"
    file_path.write_bytes(b"x" * 2048)

    assert format_attachment_item_label(str(file_path)) == "log.txt · 2.0 КБ"
    assert format_attachment_item_label(str(tmp_path / "missing.txt")) == "missing.txt"


def test_dynamic_fields_widget_shows_inline_required_message():
    app = QApplication.instance() or QApplication([])
    assert app is not None
    widget = chat_panel_module.TicketDynamicFieldsWidget()
    widget.set_form(
        {
            "fields": [
                {
                    "key": "url",
                    "label": "Адрес сайта",
                    "type": "url",
                    "required": True,
                    "required_message": "Укажите адрес сайта, чтобы поддержка могла проверить доступность.",
                    "help_text": "Можно вставить полный адрес из браузера.",
                }
            ]
        }
    )

    assert widget.validate_required_fields(show_feedback=True) == ["Адрес сайта"]
    assert widget._error_labels["url"].text() == "Укажите адрес сайта, чтобы поддержка могла проверить доступность."
    assert not widget._error_labels["url"].isHidden()

    widget._widgets["url"].setText("https://example.test")

    assert widget.validate_required_fields(show_feedback=True) == []
    assert widget._error_labels["url"].text() == ""


def test_build_post_create_process_summary_explains_next_steps_without_sla():
    summary = build_post_create_process_summary(
        {
            "ticket_code": "HD-42",
            "queue_name": "ServiceDesk L1",
            "assignee_display_name": "Иван Петров",
            "public_status_label": "Заявка в работе",
            "next_action_owner": "support",
            "first_response_due_at": "2026-05-01T10:00:00+05:00",
            "resolution_due_at": "2026-05-02T18:00:00+05:00",
            "custom_fields": {
                "request_template": {
                    "approval_policy": {"required": True},
                    "diagnostic_policy": {"suggested_playbooks": ["diagnose.website"]},
                    "reporting_policy": {"enabled": True},
                }
            },
        },
        public_access_code="ABC123",
    )

    assert "Код доступа: ABC123" in summary
    assert "Очередь: ServiceDesk L1" in summary
    assert "Исполнитель: Иван Петров" in summary
    assert "Сейчас работает поддержка" in summary
    assert "Потребуется согласование" in summary
    assert "Диагностика может быть предложена" in summary
    assert "Паспорт решения будет заполнен" in summary
    assert "Вам должны ответить до" in summary
    assert "Решение или обходной вариант ожидается до" in summary
    assert "SLA" not in summary


def test_build_post_create_process_summary_uses_requester_safe_nested_payload():
    summary = build_post_create_process_summary(
        {
            "ticket_id": "T-100",
            "status": "waiting_on_internal_team",
            "queue_code": "internal-sec",
            "root_cause": "do not show",
            "ola": {"ack_due_at": "do not show"},
            "raw_diagnostics": {"stderr": "do not show"},
            "requester_view": {
                "public_status_label": "Заявка в работе",
                "next_action_owner": "requester",
                "expected_due_at": "2026-05-03T15:45:00+05:00",
                "queue_name": "Сервис-деск",
            },
            "deadlines": {
                "first_response_due_at": "2026-05-02T11:00:00+05:00",
                "resolution_due_at": "2026-05-03T15:45:00+05:00",
            },
            "passport": {
                "status": "draft",
                "user_result_summary": "Доступ к сайту будет проверен после диагностики.",
            },
            "requester_resolution_summary": "Пользовательский итог уже подготовлен.",
        },
        public_access_code="PUB-42",
    )

    assert "Код доступа: PUB-42" in summary
    assert "Статус: Заявка в работе" in summary
    assert "Очередь: Сервис-деск" in summary
    assert "Сейчас нужен ваш ответ" in summary
    assert "Вам должны ответить до" in summary
    assert "Решение или обходной вариант ожидается до" in summary
    assert "Ожидаемый срок: " in summary
    assert "Паспорт решения будет заполнен" in summary
    assert "Итог для пользователя: Доступ к сайту будет проверен после диагностики." in summary
    assert "internal-sec" not in summary
    assert "do not show" not in summary
    assert "OLA" not in summary
    assert "SLA" not in summary


def test_build_post_create_process_summary_mentions_evidence_need_and_uploaded_files():
    summary = build_post_create_process_summary(
        {
            "ticket_id": "T-102",
            "public_status_label": "Заявка в работе",
            "custom_fields": {
                "request_template": {
                    "reporting_policy": {
                        "enabled": True,
                        "required_sections": ["evidence", "user_result"],
                        "required_evidence_types": {"evidence": ["screenshot", "file_attachment"]},
                    },
                    "closure_policy": {"evidence": {"required": True}},
                }
            },
            "requester_view": {
                "passport": {
                    "missing_facts": [
                        {
                            "required_fact": "evidence",
                            "accepted_evidence_types": ["screenshot", "file_attachment"],
                        }
                    ]
                }
            },
            "attachments": [
                {"artifact_id": "artifact-1", "name": "screen.png", "type": "screenshot"},
            ],
        },
        public_access_code="PUB-102",
    )

    assert "Для закрытия может потребоваться доказательство решения" in summary
    assert "Приложенные файлы доступны поддержке как кандидаты доказательств" in summary
    assert "screen.png" not in summary


def test_build_post_create_result_labels_use_requester_view():
    labels = build_post_create_result_labels(
        {
            "ticket_id": "T-101",
            "next_action_owner": "support",
            "first_response_due_at": "",
            "resolution_due_at": "",
            "requester_view": {
                "next_action_owner": "requester",
                "expected_due_at": "2026-05-04T12:00:00+05:00",
            },
            "deadlines": {
                "first_response_due_at": "2026-05-02T11:00:00+05:00",
            },
        },
        public_access_code="PUB-101",
    )

    assert labels["access_code"] == "Код доступа: PUB-101"
    assert labels["next_action"] == "Что дальше: сейчас нужен ваш ответ."
    assert "Вам должны ответить до" in labels["deadlines"]
    assert "Ожидаемый срок" in labels["deadlines"]
    assert "Сейчас нужен ваш ответ" in labels["summary"]


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


def test_build_request_creation_preview_shows_server_deadlines_and_diagnostics():
    preview = build_request_creation_preview(
        {"request_template_title": "Не открывается сайт"},
        server_preview={
            "request_template_title": "Не открывается сайт",
            "routing": {"target_queue_name": "Сеть"},
            "first_response_due_at": "2026-05-02T13:15:00+05:00",
            "resolution_due_at": "2026-05-03T18:30:00+05:00",
            "diagnostics": {"suggested_playbook_title": "Проверка сайта"},
        },
    )

    assert "Предварительно попадёт в очередь: Сеть" in preview
    assert "Вам должны ответить до" in preview
    assert "2026-05-02" in preview
    assert "Решение или обходной вариант ожидается до" in preview
    assert "Диагностика: Проверка сайта." in preview
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


def test_diagnostic_consent_submission_error_blocks_silent_skip():
    form = {
        "request_template_key": "website_unavailable",
        "diagnostic_policy": {
            "consent": {"required_for_requester_device": True},
        },
    }

    assert diagnostic_consent_submission_error(form, granted=False) == (
        "Для этого шаблона требуется согласие на диагностику. "
        "Поставьте галочку согласия или выберите шаблон без автодиагностики."
    )
    assert diagnostic_consent_submission_error(form, granted=True) == ""
    assert diagnostic_consent_submission_error({}, granted=False) == ""


def test_diagnostic_consent_requirement_hint_marks_required_user_action():
    form = {
        "request_template_key": "network",
        "diagnostic_policy": {
            "consent": {"required_for_requester_device": True},
        },
    }

    hint = build_diagnostic_consent_requirement_hint(form)

    assert "Обязательно" in hint
    assert "поставьте галочку" in hint
    assert build_diagnostic_consent_requirement_hint({}) == ""


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
    assert "Вам должны ответить до" in html
    assert "2026-04-16T15:12:09+00:00" in html


def test_build_ticket_meta_html_explains_support_work_without_assignee():
    panel = ChatPanel.__new__(ChatPanel)
    panel._format_ts = lambda value: value or ""
    panel._support_presence_text = lambda _ticket: "онлайн"
    panel._escape_html = lambda value: str(value)

    html = panel._build_ticket_meta_html(
        {
            "requester_display_name": "Борис",
            "requester_profile": {},
            "status": "in_progress",
            "requester_status": "in_work",
            "next_action_owner": "support",
            "queue_code": "servicedesk_l1",
            "assignee_id": "",
            "created_at": "2026-05-04T14:20:20+00:00",
            "updated_at": "2026-05-04T14:23:48+00:00",
        },
        events=[
            {
                "event_type": "status_changed",
                "payload": {
                    "actor_id": "op1",
                    "actor_role": "support",
                    "to_status": "in_progress",
                },
            }
        ],
    )

    assert "Специалист" in html
    assert "Не назначен персонально" in html
    assert "op1" in html
    assert "работе у поддержки" in html


def test_build_ticket_meta_html_is_requester_safe_without_raw_queue_or_priority():
    panel = ChatPanel.__new__(ChatPanel)
    panel._format_ts = lambda value: value or ""
    panel._support_presence_text = lambda _ticket: "онлайн"
    panel._escape_html = lambda value: str(value)

    html = panel._build_ticket_meta_html(
        {
            "status": "in_progress",
            "requester_display_name": "Фигаро",
            "priority_class": "P0",
            "queue_code": "servicedesk_l1",
            "assignee_id": "op1",
            "first_response_due_at": "2026-05-08T14:15:00+05:00",
            "resolution_due_at": "2026-05-08T16:00:00+05:00",
            "description": "Не открывается портал",
            "custom_fields": {
                "request_form_title": "Проблема с сайтом",
                "request_form_summary": [{"label": "URL сайта", "value": "portal.company.local"}],
            },
        }
    )

    assert "Что сейчас происходит" in html
    assert "Следующее действие" in html
    assert "Специалист" in html
    assert "Форма" in html
    assert "Проблема с сайтом" in html
    assert "servicedesk_l1" not in html
    assert "P0" not in html
    assert "Очередь" not in html
    assert "Приоритет" not in html


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


def test_build_ticket_deadlines_status_summary_explains_stopped_sla():
    summary = build_ticket_deadlines_status_summary(
        {
            "priority_class": "P3",
            "first_response_due_at": "2026-05-04T16:20:20+00:00",
            "first_response_at": "2026-05-04T14:20:22+00:00",
            "resolution_due_at": "2026-05-05T14:20:20+00:00",
            "resolution_at": "2026-05-04T14:25:38+00:00",
            "status": "closed",
        }
    )

    assert "Приоритет: P3" in summary
    assert "Ответ получен" in summary
    assert "Решение выполнено" in summary
    assert "без нарушения" in summary


def test_build_ticket_diagnostics_user_summary_explains_priority_skip():
    ticket = {
        "priority_class": "P3",
        "custom_fields": {
            "diagnostic_consent": {"required": True, "granted": True},
        },
    }
    events = [
        {
            "event_type": "diagnostic_autorun_skipped",
            "payload": {
                "reason": "priority_not_allowed",
                "priority_class": "P3",
                "playbook_key": "diagnose.website",
                "consent_required": True,
                "consent_granted": True,
            },
        }
    ]

    summary = build_ticket_diagnostics_user_summary(ticket, events)

    assert "Диагностика" in summary
    assert "не запускалась автоматически" in summary
    assert "приоритет P3" in summary
    assert "Согласие получено" in summary


def test_format_event_text_localizes_status_and_diagnostic_events():
    panel = ChatPanel.__new__(ChatPanel)

    status_text = panel._format_event_text(
        {
            "event_type": "status_changed",
            "payload": {
                "from_status": "queued",
                "to_status": "in_progress",
                "actor_role": "support",
                "actor_id": "op1",
            },
        }
    )
    diagnostic_text = panel._format_event_text(
        {
            "event_type": "diagnostic_autorun_skipped",
            "payload": {
                "reason": "priority_not_allowed",
                "priority_class": "P3",
                "playbook_key": "diagnose.website",
            },
        }
    )

    assert "Статус изменён" in status_text
    assert "В работе" in status_text
    assert "op1" in status_text
    assert "Диагностика" in diagnostic_text
    assert "приоритет P3" in diagnostic_text


def test_ticket_status_label_is_localized():
    assert ticket_status_label("queued") == "Заявка принята"
    assert ticket_status_label("waiting_user") == "Нужен ваш ответ"
    assert ticket_status_label("waiting_on_user") == "Нужен ваш ответ"
    assert ticket_status_label("waiting_internal") == "Передано профильному специалисту"
    assert ticket_status_label("closed") == "Закрыта"


def test_ticket_due_labels_are_local_and_requester_friendly():
    now = datetime.fromisoformat("2026-05-08T13:45:00+05:00")

    assert format_due_label("2026-05-08T14:15:00+05:00", now=now) == "Сегодня, до 14:15"
    assert format_due_label("2026-05-09T10:00:00+05:00", now=now) == "Завтра, до 10:00"
    assert format_datetime_local("2026-05-10T13:48:00+05:00", now=now) == "10.05.2026 13:48"


def test_build_next_action_view_model_for_core_statuses():
    queued = build_next_action_view_model(
        {
            "status": "queued",
            "first_response_due_at": "2026-05-08T14:15:00+05:00",
            "resolution_due_at": "2026-05-08T16:00:00+05:00",
        },
        now=datetime.fromisoformat("2026-05-08T13:45:00+05:00"),
    )
    assert queued.title == "Ожидаем специалиста"
    assert queued.first_response_text == "Сегодня, до 14:15"
    assert queued.resolution_text == "Сегодня, до 16:00"

    waiting_user = build_next_action_view_model({"status": "waiting_user"})
    assert waiting_user.title == "Нужен ваш ответ"
    assert waiting_user.primary_action_label == "Ответить"

    resolved = build_next_action_view_model({"status": "resolved"})
    assert resolved.title == "Решение предложено"
    assert resolved.primary_action_label == "Да, всё работает"
    assert resolved.secondary_action_label == "Нет, проблема осталась"


def test_build_next_action_view_model_uses_server_next_action_and_first_response_fact():
    model = build_next_action_view_model(
        {
            "status": "queued",
            "next_action_owner": "support",
            "first_response_at": "2026-05-08T13:48:00+05:00",
            "first_response_due_at": "2026-05-08T13:48:00+05:00",
            "resolution_due_at": "2026-05-08T17:33:00+05:00",
        },
        now=datetime.fromisoformat("2026-05-08T14:00:00+05:00"),
    )

    assert model.title == "Сейчас на стороне поддержки"
    assert "Первый ответ уже получен" in model.description
    assert "Ожидаем специалиста" not in model.title


def test_ticket_info_panel_marks_first_response_done_when_server_sends_fact():
    from ui_gui.ticket_view_models import build_ticket_info_panel_view_model

    model = build_ticket_info_panel_view_model(
        {
            "created_at": "2026-05-08T13:00:00+05:00",
            "first_response_at": "2026-05-08T13:48:00+05:00",
            "first_response_due_at": "2026-05-08T13:48:00+05:00",
            "resolution_due_at": "2026-05-08T17:33:00+05:00",
        },
        now=datetime.fromisoformat("2026-05-08T14:00:00+05:00"),
    )

    assert model.first_response_text == "Получен: 13:48"
    assert model.first_response_progress == 100
    assert model.first_response_remaining_text == "Первый ответ получен"


def test_map_ticket_event_to_user_timeline_item_hides_internal_and_maps_diagnostics():
    assert map_ticket_event_to_user_timeline_item({"event_type": "internal_note"}) is None

    started = map_ticket_event_to_user_timeline_item(
        {"event_type": "tool_call_started", "created_at": "2026-05-08T13:47:00+05:00"}
    )
    assert started is not None
    assert started.kind == "system_event"
    assert started.text == "Специалист запустил диагностику."

    result = map_ticket_event_to_user_timeline_item(
        {
            "event_type": "tool_call_result",
            "created_at": "2026-05-08T13:48:00+05:00",
            "payload": {
                "checks": [
                    {"name": "DNS", "status": "ok"},
                    {"name": "HTTP", "status": "error", "message": "502 Bad Gateway"},
                ]
            },
        }
    )
    assert result is not None
    assert result.kind == "diagnostic_result"
    assert result.text == "Выполнена диагностика"
    assert result.payload["checks"][1]["label"] == "HTTP"
    assert result.payload["checks"][1]["summary"] == "502 Bad Gateway"

    attachment = map_ticket_event_to_user_timeline_item(
        {
            "event_type": "attachment_uploaded",
            "created_at": "2026-05-08T13:49:00+05:00",
            "payload": {
                "file_name": "browser-error.png",
                "size_bytes": 158 * 1024,
                "download_url": "https://support.example/attachments/raw-token",
            },
        }
    )
    assert attachment is not None
    assert attachment.kind == "attachment"
    assert attachment.text == "Файл приложен"
    assert attachment.payload["name"] == "browser-error.png"
    assert attachment.payload["size_label"] == "158 КБ"
    assert "raw-token" not in attachment.text


def test_map_ticket_event_to_user_timeline_item_uses_clear_status_messages_and_hides_noop_updates():
    in_progress = map_ticket_event_to_user_timeline_item(
        {
            "event_type": "status_changed",
            "created_at": "2026-05-08T13:50:00+05:00",
            "to_status": "in_progress",
        }
    )
    assert in_progress is not None
    assert in_progress.text == "Специалист взял обращение в работу."
    assert "unknown" not in in_progress.text.lower()

    queued_update = map_ticket_event_to_user_timeline_item(
        {
            "event_type": "ticket_updated",
            "created_at": "2026-05-08T13:51:00+05:00",
            "payload": {"technical_refresh": True},
        }
    )
    assert queued_update is None

    debug_event = map_ticket_event_to_user_timeline_item(
        {
            "event_type": "raw_tool_log",
            "created_at": "2026-05-08T13:52:00+05:00",
            "payload": {"text": "event_type=raw_tool_log status=unknown token=secret"},
        }
    )
    assert debug_event is None


def test_map_ticket_event_to_user_timeline_item_prefers_server_projection():
    item = map_ticket_event_to_user_timeline_item(
        {
            "event_type": "status_changed",
            "created_at": "2026-05-08T13:53:00+05:00",
            "to_status": "unknown",
            "requester_timeline_text": "Статус обращения обновлён.",
            "requester_timeline_kind": "system_event",
            "requester_timeline_payload": {"source": "server"},
        }
    )

    assert item is not None
    assert item.kind == "system_event"
    assert item.text == "Статус обращения обновлён."
    assert item.payload == {"source": "server"}
    assert "unknown" not in item.text.lower()


def test_next_action_card_renders_only_next_action_without_duplicate_due_dates():
    from ui_gui.ticket_detail_widgets import NextActionCard

    app = QApplication.instance() or QApplication([])
    card = NextActionCard()
    model = build_next_action_view_model(
        {
            "status": "resolved",
            "first_response_due_at": "2026-05-08T14:15:00+05:00",
            "resolution_due_at": "2026-05-08T16:00:00+05:00",
        },
        now=datetime.fromisoformat("2026-05-08T13:45:00+05:00"),
    )

    card.set_view_model(model)

    assert app is not None
    assert card.objectName() == "NextActionCard"
    assert card.title_label.text() == "Решение предложено"
    assert "Проверьте" in card.description_label.text()
    assert "Сегодня, до 14:15" not in card.findChild(QLabel, "NextActionDueText").text()
    assert "Сегодня, до 16:00" not in card.findChild(QLabel, "NextActionDueText").text()
    assert card.primary_button.text() == "Да, всё работает"
    assert card.secondary_button.text() == "Нет, проблема осталась"


def test_next_action_card_uses_compact_layout_for_ticket_detail():
    from ui_gui.ticket_detail_widgets import NextActionCard

    source = inspect.getsource(NextActionCard.__init__)
    app = QApplication.instance() or QApplication([])
    card = NextActionCard()

    assert app is not None
    assert "root.setContentsMargins(14, 10, 14, 10)" in source
    assert "self.icon_label.setFixedSize(40, 40)" in source
    assert card.icon_label.width() == 40


def test_ticket_detail_status_styles_use_qss_properties_instead_of_inline_status_qss():
    from ui_gui.ticket_detail_widgets import NextActionCard, TicketHeaderWidget
    from ui_gui.ticket_view_models import NextActionViewModel, TicketHeaderViewModel

    app = QApplication.instance() or QApplication([])
    next_card = NextActionCard()
    next_card.set_view_model(NextActionViewModel(title="Нужен ответ", description="Ответьте ниже.", style="warning"))
    header = TicketHeaderWidget()
    header.set_view_model(
        TicketHeaderViewModel(
            number_text="#T-000520",
            title="Проблема с сайтом",
            status_label="Нужен ваш ответ",
            status_style="warning",
        )
    )
    next_source = inspect.getsource(NextActionCard._apply_style)
    header_source = inspect.getsource(TicketHeaderWidget._apply_styles)
    qss = theme.requester_helpdesk_stylesheet()

    assert app is not None
    assert ".setStyleSheet(" not in next_source
    assert ".setStyleSheet(" not in header_source
    assert next_card.property("nextActionStyle") == "warning"
    assert next_card.icon_label.property("nextActionStyle") == "warning"
    assert header.status_badge.property("statusStyle") == "warning"
    assert 'nextActionStyle="warning"' in qss
    assert 'statusStyle="warning"' in qss


def test_chat_panel_wires_next_action_card_into_detail_header():
    setup_source = inspect.getsource(chat_panel_module.ChatPanel._setup_chat_screen)
    header_source = inspect.getsource(chat_panel_module.ChatPanel._apply_ticket_detail_header)

    assert "NextActionCard" in setup_source
    assert "self.next_action_card" in setup_source
    assert "build_next_action_view_model(ticket)" in header_source
    assert "self.next_action_card.set_view_model" in header_source


def test_ticket_header_view_model_uses_number_title_status_and_access_actions():
    from ui_gui.ticket_view_models import build_ticket_header_view_model

    model = build_ticket_header_view_model(
        {
            "ticket_code": "T-000520",
            "title": "Проблема с сайтом",
            "status": "in_progress",
            "public_access_url": "https://support.example/t/T-000520",
        },
        access_code="RZ76RPDR",
    )

    assert model.number_text == "#T-000520"
    assert model.title == "Проблема с сайтом"
    assert model.status_label == "В работе"
    assert model.access_code == "RZ76RPDR"
    assert model.public_url == "https://support.example/t/T-000520"


def test_ticket_header_widget_renders_actions_without_raw_public_url():
    from ui_gui.ticket_detail_widgets import TicketHeaderWidget
    from ui_gui.ticket_view_models import build_ticket_header_view_model

    app = QApplication.instance() or QApplication([])
    widget = TicketHeaderWidget()
    widget.set_view_model(
        build_ticket_header_view_model(
            {
                "ticket_code": "T-000520",
                "title": "Поломка",
                "status": "queued",
                "public_access_url": "https://support.example/t/T-000520",
            },
            access_code="RZ76RPDR",
        )
    )

    assert app is not None
    assert widget.objectName() == "TicketHeaderWidget"
    assert widget.title_label.text() == "#T-000520 · Поломка"
    assert widget.status_badge.text() == "Заявка принята"
    assert widget.actions_button.text() == "Действия"
    assert widget.copy_code_action.text() == "Скопировать код доступа"
    assert widget.open_url_action.text() == "Открыть в браузере"
    assert widget.attach_action.text() == "Приложить файл"
    assert widget.refresh_action.text() == "Обновить статус"
    assert "support.example" not in widget.title_label.text()


def test_ticket_header_actions_include_resolved_resolution_choices():
    from ui_gui.ticket_detail_widgets import TicketHeaderWidget
    from ui_gui.ticket_view_models import build_ticket_header_view_model

    app = QApplication.instance() or QApplication([])
    widget = TicketHeaderWidget()
    widget.set_view_model(
        build_ticket_header_view_model(
            {
                "ticket_code": "T-000520",
                "title": "Проблема с сайтом",
                "status": "resolved",
            }
        )
    )

    assert app is not None
    assert widget.confirm_resolution_action.text() == "Да, всё работает"
    assert widget.reject_resolution_action.text() == "Нет, проблема осталась"
    assert widget.confirm_resolution_action.isVisible()
    assert widget.reject_resolution_action.isVisible()

    widget.set_view_model(
        build_ticket_header_view_model(
            {
                "ticket_code": "T-000520",
                "title": "Проблема с сайтом",
                "status": "in_progress",
            }
        )
    )

    assert not widget.confirm_resolution_action.isVisible()
    assert not widget.reject_resolution_action.isVisible()


def test_chat_panel_wires_ticket_header_into_detail_header():
    setup_source = inspect.getsource(chat_panel_module.ChatPanel._setup_chat_screen)
    header_source = inspect.getsource(chat_panel_module.ChatPanel._apply_ticket_detail_header)

    assert "TicketHeaderWidget" in setup_source
    assert "self.ticket_header" in setup_source
    assert "build_ticket_header_view_model(ticket" in header_source
    assert "self.ticket_header.set_view_model" in header_source
    assert "self.ticket_header.copyCodeRequested.connect(self._copy_access_code)" in setup_source
    assert "self.ticket_header.attachRequested.connect(self._on_attach_any_file)" in setup_source
    assert "self.ticket_header.confirmResolutionRequested.connect" in setup_source
    assert "self.ticket_header.rejectResolutionRequested.connect(self._on_reject_resolution)" in setup_source


def test_ticket_info_panel_view_model_uses_requester_deadlines_access_and_device():
    from ui_gui.ticket_view_models import build_ticket_info_panel_view_model

    model = build_ticket_info_panel_view_model(
        {
            "requester_display_name": "Фигаро",
            "requester_profile": {
                "full_name": "Фигаро Фигаро",
                "building": "Москва",
                "room": "501",
                "phone": "+7 (999) 123-45-67",
            },
            "assignee_display_name": "Иван Петров",
            "first_response_due_at": "2026-05-08T14:15:00+05:00",
            "resolution_due_at": "2026-05-08T16:00:00+05:00",
            "sla_status": "ok",
            "public_access_url": "https://support.example/t/T-000521?raw=1",
            "device": {
                "hostname": "FIGARO-WIN10",
                "os_name": "Windows",
                "os_version": "10 Pro",
                "agent_online": True,
                "last_seen_at": "2026-05-08T13:48:30+05:00",
            },
        },
        access_code="RZ76RPDR",
        now=datetime.fromisoformat("2026-05-08T13:45:00+05:00"),
    )

    assert model.requester_name == "Фигаро Фигаро"
    assert model.room == "Москва, кабинет 501"
    assert model.phone == "+7 (999) 123-45-67"
    assert model.assignee_name == "Иван Петров"
    assert model.first_response_text == "Сегодня, до 14:15"
    assert model.resolution_text == "Сегодня, до 16:00"
    assert 0 <= model.first_response_progress <= 100
    assert 0 <= model.resolution_progress <= 100
    assert model.first_response_remaining_text
    assert model.resolution_remaining_text
    assert model.sla_status_text == "Без нарушения"
    assert model.access_code == "RZ76RPDR"
    assert model.public_url == "https://support.example/t/T-000521?raw=1"
    assert model.device_name == "FIGARO-WIN10"
    assert model.os_text == "Windows 10 Pro"
    assert model.agent_status_text == "Онлайн"
    assert model.show_device is True
    assert model.last_contact_text == "08.05.2026 13:48"


def test_ticket_right_info_panel_renders_visual_sla_without_raw_url_text():
    from ui_gui.ticket_detail_widgets import TicketRightInfoPanel
    from ui_gui.ticket_view_models import build_ticket_info_panel_view_model

    app = QApplication.instance() or QApplication([])
    panel = TicketRightInfoPanel()
    panel.set_view_model(
        build_ticket_info_panel_view_model(
            {
                "requester_display_name": "Фигаро",
                "requester_profile": {"room": "501"},
                "assignee_id": "op1",
                "first_response_due_at": "2026-05-08T14:15:00+05:00",
                "resolution_due_at": "2026-05-08T16:00:00+05:00",
                "public_access_url": "https://support.example/t/T-000521",
                "created_at": "2026-05-08T13:00:00+05:00",
            },
            access_code="RZ76RPDR",
            now=datetime.fromisoformat("2026-05-08T13:45:00+05:00"),
        )
    )

    assert app is not None
    assert panel.objectName() == "TicketRightInfoPanel"
    assert panel.requester_value.text() == "Фигаро"
    assert panel.assignee_value.text() == "op1"
    assert panel.room_value.text() == "кабинет 501"
    assert panel.first_response_value.text() == "Сегодня, до 14:15"
    assert panel.resolution_value.text() == "Сегодня, до 16:00"
    assert panel.first_response_progress.objectName() == "SlaProgressBar"
    assert panel.resolution_progress.objectName() == "SlaProgressBar"
    assert panel.first_response_progress.value() > 0
    assert panel.resolution_progress.value() > 0
    assert panel.access_code_value.text() == "RZ76RPDR"
    assert "support.example" not in panel.access_code_value.text()
    assert not panel.device_card.isVisible()
    assert panel.copy_code_button.text() == "Скопировать код"
    assert panel.open_url_button.text() == "Открыть в браузере"


def test_ticket_info_panel_does_not_mark_missing_device_as_offline():
    from ui_gui.ticket_view_models import build_ticket_info_panel_view_model

    model = build_ticket_info_panel_view_model(
        {
            "requester_display_name": "Фигаро",
            "first_response_due_at": "2026-05-08T14:15:00+05:00",
            "resolution_due_at": "2026-05-08T16:00:00+05:00",
        },
        now=datetime.fromisoformat("2026-05-08T13:45:00+05:00"),
    )

    assert model.show_device is False
    assert model.agent_status_text == "—"


def test_chat_panel_wires_right_info_panel_into_detail_header():
    setup_source = inspect.getsource(chat_panel_module.ChatPanel._setup_chat_screen)
    header_source = inspect.getsource(chat_panel_module.ChatPanel._apply_ticket_detail_header)

    assert "TicketRightInfoPanel" in setup_source
    assert "self.ticket_info_panel" in setup_source
    assert "main_layout.addWidget(self.ticket_info_panel" in setup_source
    assert "build_ticket_info_panel_view_model(ticket" in header_source
    assert "self.ticket_info_panel.set_view_model" in header_source


def test_timeline_item_widget_renders_diagnostic_result_without_raw_event_type():
    from ui_gui.ticket_detail_widgets import TimelineItemWidget
    from ui_gui.ticket_view_models import TimelineItem

    app = QApplication.instance() or QApplication([])
    widget = TimelineItemWidget(
        TimelineItem(
            id="evt-1",
            kind="diagnostic_result",
            actor_label="Система",
            time_label="13:48",
            text="Выполнена диагностика",
            payload={
                "checks": [
                    {"label": "DNS", "status": "ok", "summary": "OK"},
                    {"label": "HTTP", "status": "error", "summary": "502 Bad Gateway"},
                ]
            },
        )
    )

    assert app is not None
    assert widget.objectName() == "TimelineDiagnosticResult"
    assert widget.title_label.text() == "Выполнена диагностика"
    assert widget.subtitle_label.text() == ""
    assert not widget.subtitle_label.isVisible()
    rendered = " ".join(label.text() for label in widget.check_labels)
    assert "DNS" in rendered
    assert "HTTP" in rendered
    assert "502 Bad Gateway" in rendered
    assert "tool_call_result" not in rendered


def test_timeline_item_widget_renders_attachment_card_without_raw_url():
    from ui_gui.ticket_detail_widgets import TimelineItemWidget
    from ui_gui.ticket_view_models import TimelineItem

    app = QApplication.instance() or QApplication([])
    widget = TimelineItemWidget(
        TimelineItem(
            id="att-1",
            kind="attachment",
            actor_label="Вы",
            time_label="13:49",
            text="Файл приложен",
            payload={
                "name": "browser-error.png",
                "size_label": "158 КБ",
                "url": "https://support.example/raw-token",
            },
        )
    )

    assert app is not None
    assert widget.objectName() == "TimelineAttachment"
    assert widget.title_label.text() == "Файл приложен"
    assert widget.attachment_name_label.text() == "browser-error.png"
    assert widget.attachment_size_label.text() == "158 КБ"
    assert widget.open_attachment_button.text() == "Открыть"
    assert "support.example" not in widget.attachment_name_label.text()
    assert "raw-token" not in widget.attachment_size_label.text()


def test_timeline_item_widget_renders_user_and_support_message_bubbles():
    from ui_gui.ticket_detail_widgets import TimelineItemWidget
    from ui_gui.ticket_view_models import TimelineItem

    app = QApplication.instance() or QApplication([])
    user_widget = TimelineItemWidget(
        TimelineItem(
            id="msg-1",
            kind="user_message",
            actor_label="Вы",
            time_label="13:41",
            text="Здравствуйте! Не открывается портал.",
            payload={},
        )
    )
    support_widget = TimelineItemWidget(
        TimelineItem(
            id="msg-2",
            kind="support_message",
            actor_label="Иван, специалист поддержки",
            time_label="13:44",
            text="Начинаю проверку, это займет несколько минут.",
            payload={},
        )
    )

    assert app is not None
    assert user_widget.objectName() == "TimelineUserMessage"
    assert support_widget.objectName() == "TimelineSupportMessage"
    assert user_widget.message_actor_label.text() == "Вы"
    assert support_widget.message_actor_label.text() == "Иван, специалист поддержки"
    assert user_widget.message_text_label.text() == "Здравствуйте! Не открывается портал."
    assert support_widget.message_text_label.text() == "Начинаю проверку, это займет несколько минут."
    assert user_widget.time_label.text() == "13:41"
    assert support_widget.time_label.text() == "13:44"
    assert not user_widget.subtitle_label.isVisible()
    assert not support_widget.subtitle_label.isVisible()


def test_chat_panel_build_timeline_items_uses_requester_safe_event_mapper():
    panel = ChatPanel.__new__(ChatPanel)
    panel.local_action_buffer = {}
    panel.active_ticket_id = "ticket-1"

    items = panel._build_timeline_items(
        {"ticket_id": "ticket-1"},
        [],
        [
            {"event_type": "internal_note", "created_at": "2026-05-08T13:46:00+05:00"},
            {"event_type": "tool_call_started", "created_at": "2026-05-08T13:47:00+05:00"},
            {
                "event_type": "tool_call_result",
                "created_at": "2026-05-08T13:48:00+05:00",
                "payload": {"checks": [{"name": "HTTP", "status": "error", "message": "502 Bad Gateway"}]},
            },
        ],
    )

    texts = [payload["text"] for _sort, _kind, payload in items]
    assert len(items) == 2
    assert "Специалист запустил диагностику." in texts
    assert "Выполнена диагностика" in texts
    assert all("tool_call" not in text for text in texts)
    diagnostic_payload = next(payload for _sort, _kind, payload in items if payload["text"] == "Выполнена диагностика")
    assert diagnostic_payload["timeline_item"]["kind"] == "diagnostic_result"
    assert diagnostic_payload["timeline_item"]["payload"]["checks"][0]["summary"] == "502 Bad Gateway"


def test_chat_panel_wires_timeline_item_widget_for_mapped_events():
    append_source = (
        inspect.getsource(chat_panel_module.ChatPanel._append_timeline_widgets)
        + inspect.getsource(chat_panel_module.ChatPanel._create_timeline_widget)
    )
    build_source = inspect.getsource(chat_panel_module.ChatPanel._build_timeline_items)

    assert "map_ticket_event_to_user_timeline_item" in build_source
    assert "TimelineItemWidget" in append_source
    assert "timeline_item" in append_source


def test_chat_panel_uses_header_resolution_confirmation_only():
    setup_source = inspect.getsource(chat_panel_module.ChatPanel._setup_chat_screen)
    prompt_source = inspect.getsource(chat_panel_module.ChatPanel._maybe_prompt_resolution_confirmation)

    assert "resolution_message_widget" not in setup_source
    assert "Подтвердить и закрыть" not in setup_source
    assert ".show()" not in prompt_source


def test_chat_panel_detail_layout_removes_legacy_left_meta_and_raw_access_panel():
    setup_source = inspect.getsource(chat_panel_module.ChatPanel._setup_chat_screen)

    assert "main_layout.addWidget(self.left_panel)" not in setup_source
    assert "center_layout.addWidget(self.top_pinned_info)" not in setup_source
    assert "self.left_panel.hide()" in setup_source
    assert "self.top_pinned_info.hide()" in setup_source
    assert "main_layout.addWidget(self.right_center, 3)" in setup_source
    assert "main_layout.addWidget(self.ticket_info_panel" in setup_source


def test_chat_panel_aligns_mapped_user_and_support_message_events_like_chat_bubbles():
    assert (
        ChatPanel._timeline_alignment_for_payload(
            "event",
            {"timeline_item": {"kind": "user_message", "actor_label": "Вы", "text": "Вопрос"}},
        )
        == "right"
    )
    assert (
        ChatPanel._timeline_alignment_for_payload(
            "event",
            {
                "timeline_item": {
                    "kind": "support_message",
                    "actor_label": "Иван, специалист поддержки",
                    "text": "Проверяю",
                }
            },
        )
        == "left"
    )
    assert ChatPanel._timeline_alignment_for_payload("event", {"timeline_item": {"kind": "system_event"}}) == "center"
    assert ChatPanel._timeline_alignment_for_payload("message", {"bubble_role": "support"}) == "right"
    assert ChatPanel._timeline_alignment_for_payload("message", {"bubble_role": "self"}) == "left"


def test_ticket_composer_widget_controls_send_and_terminal_state():
    from ui_gui.ticket_detail_widgets import TicketComposerWidget

    app = QApplication.instance() or QApplication([])
    composer = TicketComposerWidget()

    assert app is not None
    assert composer.objectName() == "TicketComposerWidget"
    assert composer.message_edit.placeholderText() == "Напишите сообщение специалисту..."
    assert composer.attach_button.text() == "Прикрепить файл"
    assert composer.media_button.text() == "Скриншот / Видео"
    assert composer.send_button.text() == "Отправить"
    assert not composer.send_button.isEnabled()

    composer.set_ticket_state(active=True, ticket_status="in_progress", connected=True)
    assert composer.message_edit.isEnabled()
    assert composer.attach_button.isEnabled()
    assert composer.media_button.isEnabled()
    assert not composer.send_button.isEnabled()

    composer.message_edit.setPlainText("Здравствуйте\nНужна помощь")
    assert composer.message_text() == "Здравствуйте\nНужна помощь"
    assert composer.send_button.isEnabled()

    composer.set_ticket_state(active=True, ticket_status="closed", connected=True)
    assert not composer.message_edit.isEnabled()
    assert not composer.attach_button.isEnabled()
    assert not composer.media_button.isEnabled()
    assert not composer.send_button.isEnabled()


def test_chat_panel_wires_ticket_composer_without_changing_send_paths():
    setup_source = inspect.getsource(chat_panel_module.ChatPanel._setup_chat_screen)
    send_source = inspect.getsource(chat_panel_module.ChatPanel._on_send)
    async_send_source = inspect.getsource(chat_panel_module.ChatPanel._async_send_message)
    header_source = inspect.getsource(chat_panel_module.ChatPanel._apply_ticket_detail_header)

    assert "TicketComposerWidget" in setup_source
    assert "self.composer.sendRequested.connect(self._on_send)" in setup_source
    assert "self.input_line = self.composer.message_edit" in setup_source
    assert "self.send_btn = self.composer.send_button" in setup_source
    assert "self._composer_text()" in send_source
    assert "self.ticket_client.send_message" in async_send_source
    assert "self._refresh_composer_state()" in header_source


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
