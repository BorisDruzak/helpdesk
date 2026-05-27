"""Qt widgets for the requester-facing ticket detail screen."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QProgressBar, QPushButton, QTextEdit, QToolButton, QVBoxLayout, QWidget

from . import theme
from .accessibility import set_uia_metadata
from .ticket_view_models import NextActionViewModel, TicketHeaderViewModel, TicketInfoPanelViewModel, TimelineItem


class NextActionCard(QFrame):
    """Large requester-facing card that explains the next ticket action."""

    primaryActionRequested = Signal()
    secondaryActionRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NextActionCard")

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(12)

        self.icon_label = QLabel("⌛")
        self.icon_label.setObjectName("NextActionIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(40, 40)
        root.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(3)
        self.kicker_label = QLabel("Следующее действие")
        self.kicker_label.setObjectName("CardKicker")
        self.title_label = QLabel("")
        self.title_label.setObjectName("CardTitle")
        self.title_label.setWordWrap(True)
        self.description_label = QLabel("")
        self.description_label.setObjectName("CardMeta")
        self.description_label.setWordWrap(True)
        text_col.addWidget(self.kicker_label)
        text_col.addWidget(self.title_label)
        text_col.addWidget(self.description_label)

        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 6, 0, 0)
        actions_row.setSpacing(8)
        self.primary_button = QPushButton("")
        self.primary_button.setObjectName("PrimaryButton")
        self.primary_button.clicked.connect(self.primaryActionRequested.emit)
        self.secondary_button = QPushButton("")
        self.secondary_button.setObjectName("SecondaryButton")
        self.secondary_button.clicked.connect(self.secondaryActionRequested.emit)
        actions_row.addWidget(self.primary_button)
        actions_row.addWidget(self.secondary_button)
        actions_row.addStretch(1)
        text_col.addLayout(actions_row)
        root.addLayout(text_col, 1)

        self.first_response_value = QLabel("", self)
        self.first_response_value.setObjectName("NextActionDueText")
        self.first_response_value.hide()
        self.resolution_value = QLabel("", self)
        self.resolution_value.setObjectName("NextActionDueText")
        self.resolution_value.hide()

        self.set_view_model(
            NextActionViewModel(
                title="Откройте обращение",
                description="Выберите обращение в списке, чтобы увидеть следующий шаг.",
            )
        )

    def set_view_model(self, model: NextActionViewModel) -> None:
        self.title_label.setText(model.title)
        self.description_label.setText(model.description)
        self.first_response_value.setText("")
        self.resolution_value.setText("")
        self.primary_button.setText(model.primary_action_label)
        self.primary_button.setVisible(bool(model.primary_action_label))
        self.secondary_button.setText(model.secondary_action_label)
        self.secondary_button.setVisible(bool(model.secondary_action_label))
        self._apply_style(model.style)

    def _apply_style(self, style: str) -> None:
        normalized = style if style in {"success", "warning", "danger", "info"} else "info"
        self.setProperty("nextActionStyle", normalized)
        self.icon_label.setProperty("nextActionStyle", normalized)
        theme.refresh_qss_state(self)
        theme.refresh_qss_state(self.icon_label)


class TicketHeaderWidget(QFrame):
    """Requester-facing ticket header with status badge and actions menu."""

    copyCodeRequested = Signal(str)
    openUrlRequested = Signal(str)
    attachRequested = Signal()
    refreshRequested = Signal()
    confirmResolutionRequested = Signal()
    rejectResolutionRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TicketHeaderWidget")
        set_uia_metadata(self, name="agent.ticket.active", description="id=agent.ticket.active")
        self._access_code = ""
        self._public_url = ""

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(4)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        self.title_label = QLabel("#— · Обращение не выбрано")
        self.title_label.setObjectName("TicketHeaderTitle")
        set_uia_metadata(self.title_label, name="agent.ticket.active.title", description="id=agent.ticket.active.title")
        self.title_label.setWordWrap(True)
        self.status_badge = QLabel("—")
        self.status_badge.setObjectName("StatusBadge")
        set_uia_metadata(self.status_badge, name="agent.ticket.active.status", description="id=agent.ticket.active.status")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(self.title_label, 1)
        title_row.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignTop)
        title_col.addLayout(title_row)
        root.addLayout(title_col, 1)

        self.actions_button = QToolButton()
        self.actions_button.setObjectName("SecondaryButton")
        self.actions_button.setText("Действия")
        self.actions_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.actions_button)
        menu.setObjectName("AgentPopupMenu")
        self.copy_code_action = menu.addAction("Скопировать код доступа")
        self.open_url_action = menu.addAction("Открыть в браузере")
        self.attach_action = menu.addAction("Приложить файл")
        self.refresh_action = menu.addAction("Обновить статус")
        self.resolution_separator = menu.addSeparator()
        self.confirm_resolution_action = menu.addAction("Да, всё работает")
        self.reject_resolution_action = menu.addAction("Нет, проблема осталась")
        self.copy_code_action.triggered.connect(self._emit_copy_code)
        self.open_url_action.triggered.connect(self._emit_open_url)
        self.attach_action.triggered.connect(self.attachRequested.emit)
        self.refresh_action.triggered.connect(self.refreshRequested.emit)
        self.confirm_resolution_action.triggered.connect(self.confirmResolutionRequested.emit)
        self.reject_resolution_action.triggered.connect(self.rejectResolutionRequested.emit)
        self.actions_button.setMenu(menu)
        root.addWidget(self.actions_button, 0, Qt.AlignmentFlag.AlignTop)

        self._apply_styles("info")

    def set_view_model(self, model: TicketHeaderViewModel) -> None:
        self._access_code = model.access_code
        self._public_url = model.public_url
        self.title_label.setText(f"{model.number_text} · {model.title}")
        self.status_badge.setText(model.status_label)
        description = (
            f"id=agent.ticket.active; ticket_code={model.number_text.lstrip('#')}; "
            f"status={model.status_label}; title={model.title}"
        )
        set_uia_metadata(self, name="agent.ticket.active", description=description)
        set_uia_metadata(
            self.title_label,
            name="agent.ticket.active.title",
            description=f"id=agent.ticket.active.title; title={model.title}; ticket_code={model.number_text.lstrip('#')}",
        )
        set_uia_metadata(
            self.status_badge,
            name="agent.ticket.active.status",
            description=f"id=agent.ticket.active.status; status={model.status_label}",
        )
        self.copy_code_action.setEnabled(bool(self._access_code))
        self.open_url_action.setEnabled(bool(self._public_url))
        self.resolution_separator.setVisible(model.show_resolution_actions)
        self.confirm_resolution_action.setVisible(model.show_resolution_actions)
        self.reject_resolution_action.setVisible(model.show_resolution_actions)
        self._apply_styles(model.status_style)

    def _emit_copy_code(self) -> None:
        if self._access_code:
            self.copyCodeRequested.emit(self._access_code)

    def _emit_open_url(self) -> None:
        if self._public_url:
            self.openUrlRequested.emit(self._public_url)

    def _apply_styles(self, status_style: str) -> None:
        normalized = status_style if status_style in {"success", "warning", "danger", "info"} else "info"
        self.status_badge.setProperty("statusStyle", normalized)
        theme.refresh_qss_state(self.status_badge)


class TicketRightInfoPanel(QFrame):
    """Requester-safe right panel with ticket facts and access actions."""

    copyCodeRequested = Signal(str)
    openUrlRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TicketRightInfoPanel")
        self.setFixedWidth(300)
        self._access_code = ""
        self._public_url = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        info_layout = self._add_card(root, "Информация")
        self.requester_value = self._add_row(info_layout, "Заявитель")
        self.assignee_value = self._add_row(info_layout, "Исполнитель")
        self.room_value = self._add_row(info_layout, "Кабинет")
        self.phone_value = self._add_row(info_layout, "Телефон")

        timing_layout = self._add_card(root, "Сроки")
        self.first_response_value = self._add_row(timing_layout, "Первый ответ")
        self.first_response_remaining = QLabel("—")
        self.first_response_remaining.setObjectName("InfoSubValue")
        timing_layout.addWidget(self.first_response_remaining)
        self.first_response_progress = self._add_sla_progress(timing_layout)
        self.resolution_value = self._add_row(timing_layout, "Решение")
        self.resolution_remaining = QLabel("—")
        self.resolution_remaining.setObjectName("InfoSubValue")
        timing_layout.addWidget(self.resolution_remaining)
        self.resolution_progress = self._add_sla_progress(timing_layout)
        self.sla_status_value = self._add_row(timing_layout, "Статус по срокам")

        access_layout = self._add_card(root, "Доступ к обращению")
        access_hint = QLabel("Код доступа")
        access_hint.setObjectName("InfoLabel")
        self.access_code_value = QLabel("—")
        self.access_code_value.setObjectName("AccessCodeValue")
        self.access_code_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        access_layout.addWidget(access_hint)
        access_layout.addWidget(self.access_code_value)
        access_buttons = QHBoxLayout()
        access_buttons.setContentsMargins(0, 4, 0, 0)
        access_buttons.setSpacing(8)
        self.copy_code_button = QPushButton("Скопировать код")
        self.copy_code_button.setObjectName("SecondaryButton")
        self.copy_code_button.clicked.connect(self._emit_copy_code)
        self.open_url_button = QPushButton("Открыть в браузере")
        self.open_url_button.setObjectName("SecondaryButton")
        self.open_url_button.clicked.connect(self._emit_open_url)
        access_buttons.addWidget(self.copy_code_button)
        access_buttons.addWidget(self.open_url_button)
        access_layout.addLayout(access_buttons)

        device_layout = self._add_card(root, "Устройство")
        self.device_card = device_layout.parentWidget()
        self.device_name_value = self._add_row(device_layout, "Имя устройства")
        self.os_value = self._add_row(device_layout, "Операционная система")
        self.agent_status_value = self._add_row(device_layout, "Агент")
        self.last_contact_value = self._add_row(device_layout, "Последний контакт")

        root.addStretch(1)
        self._apply_styles()
        self.set_view_model(TicketInfoPanelViewModel())

    def _add_card(self, parent_layout: QVBoxLayout, title: str) -> QVBoxLayout:
        card = QFrame()
        card.setObjectName("InfoCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("InfoCardTitle")
        layout.addWidget(title_label)
        parent_layout.addWidget(card)
        return layout

    def _add_row(self, parent_layout: QVBoxLayout, label: str) -> QLabel:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        label_widget = QLabel(label)
        label_widget.setObjectName("InfoLabel")
        value_widget = QLabel("—")
        value_widget.setObjectName("InfoValue")
        value_widget.setWordWrap(True)
        value_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(label_widget, 0)
        row.addWidget(value_widget, 1)
        parent_layout.addLayout(row)
        return value_widget

    def _add_sla_progress(self, parent_layout: QVBoxLayout) -> QProgressBar:
        progress = QProgressBar()
        progress.setObjectName("SlaProgressBar")
        progress.setRange(0, 100)
        progress.setTextVisible(False)
        progress.setFixedHeight(8)
        parent_layout.addWidget(progress)
        return progress

    def set_view_model(self, model: TicketInfoPanelViewModel) -> None:
        self._access_code = model.access_code if model.access_code != "—" else ""
        self._public_url = model.public_url
        self.requester_value.setText(model.requester_name)
        self.assignee_value.setText(model.assignee_name)
        self.room_value.setText(model.room)
        self.phone_value.setText(model.phone)
        self.first_response_value.setText(model.first_response_text)
        self.first_response_remaining.setText(model.first_response_remaining_text)
        self.first_response_progress.setValue(model.first_response_progress)
        self.resolution_value.setText(model.resolution_text)
        self.resolution_remaining.setText(model.resolution_remaining_text)
        self.resolution_progress.setValue(model.resolution_progress)
        self.sla_status_value.setText(model.sla_status_text)
        self.sla_status_value.setProperty("slaStyle", model.sla_style)
        self.access_code_value.setText(model.access_code)
        self.copy_code_button.setEnabled(bool(self._access_code))
        self.open_url_button.setEnabled(bool(self._public_url))
        self.device_name_value.setText(model.device_name)
        self.os_value.setText(model.os_text)
        self.agent_status_value.setText(model.agent_status_text)
        self.last_contact_value.setText(model.last_contact_text)
        self.device_card.setVisible(model.show_device)
        self._apply_styles()

    def _emit_copy_code(self) -> None:
        if self._access_code:
            self.copyCodeRequested.emit(self._access_code)

    def _emit_open_url(self) -> None:
        if self._public_url:
            self.openUrlRequested.emit(self._public_url)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            theme.requester_helpdesk_stylesheet()
            +
            f"QFrame#TicketRightInfoPanel {{ background: transparent; border: none; }}"
            f"QFrame#InfoCard {{ background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; border-radius: 16px; }}"
            f"QLabel#InfoCardTitle {{ color: {theme.TEXT_PRIMARY}; font-size: {theme.TITLE_PT}pt; font-weight: 800; }}"
            f"QLabel#InfoLabel {{ color: {theme.TEXT_MUTED}; font-size: {theme.UI_FONT_PT}pt; font-weight: 700; }}"
            f"QLabel#InfoValue {{ color: {theme.TEXT_PRIMARY}; font-size: {theme.BODY_PT}pt; font-weight: 600; }}"
            f"QLabel#InfoSubValue {{ color: {theme.TEXT_MUTED}; font-size: {theme.UI_FONT_PT}pt; font-weight: 600; }}"
            f"QLabel#AccessCodeValue {{ background: {theme.INFO_BG}; color: {theme.TEXT_PRIMARY}; border-radius: 12px; padding: 10px; font-size: {theme.TITLE_PT}pt; font-weight: 900; letter-spacing: 1px; }}"
            f"QProgressBar#SlaProgressBar {{ background: {theme.BG_INPUT}; border: 1px solid {theme.BORDER}; border-radius: 4px; }}"
            f"QProgressBar#SlaProgressBar::chunk {{ background: {theme.PRIMARY_BTN}; border-radius: 4px; }}"
        )


class TimelineItemWidget(QFrame):
    """Requester-safe timeline widget for chat, system, attachment and diagnostic events."""

    def __init__(self, item: TimelineItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item = item
        self.check_labels: list[QLabel] = []
        if item.kind == "diagnostic_result":
            object_name = "TimelineDiagnosticResult"
        elif item.kind == "attachment":
            object_name = "TimelineAttachment"
        elif item.kind == "user_message":
            object_name = "TimelineUserMessage"
        elif item.kind == "support_message":
            object_name = "TimelineSupportMessage"
        else:
            object_name = "TimelineSystemEvent"
        self.setObjectName(object_name)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(6)

        is_message = item.kind in {"user_message", "support_message"}
        title_text = item.actor_label if is_message else (item.text or "Событие обращения")
        self.title_label = QLabel(title_text)
        self.title_label.setObjectName("TimelineMessageActor" if is_message else "TimelineTitle")
        self.title_label.setWordWrap(True)
        root.addWidget(self.title_label)
        self.message_actor_label = self.title_label if is_message else QLabel("")
        if not is_message:
            self.message_actor_label.hide()

        subtitle = "" if item.kind == "diagnostic_result" else ("" if is_message else item.actor_label)
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("TimelineSubtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))
        root.addWidget(self.subtitle_label)

        if is_message:
            self.message_text_label = QLabel(item.text)
            self.message_text_label.setObjectName("TimelineMessageText")
            self.message_text_label.setWordWrap(True)
            root.addWidget(self.message_text_label)
        else:
            self.message_text_label = QLabel("")
            self.message_text_label.hide()

        if item.kind == "diagnostic_result":
            checks_row = QHBoxLayout()
            checks_row.setContentsMargins(0, 4, 0, 0)
            checks_row.setSpacing(8)
            for check in item.payload.get("checks") or []:
                if not isinstance(check, dict):
                    continue
                label = self._build_check_label(check)
                self.check_labels.append(label)
                checks_row.addWidget(label)
            checks_row.addStretch(1)
            root.addLayout(checks_row)

        if item.kind == "attachment":
            attachment_row = QHBoxLayout()
            attachment_row.setContentsMargins(0, 4, 0, 0)
            attachment_row.setSpacing(8)
            file_text_col = QVBoxLayout()
            file_text_col.setContentsMargins(0, 0, 0, 0)
            file_text_col.setSpacing(2)
            self.attachment_name_label = QLabel(str(item.payload.get("name") or "Файл"))
            self.attachment_name_label.setObjectName("AttachmentName")
            self.attachment_name_label.setWordWrap(True)
            self.attachment_size_label = QLabel(str(item.payload.get("size_label") or ""))
            self.attachment_size_label.setObjectName("AttachmentMeta")
            file_text_col.addWidget(self.attachment_name_label)
            file_text_col.addWidget(self.attachment_size_label)
            self.open_attachment_button = QPushButton("Открыть")
            self.open_attachment_button.setObjectName("SecondaryButton")
            self.open_attachment_button.setEnabled(bool(str(item.payload.get("url") or "").strip()))
            self.open_attachment_button.clicked.connect(self._open_attachment)
            attachment_row.addLayout(file_text_col, 1)
            attachment_row.addWidget(self.open_attachment_button, 0, Qt.AlignmentFlag.AlignTop)
            root.addLayout(attachment_row)
        else:
            self.attachment_name_label = QLabel("")
            self.attachment_name_label.hide()
            self.attachment_size_label = QLabel("")
            self.attachment_size_label.hide()
            self.open_attachment_button = QPushButton("Открыть")
            self.open_attachment_button.hide()

        if item.time_label:
            self.time_label = QLabel(item.time_label)
            self.time_label.setObjectName("TimelineTime")
            root.addWidget(self.time_label)
        else:
            self.time_label = QLabel("")
            self.time_label.hide()

        self._apply_styles()

    def _open_attachment(self) -> None:
        url = str(self.item.payload.get("url") or "").strip()
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _build_check_label(self, check: dict) -> QLabel:
        label_text = str(check.get("label") or "Проверка").strip()
        summary = str(check.get("summary") or "").strip()
        label = QLabel(f"{label_text}\n{summary}".strip())
        label.setObjectName("DiagnosticCheck")
        label.setWordWrap(True)
        label.setMinimumWidth(92)
        return label

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            theme.requester_helpdesk_stylesheet()
            +
            f"QFrame#TimelineSystemEvent {{ background: {theme.BG_CARD_ALT}; border: 1px solid {theme.BORDER}; border-radius: 14px; }}"
            f"QFrame#TimelineDiagnosticResult {{ background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; border-radius: 16px; }}"
            f"QFrame#TimelineAttachment {{ background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; border-radius: 16px; }}"
            f"QFrame#TimelineUserMessage {{ background: #EAF6FF; border: 1px solid #BFDBFE; border-radius: 16px; }}"
            f"QFrame#TimelineSupportMessage {{ background: #ECFDF3; border: 1px solid #BBF7D0; border-radius: 16px; }}"
            f"QLabel#TimelineTitle {{ color: {theme.TEXT_PRIMARY}; font-size: {theme.BODY_PT}pt; font-weight: 800; }}"
            f"QLabel#TimelineSubtitle {{ color: {theme.TEXT_SECONDARY}; font-size: {theme.UI_FONT_PT}pt; font-weight: 600; }}"
            f"QLabel#TimelineTime {{ color: {theme.TEXT_MUTED}; font-size: {theme.UI_FONT_PT}pt; }}"
            f"QLabel#TimelineMessageActor {{ color: {theme.TEXT_PRIMARY}; font-size: {theme.UI_FONT_PT}pt; font-weight: 800; }}"
            f"QLabel#TimelineMessageText {{ color: {theme.TEXT_PRIMARY}; font-size: {theme.BODY_PT}pt; font-weight: 500; }}"
            f"QLabel#DiagnosticCheck {{ background: {theme.BG_CARD_ALT}; color: {theme.TEXT_PRIMARY}; border: 1px solid {theme.BORDER}; border-radius: 10px; padding: 8px; font-size: {theme.UI_FONT_PT}pt; font-weight: 700; }}"
            f"QLabel#AttachmentName {{ color: {theme.TEXT_PRIMARY}; font-size: {theme.BODY_PT}pt; font-weight: 800; }}"
            f"QLabel#AttachmentMeta {{ color: {theme.TEXT_MUTED}; font-size: {theme.UI_FONT_PT}pt; font-weight: 600; }}"
        )


class TicketComposerWidget(QFrame):
    """Multiline requester composer for ticket messages and materials."""

    sendRequested = Signal()

    TERMINAL_STATUSES = {"closed", "canceled", "cancelled"}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TicketComposerWidget")
        self._active = False
        self._connected = True
        self._terminal = False
        self._sending = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self.message_edit = QTextEdit()
        self.message_edit.setObjectName("ChatComposerInput")
        self.message_edit.setPlaceholderText("Напишите сообщение специалисту...")
        self.message_edit.setMinimumHeight(74)
        self.message_edit.setMaximumHeight(120)
        self.message_edit.textChanged.connect(self._update_enabled_state)
        root.addWidget(self.message_edit)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.attach_button = QPushButton("Прикрепить файл")
        self.attach_button.setObjectName("SecondaryButton")
        self.media_button = QPushButton("Скриншот / Видео")
        self.media_button.setObjectName("SecondaryButton")
        self.status_label = QLabel("")
        self.status_label.setObjectName("ComposerStatusLabel")
        self.send_button = QPushButton("Отправить")
        self.send_button.setObjectName("PrimaryButton")
        self.send_button.clicked.connect(self.sendRequested.emit)
        row.addWidget(self.attach_button)
        row.addWidget(self.media_button)
        row.addWidget(self.status_label, 1)
        row.addWidget(self.send_button)
        root.addLayout(row)

        self._apply_styles()
        self._update_enabled_state()

    def message_text(self) -> str:
        return self.message_edit.toPlainText().strip()

    def clear_message(self) -> None:
        self.message_edit.clear()

    def set_ticket_state(
        self,
        *,
        active: bool,
        ticket_status: str = "",
        connected: bool = True,
        sending: bool = False,
    ) -> None:
        self._active = bool(active)
        self._connected = bool(connected)
        self._terminal = str(ticket_status or "").strip().lower() in self.TERMINAL_STATUSES
        self._sending = bool(sending)
        self._update_enabled_state()

    def set_sending(self, sending: bool) -> None:
        self._sending = bool(sending)
        self._update_enabled_state()

    def _update_enabled_state(self) -> None:
        can_use = self._active and self._connected and not self._terminal and not self._sending
        self.message_edit.setEnabled(can_use)
        self.attach_button.setEnabled(can_use)
        self.media_button.setEnabled(can_use)
        self.send_button.setEnabled(can_use and bool(self.message_text()))
        if self._terminal:
            self.status_label.setText("Обращение закрыто")
        elif not self._active:
            self.status_label.setText("Откройте обращение")
        elif not self._connected:
            self.status_label.setText("Нет подключения")
        elif self._sending:
            self.status_label.setText("Отправляется...")
        else:
            self.status_label.setText("")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            theme.requester_helpdesk_stylesheet()
            +
            f"QFrame#TicketComposerWidget {{ background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; border-radius: 16px; }}"
            f"QTextEdit#ChatComposerInput {{ background: {theme.BG_INPUT}; color: {theme.TEXT_PRIMARY}; border: 1px solid {theme.BORDER}; border-radius: 12px; padding: 10px; font-size: {theme.BODY_PT}pt; }}"
            f"QLabel#ComposerStatusLabel {{ color: {theme.TEXT_MUTED}; font-size: {theme.UI_FONT_PT}pt; font-weight: 600; }}"
        )
