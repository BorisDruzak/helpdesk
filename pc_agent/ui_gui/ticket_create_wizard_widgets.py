"""Reusable widgets for the requester-facing ticket creation wizard."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from typing import Any

from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from . import theme


class CreateTicketProgressBar(QFrame):
    """Compact four-step progress indicator for the create-ticket wizard."""

    stepRequested = Signal(int)

    def __init__(self, labels: list[str], parent=None) -> None:
        super().__init__(parent)
        self._labels = list(labels)
        self.step_buttons: list[QPushButton] = []
        self.setObjectName("CreateTicketProgressBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for index, label in enumerate(self._labels):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName("WizardStepButton")
            button.clicked.connect(lambda _checked=False, step=index: self.stepRequested.emit(step))
            layout.addWidget(button, 1)
            self.step_buttons.append(button)

    def set_state(self, *, current_step: int, unlocked_steps: set[int], completed_steps: set[int]) -> None:
        for index, button in enumerate(self.step_buttons):
            label = self._labels[index]
            if index in completed_steps:
                button.setText(f"✓ {label}")
            else:
                button.setText(f"{index + 1}. {label}")
            button.setEnabled(index in unlocked_steps)
            button.setChecked(index == current_step)
            if index == current_step:
                state = "current"
            elif index in completed_steps:
                state = "completed"
            elif index in unlocked_steps:
                state = "available"
            else:
                state = "locked"
            button.setProperty("wizardState", state)
            theme.refresh_qss_state(button)


class CreateTicketTypeGrid(QFrame):
    """Card grid for choosing the requester-visible ticket type/template."""

    typeSelected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.card_buttons: list[QPushButton] = []
        self._templates: list[dict[str, Any]] = []
        self.setObjectName("CreateTicketTypeGrid")
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(10)
        self._layout.setVerticalSpacing(10)

    def set_templates(self, templates: list[dict[str, Any]], *, current_key: str = "") -> None:
        self._templates = [item for item in templates if isinstance(item, dict)]
        while self._layout.count():
            child = self._layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        self.card_buttons.clear()
        for index, template in enumerate(self._templates):
            key = str(template.get("key") or "").strip()
            title = self._template_title(template)
            description = self._template_description(template)
            button = QPushButton(f"{title}\n{description}")
            button.setCheckable(True)
            button.setObjectName("TicketTypeCard")
            button.setAccessibleName(f"ticket-type-card:{key}")
            button.setAccessibleDescription(title)
            button.setMinimumHeight(104)
            button.setToolTip(description)
            button.clicked.connect(lambda _checked=False, value=key: self.typeSelected.emit(value))
            self._layout.addWidget(button, index // 3, index % 3)
            self.card_buttons.append(button)
        self.set_selected_key(current_key)

    def set_selected_key(self, current_key: Any) -> None:
        target = str(current_key or "").strip()
        for button, template in zip(self.card_buttons, self._templates):
            selected = str(template.get("key") or "").strip() == target
            button.setChecked(selected)
            button.setProperty("ticketTypeSelected", selected)
            theme.refresh_qss_state(button)

    @staticmethod
    def _template_title(template: dict[str, Any]) -> str:
        return str(
            template.get("request_template_title")
            or template.get("title")
            or template.get("category_label")
            or template.get("key")
            or "Обращение"
        ).strip()

    @staticmethod
    def _template_description(template: dict[str, Any]) -> str:
        description = str(template.get("description") or "").strip()
        if description:
            return description
        normalized = " ".join(
            str(template.get(key) or "").casefold()
            for key in ("key", "category", "ticket_type", "request_kind", "title", "request_template_title")
        )
        if "site" in normalized or "web" in normalized or "сайт" in normalized:
            return "Сайт или веб-сервис не загружается, работает некорректно или недоступен."
        if "printer" in normalized or "print" in normalized or "принтер" in normalized:
            return "Проблемы с печатью, сканированием или работой принтера."
        if "access" in normalized or "доступ" in normalized:
            return "Нет доступа к системе, файлам или функциям. Нужны права или роли."
        if "software" in normalized or "install" in normalized or "установка" in normalized:
            return "Нужно установить программу или настроить программное обеспечение."
        if "consult" in normalized or "консульта" in normalized:
            return "Вопрос по работе сервисов, систем или оборудования."
        return "Что-то не работает или требует помощи специалиста поддержки."


class CreateTicketConfirmationPanel(QFrame):
    """Requester-facing summary before the final submit confirmation dialog."""

    confirmedChanged = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CreateTicketConfirmationPanel")
        self.setStyleSheet(
            theme.chat_panel_stylesheet()
            + theme.profile_sidebar_stylesheet()
            + theme.requester_helpdesk_stylesheet()
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title = QLabel("Проверьте данные обращения")
        title.setObjectName("ProfileSidebarTitle")
        layout.addWidget(title)

        self.category_value = self._add_row(layout, "Категория")
        self.subject_value = self._add_row(layout, "Краткое описание")
        self.requester_value = self._add_row(layout, "Инициатор")
        self.impact_value = self._add_row(layout, "Влияние")
        self.urgency_value = self._add_row(layout, "Срочность")
        self.description_value = self._add_row(layout, "Описание проблемы")
        self.attachments_value = self._add_row(layout, "Вложения")
        self.process_value = self._add_row(layout, "Как будет создано обращение")

    def _add_row(self, parent: QVBoxLayout, label: str) -> QLabel:
        card = QFrame()
        card.setObjectName("InfoCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(4)
        label_widget = QLabel(label)
        label_widget.setObjectName("ProfileFieldLabel")
        value_widget = QLabel("—")
        value_widget.setObjectName("ProfileHint")
        value_widget.setWordWrap(True)
        card_layout.addWidget(label_widget)
        card_layout.addWidget(value_widget)
        parent.addWidget(card)
        return value_widget

    def set_summary(
        self,
        *,
        category: str,
        subject: str,
        requester: str,
        impact: str,
        urgency: str,
        description: str,
        attachments: list[str],
        process_preview: str,
    ) -> None:
        self.category_value.setText(category.strip() or "Не выбрана")
        self.subject_value.setText(subject.strip() or "Будет сформировано из описания")
        self.requester_value.setText(requester.strip() or "Профиль не выбран")
        self.impact_value.setText(impact.strip() or "Не указано")
        self.urgency_value.setText(urgency.strip() or "Не указано")
        self.description_value.setText(description.strip() or "Описание пока не заполнено")
        self.attachments_value.setText(", ".join(item for item in attachments if item) or "Нет вложений")
        self.process_value.setText(process_preview.strip() or "Маршрут, приоритет и сроки будут рассчитаны при создании.")

    def set_confirmed(self, confirmed: bool) -> None:
        return None

    def is_confirmed(self) -> bool:
        return True


class CreateTicketSuccessPanel(QFrame):
    """Final wizard screen shown after a ticket is created."""

    openRequested = Signal()
    addMessageRequested = Signal()
    createAnotherRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._access_code = ""
        self.setObjectName("CreateTicketSuccessPanel")
        self.setStyleSheet(
            theme.chat_panel_stylesheet()
            + theme.profile_sidebar_stylesheet()
            + theme.requester_helpdesk_stylesheet()
        )

        palette = theme.current_palette()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.check_label = QLabel("✓")
        self.check_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.check_label.setObjectName("StatusBadge")
        self.check_label.setStyleSheet(
            f"font-size: 30px; font-weight: 800; color: {palette.status_online_fg}; "
            f"background: {palette.status_online_bg}; border-radius: 32px; min-width: 64px; min-height: 64px;"
        )
        layout.addWidget(self.check_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.title_label = QLabel("Обращение создано")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("ProfileSidebarTitle")
        layout.addWidget(self.title_label)

        self.ticket_number_label = QLabel("")
        self.ticket_number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ticket_number_label.setObjectName("ProfileSidebarTitle")
        self.ticket_number_label.setStyleSheet(
            f"font-size: 26px; font-weight: 800; color: {palette.primary_btn}; background: transparent;"
        )
        layout.addWidget(self.ticket_number_label)

        self.subject_label = QLabel("")
        self.subject_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subject_label.setObjectName("ProfileHint")
        self.subject_label.setWordWrap(True)
        layout.addWidget(self.subject_label)

        info_row = QHBoxLayout()
        info_row.setSpacing(10)
        self.access_card = self._build_info_card("Код доступа")
        self.first_response_card = self._build_info_card("Первый ответ")
        self.resolution_card = self._build_info_card("Решение")
        info_row.addWidget(self.access_card)
        info_row.addWidget(self.first_response_card)
        info_row.addWidget(self.resolution_card)
        layout.addLayout(info_row)

        self.access_code_label = QLabel("")
        self.access_code_label.setObjectName("ProfileSidebarTitle")
        self.access_code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.access_card.layout().addWidget(self.access_code_label)
        self.first_response_label = QLabel("")
        self.first_response_label.setWordWrap(True)
        self.first_response_label.setObjectName("ProfileHint")
        self.first_response_card.layout().addWidget(self.first_response_label)
        self.resolution_label = QLabel("")
        self.resolution_label.setWordWrap(True)
        self.resolution_label.setObjectName("ProfileHint")
        self.resolution_card.layout().addWidget(self.resolution_label)

        self.next_action_label = QLabel("")
        self.next_action_label.setWordWrap(True)
        self.next_action_label.setObjectName("ProfileHint")
        layout.addWidget(self.next_action_label)

        self.deadline_label = QLabel("")
        self.deadline_label.setWordWrap(True)
        self.deadline_label.setObjectName("ProfileHint")
        layout.addWidget(self.deadline_label)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setObjectName("ProfileHint")
        layout.addWidget(self.result_label)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.open_created_ticket_btn = QPushButton("Открыть обращение")
        self.open_created_ticket_btn.setObjectName("PrimaryButton")
        self.open_created_ticket_btn.clicked.connect(self.openRequested.emit)
        self.create_another_btn = QPushButton("Создать ещё одно")
        self.create_another_btn.setObjectName("SecondaryButton")
        self.create_another_btn.clicked.connect(self.createAnotherRequested.emit)
        self.copy_code_btn = QPushButton("Скопировать код")
        self.copy_code_btn.setObjectName("SecondaryButton")
        self.copy_code_btn.clicked.connect(self.copy_access_code)
        self.add_message_to_created_ticket_btn = QPushButton("Добавить сообщение")
        self.add_message_to_created_ticket_btn.setObjectName("SecondaryButton")
        self.add_message_to_created_ticket_btn.clicked.connect(self.addMessageRequested.emit)
        actions.addWidget(self.open_created_ticket_btn)
        actions.addWidget(self.create_another_btn)
        actions.addWidget(self.copy_code_btn)
        actions.addWidget(self.add_message_to_created_ticket_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

    def _build_info_card(self, title: str) -> QFrame:
        card = QFrame()
        card.setObjectName("InfoCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("ProfileFieldLabel")
        card_layout.addWidget(title_label)
        return card

    def set_result(
        self,
        *,
        ticket_number: str,
        title: str,
        access_code: str,
        next_action: str,
        deadlines: str,
        summary: str,
        has_ticket: bool,
    ) -> None:
        self._access_code = access_code.strip()
        self.ticket_number_label.setText(ticket_number.strip() or "Номер появится в обращении")
        self.subject_label.setText(title.strip() or "Обращение отправлено в службу поддержки")
        self.access_code_label.setText(self._access_code or "Будет показан после создания")
        self.next_action_label.setText(next_action.strip())
        self.deadline_label.setText(deadlines.strip())
        self.result_label.setText(summary.strip())
        self.first_response_label.setText(self._extract_sentence(deadlines, "ответить") or "Срок появится в обращении.")
        self.resolution_label.setText(
            self._extract_sentence(deadlines, "Решение")
            or self._extract_sentence(deadlines, "срок")
            or "Срок появится в обращении."
        )
        self.open_created_ticket_btn.setEnabled(has_ticket)
        self.add_message_to_created_ticket_btn.setEnabled(has_ticket)
        self.copy_code_btn.setEnabled(bool(self._access_code))

    def clear_result(self) -> None:
        self._access_code = ""
        for label in (
            self.ticket_number_label,
            self.subject_label,
            self.access_code_label,
            self.next_action_label,
            self.deadline_label,
            self.result_label,
            self.first_response_label,
            self.resolution_label,
        ):
            label.setText("")
        self.open_created_ticket_btn.setEnabled(False)
        self.add_message_to_created_ticket_btn.setEnabled(False)
        self.copy_code_btn.setEnabled(False)

    def copy_access_code(self) -> None:
        if self._access_code:
            QApplication.clipboard().setText(self._access_code)

    @staticmethod
    def _extract_sentence(text: str, marker: str) -> str:
        for sentence in (text or "").split("."):
            sentence = sentence.strip()
            if marker.casefold() in sentence.casefold():
                return sentence + "."
        return ""
