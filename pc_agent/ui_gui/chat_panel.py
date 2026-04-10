"""Ticket chat panel for the agent GUI."""

from __future__ import annotations

import asyncio
import json
import re
import socket
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from loguru import logger

from pc_agent.core.runtime_paths import resolve_data_root

from .server_api import ServerApiClient, TicketApiClient
from . import theme
from .ticket_format import (
    format_ts_short,
    normalize_iso_ts,
    ticket_row_fingerprint,
    ticket_status_colors,
    ticket_status_label,
)
from .tickets_list_model import TicketCardDelegate, TicketsListModel

PINNED_STUB_META_KEY = "agent_stub_reply_to_message"

OUTGOING_MESSAGE_ROLES = {"user", "agent", "requester"}
SUPPORT_MESSAGE_ROLES = {"support", "admin"}


def can_user_confirm_close(ticket: dict) -> bool:
    return str(ticket.get("status") or "").strip().lower() == "resolved"


def ticket_matches_query(ticket: dict, query: str) -> bool:
    normalized_query = (query or "").strip().casefold()
    if not normalized_query:
        return True
    haystack = " ".join(
        str(ticket.get(key) or "")
        for key in (
            "ticket_code",
            "ticket_id",
            "title",
            "description",
            "status",
            "priority_class",
            "priority",
            "queue_code",
            "assignee_id",
            "requester_display_name",
        )
    ).casefold()
    return normalized_query in haystack


def message_visual_role(message: dict) -> str:
    role = str(message.get("from_role") or "").strip().lower()
    direction = str(message.get("direction") or "").strip().lower()
    if direction == "from_agent" or role in OUTGOING_MESSAGE_ROLES:
        return "self"
    if role in SUPPORT_MESSAGE_ROLES:
        return "support"
    return "neutral"


class MessageBubbleWidget(QFrame):
    """Single message/event bubble in the messenger timeline."""

    def __init__(
        self,
        panel: "ChatPanel",
        bubble_role: str,
        sender: str,
        text: str,
        ts_text: str,
        attachments: Optional[List[str]] = None,
        menu_text: Optional[str] = None,
        reply_to: Optional[dict] = None,
        message_context: Optional[dict] = None,
    ) -> None:
        super().__init__(panel)
        self._panel = panel
        self._menu_text = (menu_text or text or "").strip()
        self._interactive = bubble_role in {"self", "support"}
        self._message_context = dict(message_context or {})
        self.setObjectName(f"bubble_{bubble_role}")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

        styles = {
            "self": (
                theme.BUBBLE_SELF_BG,
                theme.BUBBLE_SELF_BORDER,
                theme.BUBBLE_SELF_FG,
                theme.TEXT_MUTED,
            ),
            "support": (
                theme.BUBBLE_SUPPORT_BG,
                theme.BUBBLE_SUPPORT_BORDER,
                theme.BUBBLE_SUPPORT_FG,
                theme.TEXT_MUTED,
            ),
            "event": (
                theme.BUBBLE_EVENT_BG,
                theme.BUBBLE_EVENT_BORDER,
                theme.BUBBLE_EVENT_FG,
                theme.BUBBLE_EVENT_MUTED,
            ),
        }
        bg, border, fg, muted = styles.get(bubble_role, styles["event"])

        self.setStyleSheet(
            f"""
            QFrame#{self.objectName()} {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(6)

        if sender:
            sender_label = QLabel(sender)
            sender_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            sender_label.setStyleSheet(
                f"font-size: {theme.UI_FONT_PT + 1}pt; color: {muted}; font-weight: 700; border: none; background: transparent;"
            )
            layout.addWidget(sender_label)

        reply_info = self._panel._resolve_reply_reference(reply_to)
        if reply_info:
            reply_author = QLabel(reply_info.get("sender_display_name") or "Ответ")
            reply_author.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            reply_author.setStyleSheet(
                f"font-size: {theme.UI_FONT_PT}pt; font-weight: 700; color: {theme.LINK}; border: none; background: transparent;"
            )
            reply_preview = QLabel(reply_info.get("preview") or "")
            reply_preview.setWordWrap(True)
            reply_preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            reply_preview.setStyleSheet(
                f"font-size: {theme.BODY_PT}pt; color: {theme.TEXT_SECONDARY}; border: none; background: transparent;"
            )
            reply_wrap = QFrame()
            reply_wrap.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            reply_wrap.setStyleSheet(
                f"background: rgba(255,255,255,0.65); border: 1px solid {theme.BORDER_SOFT}; border-radius: 12px;"
            )
            reply_layout = QVBoxLayout(reply_wrap)
            reply_layout.setContentsMargins(8, 6, 8, 6)
            reply_layout.setSpacing(2)
            reply_layout.addWidget(reply_author)
            reply_layout.addWidget(reply_preview)
            layout.addWidget(reply_wrap)

        text_label = QLabel(text or "Вложение")
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        text_label.setStyleSheet(
            f"font-size: {theme.BUBBLE_BODY_PT}pt; color: {fg}; border: none; background: transparent; "
            f"line-height: 1.5; padding: 2px 0;"
        )
        layout.addWidget(text_label)

        for attachment in attachments or []:
            chip = QLabel(attachment)
            chip.setWordWrap(True)
            chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            chip.setStyleSheet(
                f"font-size: {theme.BODY_PT}pt; color: {fg}; "
                "padding: 6px 10px; border-radius: 10px; border: none; "
                "background: rgba(255,255,255,0.55); font-weight: 600;"
            )
            layout.addWidget(chip)

        if ts_text:
            time_label = QLabel(ts_text)
            time_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            time_label.setStyleSheet(
                f"font-size: {theme.UI_FONT_PT}pt; color: {muted}; border: none; background: transparent;"
            )
            layout.addWidget(time_label, alignment=Qt.AlignmentFlag.AlignRight if bubble_role == "support" else Qt.AlignmentFlag.AlignLeft)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if not self._interactive or not self._menu_text:
            event.ignore()
            return
        context = dict(self._message_context)
        if not context.get("preview"):
            context["preview"] = self._menu_text
        self._panel._open_message_context_menu(event.globalPos(), context)
        event.accept()


class TicketCreateDialog(QDialog):
    """Modal dialog for ticket creation."""

    def __init__(self, panel: "ChatPanel"):
        super().__init__(panel)
        self.panel = panel

        self.setWindowTitle("Создать тикет")
        self.setModal(True)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        profile_group = QGroupBox("Профиль инициатора")
        profile_layout = QVBoxLayout(profile_group)
        self.profile_selector = QComboBox()
        self.profile_selector.currentIndexChanged.connect(self._on_profile_changed)
        profile_layout.addWidget(self.profile_selector)

        self.profile_summary = QLabel("")
        self.profile_summary.setWordWrap(True)
        profile_layout.addWidget(self.profile_summary)

        profile_buttons = QHBoxLayout()
        self.manage_profiles_btn = QPushButton("Профили")
        self.manage_profiles_btn.clicked.connect(self._on_manage_profiles)
        profile_buttons.addWidget(self.manage_profiles_btn)
        profile_buttons.addStretch(1)
        profile_layout.addLayout(profile_buttons)
        layout.addWidget(profile_group)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Опишите проблему для службы поддержки")
        self.description_input.setMinimumHeight(140)
        layout.addWidget(self.description_input)

        priority_form = QFormLayout()
        self.urgency_select = QComboBox()
        self.urgency_select.addItem("Несрочно", False)
        self.urgency_select.addItem("Срочно", True)
        self.importance_select = QComboBox()
        self.importance_select.addItem("Неважно", False)
        self.importance_select.addItem("Важно", True)
        self.urgency_reason_input = QLineEdit()
        self.urgency_reason_input.setPlaceholderText("Обоснование срочности")
        self.importance_reason_input = QLineEdit()
        self.importance_reason_input.setPlaceholderText("Обоснование важности")
        priority_form.addRow("Срочность", self.urgency_select)
        priority_form.addRow("Важность", self.importance_select)
        priority_form.addRow("Причина срочности", self.urgency_reason_input)
        priority_form.addRow("Причина важности", self.importance_reason_input)
        layout.addLayout(priority_form)

        buttons = QHBoxLayout()
        self.create_btn = QPushButton("Создать")
        self.create_btn.clicked.connect(self._on_accept)
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addStretch(1)
        self.create_btn.setObjectName("PrimaryButton")
        self.cancel_btn.setObjectName("SecondaryButton")
        buttons.addWidget(self.create_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

        self.manage_profiles_btn.setObjectName("SecondaryButton")
        theme.apply_agent_dialog_theme(self)
        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        active_id = self.panel._profiles_data.get("active_profile_id")
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        for profile in self.panel._profiles():
            title = profile.get("display_name") or profile.get("full_name") or "Без имени"
            self.profile_selector.addItem(title, profile.get("id"))

        if self.profile_selector.count() > 0:
            if active_id:
                idx = self.profile_selector.findData(active_id)
                self.profile_selector.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                self.profile_selector.setCurrentIndex(0)

        self.profile_selector.blockSignals(False)
        self.profile_summary.setText(self.panel.current_requester_profile_summary())

    def _on_profile_changed(self, *_args) -> None:
        profile_id = self.profile_selector.currentData()
        self.panel._profiles_data["active_profile_id"] = profile_id
        self.panel._save_profiles()
        self.profile_summary.setText(self.panel.current_requester_profile_summary())

    def _on_manage_profiles(self) -> None:
        self.panel.open_profile_manager()
        self._refresh_profiles()

    def _on_accept(self) -> None:
        if not self.panel.has_active_profile():
            QMessageBox.warning(self, "Профиль обязателен", "Выберите профиль инициатора.")
            return
        if not self.description_input.toPlainText().strip():
            QMessageBox.warning(self, "Ошибка", "Опишите проблему")
            return
        self.accept()

    def payload(self) -> dict:
        description = self.description_input.toPlainText().strip()
        urgency = bool(self.urgency_select.currentData())
        importance = bool(self.importance_select.currentData())
        urgency_reason = self.urgency_reason_input.text().strip() or ("Срочно" if urgency else "Несрочно")
        importance_reason = self.importance_reason_input.text().strip() or ("Важно" if importance else "Неважно")
        return {
            "description": description,
            "urgency": urgency,
            "importance": importance,
            "urgency_reason": urgency_reason,
            "importance_reason": importance_reason,
        }


class ProfileSidebarWidget(QFrame):
    """Левая колонка главного окна: данные активного профиля и переключение."""

    def __init__(self, panel: "ChatPanel", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._panel = panel
        self._loading_combo = False
        self.setObjectName("ProfileSidebar")
        self.setStyleSheet(theme.profile_sidebar_stylesheet())
        self.setMinimumWidth(280)
        self.setMaximumWidth(400)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(12)

        title = QLabel("Профиль инициатора")
        title.setObjectName("ProfileSidebarTitle")
        outer.addWidget(title)

        self._hint = QLabel("")
        self._hint.setObjectName("ProfileHint")
        self._hint.setWordWrap(True)
        outer.addWidget(self._hint)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self._fld_display = QLabel("—")
        self._fld_display.setObjectName("ProfileFieldValue")
        self._fld_display.setWordWrap(True)
        self._lbl_display = QLabel("Отображаемое имя")
        self._lbl_display.setObjectName("ProfileFieldLabel")
        form.addRow(self._lbl_display, self._fld_display)

        self._fld_full = QLabel("—")
        self._fld_full.setObjectName("ProfileFieldValue")
        self._fld_full.setWordWrap(True)
        self._lbl_full = QLabel("ФИО")
        self._lbl_full.setObjectName("ProfileFieldLabel")
        form.addRow(self._lbl_full, self._fld_full)

        self._fld_location = QLabel("—")
        self._fld_location.setObjectName("ProfileFieldValue")
        self._fld_location.setWordWrap(True)
        self._lbl_location = QLabel("Корпус / кабинет")
        self._lbl_location.setObjectName("ProfileFieldLabel")
        form.addRow(self._lbl_location, self._fld_location)

        self._fld_phone = QLabel("—")
        self._fld_phone.setObjectName("ProfileFieldValue")
        self._fld_phone.setWordWrap(True)
        self._lbl_phone = QLabel("Телефон")
        self._lbl_phone.setObjectName("ProfileFieldLabel")
        form.addRow(self._lbl_phone, self._fld_phone)

        outer.addLayout(form)

        combo_label = QLabel("Активный профиль")
        combo_label.setObjectName("ProfileFieldLabel")
        outer.addWidget(combo_label)
        self._profile_combo = QComboBox()
        self._profile_combo.currentIndexChanged.connect(self._on_combo_changed)
        outer.addWidget(self._profile_combo)

        btn_row = QVBoxLayout()
        btn_row.setSpacing(8)
        self._btn_manage = QPushButton("Изменить / создать профили…")
        self._btn_manage.clicked.connect(self._on_manage_clicked)
        btn_row.addWidget(self._btn_manage)
        self._btn_new = QPushButton("Новый профиль")
        self._btn_new.clicked.connect(self._on_new_clicked)
        btn_row.addWidget(self._btn_new)
        outer.addLayout(btn_row)

        outer.addStretch(1)
        self.refresh_from_panel()

    def _on_manage_clicked(self) -> None:
        self._panel.open_profile_manager(start_new=False)

    def _on_new_clicked(self) -> None:
        self._panel.open_profile_manager(start_new=True)

    def _on_combo_changed(self, _index: int) -> None:
        if self._loading_combo:
            return
        pid = self._profile_combo.currentData()
        if pid is None:
            return
        cur = self._panel._profiles_data.get("active_profile_id")
        if pid == cur:
            return
        self._panel._profiles_data["active_profile_id"] = pid
        self._panel._save_profiles()

    def refresh_from_panel(self) -> None:
        profile = self._panel._active_profile()
        if profile is None:
            self._hint.setText("Профиль не выбран. Создайте или выберите профиль — без него нельзя создать тикет.")
            self._fld_display.setText("—")
            self._fld_full.setText("—")
            self._fld_location.setText("—")
            self._fld_phone.setText("—")
            for w in (
                self._lbl_display,
                self._lbl_full,
                self._lbl_location,
                self._lbl_phone,
                self._fld_display,
                self._fld_full,
                self._fld_location,
                self._fld_phone,
            ):
                w.show()
        else:
            self._hint.setText("")
            self._fld_display.setText(str(profile.get("display_name") or "—"))
            self._fld_full.setText(str(profile.get("full_name") or "—"))
            loc = " ".join(filter(None, [profile.get("building"), profile.get("room")])) or "—"
            self._fld_location.setText(loc)
            self._fld_phone.setText(str(profile.get("phone") or "—"))

        self._loading_combo = True
        self._profile_combo.clear()
        active_id = self._panel._profiles_data.get("active_profile_id")
        for p in self._panel._profiles():
            title = p.get("display_name") or p.get("full_name") or "Без имени"
            self._profile_combo.addItem(str(title), p.get("id"))
        if self._profile_combo.count() == 0:
            self._profile_combo.addItem("(нет профилей)", None)
        else:
            idx = -1
            if active_id:
                idx = self._profile_combo.findData(active_id)
            if idx < 0:
                idx = 0
            self._profile_combo.setCurrentIndex(idx)
        self._loading_combo = False


class ChatPanel(QWidget):
    """Ticket UI used by the desktop agent."""

    chatSessionChanged = Signal(str)
    requesterProfileChanged = Signal()
    listNavigationVisibilityChanged = Signal(bool)

    def __init__(
        self,
        client: Optional[ServerApiClient] = None,
        base_url: Optional[str] = None,
        device_id: str = "test_pc_01",
        actor_role: str = "support",
        auth_token: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)

        if client is not None:
            self.client = client
        else:
            if base_url is None:
                try:
                    from pc_agent.config.config_loader import get_config

                    base_url = get_config().server.api_url
                except Exception:
                    from pc_agent.config.config_loader import ServerConfig

                    base_url = ServerConfig().api_url
            self.client = ServerApiClient(base_url, device_id, actor_role)

        if base_url is None:
            try:
                from pc_agent.config.config_loader import get_config

                base_url = get_config().server.api_url
            except Exception:
                from pc_agent.config.config_loader import ServerConfig

                base_url = ServerConfig().api_url

        self.device_id = device_id
        try:
            from core.identity import IdentityManager

            identity = IdentityManager().load_or_create()
            self.device_id = identity.get("uuid", device_id)
        except Exception as exc:
            logger.warning(f"Не удалось загрузить identity: {exc}")

        self.user_display_name = socket.gethostname() or "User"
        self.ticket_client = TicketApiClient(base_url, self.device_id, self.user_display_name, auth_token=auth_token)

        self.active_ticket_id: Optional[str] = None
        self.current_job_id: Optional[str] = None
        self.tickets_cache: List[dict] = []
        self.local_action_buffer: Dict[str, List[dict]] = {}
        self._ticket_search_query = ""
        self._show_open_tickets = True
        self._show_closed_tickets = False
        self._pinned_messages: Dict[str, List[dict]] = {}
        self._reply_target: Optional[dict] = None
        self._last_timeline_html: Optional[str] = None
        self._pending_ticket_snapshot: Optional[tuple[dict, List[dict], List[dict]]] = None
        self._bubble_menu_open = False
        self._timeline_bubbles: List[MessageBubbleWidget] = []
        self._resolution_prompt_keys: set[str] = set()
        self._resolution_prompt_open_for: Optional[str] = None
        self._pending_tasks: set[asyncio.Task] = set()
        self._is_closing = False
        self._last_marked_read_event_id: Dict[str, int] = {}
        self._profile_sidebar: Optional[ProfileSidebarWidget] = None
        self._last_tickets_list_fingerprint: Optional[str] = None
        self._last_detail_header_sig: Optional[str] = None
        self._ticket_list_refresh_seq = 0
        self._ticket_detail_refresh_seq = 0
        self._tickets_model: Optional[TicketsListModel] = None

        self._profiles_path = resolve_data_root() / "requester_profiles.json"
        self._profiles_data = self._load_profiles()

        self._ticket_list_timer = QTimer(self)
        self._ticket_list_timer.timeout.connect(self._refresh_ticket_list_async)
        self._ticket_detail_timer = QTimer(self)
        self._ticket_detail_timer.timeout.connect(self._refresh_ticket_detail_async)

        self._setup_ui()
        self._ticket_list_timer.start(3000)
        self._refresh_ticket_list_async()

    def _setup_ui(self) -> None:
        self.setObjectName("AgentChatPanel")
        self.setStyleSheet(theme.chat_panel_stylesheet())

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        self.stacked = QStackedWidget()
        self.stacked.setObjectName("TicketStack")
        self._setup_list_screen()
        self._setup_chat_screen()
        self.stacked.addWidget(self.list_screen)
        self.stacked.addWidget(self.chat_screen)
        self.stacked.setCurrentWidget(self.list_screen)
        root_layout.addWidget(self.stacked)

        self._apply_view_port_opts()
        self._solidify_stack_backgrounds()
        self._refresh_profile_selector()

    def _setup_list_screen(self) -> None:
        self.list_screen = QWidget()
        self.list_screen.setObjectName("TicketListScreen")
        layout = QVBoxLayout(self.list_screen)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        actions_row = QHBoxLayout()
        self.create_ticket_btn = QPushButton("Создать тикет")
        self.create_ticket_btn.setObjectName("PrimaryButton")
        self.create_ticket_btn.clicked.connect(self._on_create_ticket)
        self.ticket_search_input = QLineEdit()
        self.ticket_search_input.setPlaceholderText("Поиск по коду, названию, статусу")
        self.ticket_search_input.textChanged.connect(self._on_ticket_search_changed)
        self.filter_open_checkbox = QCheckBox("Открытые")
        self.filter_open_checkbox.setChecked(True)
        self.filter_open_checkbox.toggled.connect(self._on_ticket_filter_changed)
        self.filter_closed_checkbox = QCheckBox("Закрытые")
        self.filter_closed_checkbox.setChecked(False)
        self.filter_closed_checkbox.toggled.connect(self._on_ticket_filter_changed)
        actions_row.addWidget(self.create_ticket_btn)
        actions_row.addWidget(self.ticket_search_input, 1)
        actions_row.addWidget(self.filter_open_checkbox)
        actions_row.addWidget(self.filter_closed_checkbox)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)

        tickets_group = QGroupBox("Список тикетов (только тикеты этого агента)")
        tickets_layout = QVBoxLayout(tickets_group)

        self.tickets_empty_label = QLabel("Ничего не найдено")
        self.tickets_empty_label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-weight: 600; padding: 12px; background: transparent;"
        )
        self.tickets_empty_label.setVisible(False)
        tickets_layout.addWidget(self.tickets_empty_label)

        self.tickets_list = QListView()
        self.tickets_list.setObjectName("TicketsListView")
        self.tickets_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tickets_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tickets_list.setUniformItemSizes(True)
        self.tickets_list.setSpacing(6)
        self.tickets_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tickets_list.setMouseTracking(True)
        self.tickets_list.setAutoFillBackground(True)
        self._tickets_model = TicketsListModel(self.tickets_list)
        self.tickets_list.setModel(self._tickets_model)
        self.tickets_list.setItemDelegate(TicketCardDelegate(self.tickets_list))
        self.tickets_list.doubleClicked.connect(lambda *_: self._on_open_ticket())
        tickets_layout.addWidget(self.tickets_list, 1)

        open_row = QHBoxLayout()
        self.open_ticket_btn = QPushButton("Открыть чат")
        self.open_ticket_btn.setObjectName("PrimaryButton")
        self.open_ticket_btn.clicked.connect(self._on_open_ticket)
        open_row.addStretch(1)
        open_row.addWidget(self.open_ticket_btn)
        tickets_layout.addLayout(open_row)

        layout.addWidget(tickets_group, 1)

    def _setup_chat_screen(self) -> None:
        self.chat_screen = QWidget()
        self.chat_screen.setObjectName("ChatScreenRoot")
        main_layout = QHBoxLayout(self.chat_screen)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        left_panel = QFrame()
        left_panel.setFrameShape(QFrame.Shape.StyledPanel)
        left_panel.setStyleSheet(
            f"background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; border-radius: 16px;"
        )
        left_panel.setFixedWidth(280)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)

        self.back_to_list_btn = QPushButton("← К списку тикетов")
        self.back_to_list_btn.setObjectName("SecondaryButton")
        self.back_to_list_btn.clicked.connect(self._show_list_screen)
        left_layout.addWidget(self.back_to_list_btn)

        self.ticket_info_label = QLabel("Тикет не выбран")
        self.ticket_info_label.setWordWrap(True)
        self.ticket_info_label.setTextFormat(Qt.TextFormat.RichText)
        self.ticket_info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.ticket_info_label.linkActivated.connect(self._on_ticket_code_clicked)
        self.ticket_info_label.setStyleSheet(
            f"font-weight: 700; font-size: {theme.TITLE_PT}pt; padding: 14px 16px; border-radius: 16px; "
            f"background: {theme.INFO_BG}; color: {theme.INFO_FG};"
        )
        left_layout.addWidget(self.ticket_info_label)

        self.ticket_meta_label = QLabel("Откройте тикет в списке.")
        self.ticket_meta_label.setWordWrap(True)
        self.ticket_meta_label.setTextFormat(Qt.TextFormat.RichText)
        self.ticket_meta_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.ticket_meta_label.setStyleSheet(
            f"padding: 12px 14px; color: {theme.TEXT_SECONDARY}; background: {theme.BG_INPUT}; "
            f"border: 1px solid {theme.BORDER}; border-radius: 14px; font-size: {theme.BODY_PT}pt; line-height: 1.45;"
        )
        left_layout.addWidget(self.ticket_meta_label, 1)
        left_layout.addStretch(1)
        main_layout.addWidget(left_panel)

        right_center = QWidget()
        right_center.setObjectName("ChatRightColumn")
        right_center.setStyleSheet(
            f"QWidget#ChatRightColumn {{ background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; border-radius: 18px; }}"
        )
        center_layout = QVBoxLayout(right_center)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(10)

        self.ticket_status_top = QLabel("Статус: —")
        self.ticket_status_top.setStyleSheet(
            f"font-weight: 700; font-size: {theme.TITLE_PT}pt; padding: 12px 16px; border-radius: 14px; "
            f"background: {theme.INFO_BG}; color: {theme.INFO_FG};"
        )
        center_layout.addWidget(self.ticket_status_top)

        self.top_pinned_info = QLabel("Код авторизации и ссылка тикета появятся здесь.")
        self.top_pinned_info.setWordWrap(True)
        self.top_pinned_info.setTextFormat(Qt.TextFormat.RichText)
        self.top_pinned_info.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.top_pinned_info.setOpenExternalLinks(True)
        self.top_pinned_info.linkActivated.connect(self._on_top_info_link_activated)
        self.top_pinned_info.setStyleSheet(
            f"padding: 12px 14px; border: 1px solid {theme.BORDER}; border-radius: 12px; "
            f"background: {theme.INFO_BG}; color: {theme.INFO_FG}; font-size: {theme.BODY_PT}pt;"
        )
        center_layout.addWidget(self.top_pinned_info)

        self.pinned_messages_widget = QWidget()
        pinned_row = QHBoxLayout(self.pinned_messages_widget)
        pinned_row.setContentsMargins(8, 8, 8, 8)
        pinned_row.setSpacing(8)
        self.pinned_messages_label = QLabel("")
        self.pinned_messages_label.setWordWrap(True)
        self.pinned_messages_label.setStyleSheet(
            f"color: {theme.LINK}; font-size: {theme.BODY_PT}pt; font-weight: 600;"
        )
        self.pinned_clear_btn = QPushButton("✕")
        self.pinned_clear_btn.setFixedSize(28, 28)
        self.pinned_clear_btn.clicked.connect(self._clear_pinned_messages_for_active_ticket)
        pinned_row.addWidget(self.pinned_messages_label, 1)
        pinned_row.addWidget(self.pinned_clear_btn)
        self.pinned_messages_widget.setStyleSheet(
            f"border: 1px dashed {theme.BORDER_SOFT}; border-radius: 12px; background: {theme.BG_CARD_ALT};"
        )
        self.pinned_messages_widget.hide()
        center_layout.addWidget(self.pinned_messages_widget)

        self.reply_stub_label = QLabel("")
        self.reply_stub_label.setWordWrap(True)
        self.reply_stub_label.setStyleSheet(
            f"padding: 6px 10px; border-radius: 10px; background: #faf3e3; color: #7a5a1a; border: 1px solid #e8d4a8;"
        )
        self.reply_stub_label.hide()
        center_layout.addWidget(self.reply_stub_label)

        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setObjectName("TimelineScroll")
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.timeline_scroll.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.timeline_container = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_container)
        self.timeline_layout.setContentsMargins(16, 16, 16, 16)
        self.timeline_layout.setSpacing(12)
        self.timeline_scroll.setWidget(self.timeline_container)
        center_layout.addWidget(self.timeline_scroll, 1)

        self.input_line = QLineEdit()
        self.input_line.setObjectName("ChatInputLine")
        self.input_line.setPlaceholderText("Сообщение в тикет")
        self.input_line.returnPressed.connect(self._on_send)
        center_layout.addWidget(self.input_line)

        self.resolution_message_widget = QWidget()
        resolution_layout = QHBoxLayout(self.resolution_message_widget)
        resolution_layout.setContentsMargins(10, 8, 10, 8)
        self.resolution_message_widget.setStyleSheet(
            f"background: #faf0e4; border: 1px solid #e8c49a; border-radius: 12px;"
        )
        self.resolution_prompt_label = QLabel(
            "Поддержка перевела тикет в статус 'Решён'. Подтвердить закрытие?"
        )
        self.resolution_prompt_label.setStyleSheet(
            f"font-size: {theme.BODY_PT}pt; color: {theme.TEXT_PRIMARY}; background: transparent;"
        )
        self.resolution_confirm_btn = QPushButton("Подтвердить")
        self.resolution_confirm_btn.setObjectName("PrimaryButton")
        self.resolution_confirm_btn.clicked.connect(lambda: self._spawn_task(self._async_close_ticket()))
        self.resolution_reject_btn = QPushButton("Отклонить")
        self.resolution_reject_btn.setObjectName("SecondaryButton")
        self.resolution_reject_btn.clicked.connect(self._on_reject_resolution)
        resolution_layout.addWidget(self.resolution_prompt_label, 1)
        resolution_layout.addWidget(self.resolution_confirm_btn)
        resolution_layout.addWidget(self.resolution_reject_btn)
        self.resolution_message_widget.hide()
        center_layout.addWidget(self.resolution_message_widget)

        actions = QHBoxLayout()
        self.send_btn = QPushButton("Отправить")
        self.send_btn.setObjectName("ChatSendButton")
        self.send_btn.clicked.connect(self._on_send)
        self.attach_btn = QToolButton()
        self.attach_btn.setText("📎")
        self.attach_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.attach_btn.setToolTip("Прикрепить")
        attach_menu = QMenu(self.attach_btn)
        attach_menu.addAction("Прикрепить фото", self._on_attach_photo)
        attach_menu.addAction("Прикрепить документ", self._on_attach_document)
        attach_menu.addAction("Прикрепить любой файл", self._on_attach_any_file)
        self.attach_btn.setMenu(attach_menu)
        self.media_btn = QPushButton("Скриншот / Видео")
        media_menu = QMenu(self.media_btn)
        media_menu.addAction("Сделать скриншот", self._on_send_screenshot)
        media_menu.addAction("Записать видео до 60 секунд", self._on_send_video)
        self.media_btn.setMenu(media_menu)
        self.tool_status_label = QLabel("")
        actions.addWidget(self.send_btn)
        actions.addWidget(self.attach_btn)
        actions.addWidget(self.media_btn)
        actions.addWidget(self.tool_status_label, 1)
        center_layout.addLayout(actions)

        main_layout.addWidget(right_center, 3)

    def _apply_view_port_opts(self) -> None:
        base = QFont()
        base.setFamilies(["Segoe UI", "Tahoma", "Arial"])
        base.setPointSize(10)
        self.setFont(base)
        if hasattr(self, "tickets_list"):
            self.tickets_list.setFont(base)
            _list_bg = QColor(theme.BG_CARD_ALT)
            list_pal = QPalette(self.tickets_list.palette())
            list_pal.setColor(QPalette.ColorRole.Window, _list_bg)
            list_pal.setColor(QPalette.ColorRole.Base, _list_bg)
            self.tickets_list.setPalette(list_pal)

            t_vp = self.tickets_list.viewport()
            t_vp.setMouseTracking(True)
            # Не ставить WA_OpaquePaintEvent: иначе Qt не заливает фон viewport, а делегат рисует
            # только строки — на Windows остаётся «чёрная дыра».
            t_vp.setAutoFillBackground(True)
            t_vp.setStyleSheet(f"background-color: {theme.BG_CARD_ALT};")
            vp_pal = QPalette(t_vp.palette())
            vp_pal.setColor(QPalette.ColorRole.Window, _list_bg)
            vp_pal.setColor(QPalette.ColorRole.Base, _list_bg)
            t_vp.setPalette(vp_pal)
        if hasattr(self, "timeline_scroll"):
            self.timeline_scroll.setAutoFillBackground(True)
            tsp = self.timeline_scroll.palette()
            tsp.setColor(self.timeline_scroll.backgroundRole(), QColor(theme.TIMELINE_SCROLL_BG))
            self.timeline_scroll.setPalette(tsp)
            s_vp = self.timeline_scroll.viewport()
            s_vp.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            s_vp.setAutoFillBackground(True)
            pal2 = s_vp.palette()
            pal2.setColor(s_vp.backgroundRole(), QColor(theme.TIMELINE_SCROLL_BG))
            s_vp.setPalette(pal2)
        if hasattr(self, "timeline_container"):
            self.timeline_container.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def _solidify_stack_backgrounds(self) -> None:
        page = QColor(theme.BG_PAGE)
        for w in (self.stacked, self.list_screen, self.chat_screen):
            w.setAutoFillBackground(True)
            pal = QPalette(w.palette())
            pal.setColor(QPalette.ColorRole.Window, page)
            w.setPalette(pal)
        if hasattr(self, "timeline_container"):
            tl = QColor(theme.TIMELINE_SCROLL_BG)
            self.timeline_container.setAutoFillBackground(True)
            p = QPalette(self.timeline_container.palette())
            p.setColor(QPalette.ColorRole.Window, tl)
            self.timeline_container.setPalette(p)

    def _profiles_dir_ready(self) -> None:
        self._profiles_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_profiles(self) -> dict:
        try:
            if self._profiles_path.exists():
                return json.loads(self._profiles_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Не удалось загрузить профили: {exc}")
        return {"active_profile_id": None, "profiles": []}

    def _save_profiles(self) -> None:
        self._profiles_dir_ready()
        self._profiles_path.write_text(
            json.dumps(self._profiles_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._refresh_profile_selector()
        self.requesterProfileChanged.emit()

    def _profiles(self) -> List[dict]:
        profiles = self._profiles_data.get("profiles")
        return profiles if isinstance(profiles, list) else []

    def set_profile_sidebar(self, sidebar: ProfileSidebarWidget) -> None:
        self._profile_sidebar = sidebar

    def _refresh_profile_selector(self) -> None:
        if self._profile_sidebar is not None:
            self._profile_sidebar.refresh_from_panel()

    def _filtered_tickets_for_list(self) -> List[dict]:
        filtered: List[dict] = []
        for row in self.tickets_cache:
            ticket = row.get("ticket", row)
            status = str(ticket.get("status") or "").strip().lower()
            is_closed = status == "closed"
            if is_closed and not self._show_closed_tickets:
                continue
            if (not is_closed) and not self._show_open_tickets:
                continue
            if ticket_matches_query(ticket, self._ticket_search_query):
                filtered.append(ticket)
        return filtered

    @staticmethod
    def _fingerprint_visible_tickets(filtered: List[dict]) -> str:
        return "\n".join(ticket_row_fingerprint(t) for t in filtered)

    def _on_ticket_search_changed(self, text: str) -> None:
        self._ticket_search_query = text or ""
        self._last_tickets_list_fingerprint = None
        self._update_tickets_list_ui()

    def _on_ticket_filter_changed(self) -> None:
        self._show_open_tickets = bool(self.filter_open_checkbox.isChecked())
        self._show_closed_tickets = bool(self.filter_closed_checkbox.isChecked())
        if not self._show_open_tickets and not self._show_closed_tickets:
            self._show_open_tickets = True
            self.filter_open_checkbox.blockSignals(True)
            self.filter_open_checkbox.setChecked(True)
            self.filter_open_checkbox.blockSignals(False)
        self._last_tickets_list_fingerprint = None
        self._update_tickets_list_ui()

    def _active_profile(self) -> Optional[dict]:
        active_id = self._profiles_data.get("active_profile_id")
        if not active_id:
            return None
        for profile in self._profiles():
            if profile.get("id") == active_id:
                return profile
        return None

    def current_requester_profile_summary(self) -> str:
        profile = self._active_profile()
        if not profile:
            return f"Без профиля | {self.user_display_name}"
        parts = [profile.get("full_name") or profile.get("display_name") or "Без имени"]
        location = " ".join(filter(None, [profile.get("building"), profile.get("room")]))
        if location:
            parts.append(location)
        if profile.get("phone"):
            parts.append(profile["phone"])
        return " | ".join(parts)

    def has_active_profile(self) -> bool:
        return self._active_profile() is not None

    def open_profile_manager(self, *, start_new: bool = False) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Профили инициатора")
        dialog.setMinimumWidth(540)
        theme.apply_agent_dialog_theme(dialog)
        layout = QVBoxLayout(dialog)

        profiles_list = QListWidget()
        profiles_list.setObjectName("ProfileManagerList")
        layout.addWidget(profiles_list)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        display_name = QLineEdit()
        full_name = QLineEdit()
        building = QLineEdit()
        room = QLineEdit()
        phone = QLineEdit()
        form.addRow("Отображаемое имя", display_name)
        form.addRow("ФИО", full_name)
        form.addRow("Корпус", building)
        form.addRow("Кабинет", room)
        form.addRow("Телефон", phone)
        layout.addWidget(form_widget)

        def refresh_profiles(
            selected_id: Optional[str] = None,
            *,
            skip_auto_select: bool = False,
        ) -> None:
            profiles_list.clear()
            for profile in self._profiles():
                title = profile.get("display_name") or profile.get("full_name") or "Без имени"
                item = QListWidgetItem(title)
                item.setData(Qt.ItemDataRole.UserRole, profile.get("id"))
                profiles_list.addItem(item)
                if selected_id and profile.get("id") == selected_id:
                    profiles_list.setCurrentItem(item)
            if skip_auto_select:
                return
            if profiles_list.count() and profiles_list.currentRow() < 0:
                profiles_list.setCurrentRow(0)

        def load_current() -> None:
            item = profiles_list.currentItem()
            profile_id = item.data(Qt.ItemDataRole.UserRole) if item else None
            profile = next((p for p in self._profiles() if p.get("id") == profile_id), None)
            display_name.setText(profile.get("display_name") if profile else "")
            full_name.setText(profile.get("full_name") if profile else "")
            building.setText(profile.get("building") if profile else "")
            room.setText(profile.get("room") if profile else "")
            phone.setText(profile.get("phone") if profile else "")

        profiles_list.currentItemChanged.connect(lambda *_: load_current())

        buttons = QHBoxLayout()
        btn_new = QPushButton("Новый")
        btn_save = QPushButton("Сохранить")
        btn_delete = QPushButton("Удалить")
        btn_select = QPushButton("Выбрать активным")
        btn_save.setObjectName("PrimaryButton")
        btn_select.setObjectName("PrimaryButton")
        btn_new.setObjectName("SecondaryButton")
        btn_delete.setObjectName("SecondaryButton")
        buttons.addWidget(btn_new)
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_delete)
        buttons.addWidget(btn_select)
        layout.addLayout(buttons)

        def current_profile_id() -> Optional[str]:
            item = profiles_list.currentItem()
            return item.data(Qt.ItemDataRole.UserRole) if item else None

        def save_profile(*, force_new: bool) -> None:
            profile_id = None if force_new else current_profile_id()
            payload = {
                "id": profile_id or str(uuid.uuid4()),
                "display_name": display_name.text().strip(),
                "full_name": full_name.text().strip(),
                "building": building.text().strip(),
                "room": room.text().strip(),
                "phone": phone.text().strip(),
            }
            profiles = [p for p in self._profiles() if p.get("id") != payload["id"]]
            profiles.append(payload)
            self._profiles_data["profiles"] = profiles
            if not self._profiles_data.get("active_profile_id"):
                self._profiles_data["active_profile_id"] = payload["id"]
            self._save_profiles()
            refresh_profiles(payload["id"])

        def save_clicked() -> None:
            save_profile(force_new=current_profile_id() is None)

        def start_blank_profile() -> None:
            profiles_list.clearSelection()
            display_name.clear()
            full_name.clear()
            building.clear()
            room.clear()
            phone.clear()

        def delete_profile() -> None:
            profile_id = current_profile_id()
            if not profile_id:
                return
            self._profiles_data["profiles"] = [p for p in self._profiles() if p.get("id") != profile_id]
            if self._profiles_data.get("active_profile_id") == profile_id:
                self._profiles_data["active_profile_id"] = self._profiles()[0].get("id") if self._profiles() else None
            self._save_profiles()
            refresh_profiles()
            load_current()

        def select_active() -> None:
            profile_id = current_profile_id()
            if not profile_id:
                return
            self._profiles_data["active_profile_id"] = profile_id
            self._save_profiles()
            dialog.accept()

        btn_new.clicked.connect(start_blank_profile)
        btn_save.clicked.connect(save_clicked)
        btn_delete.clicked.connect(delete_profile)
        btn_select.clicked.connect(select_active)

        active = self._profiles_data.get("active_profile_id")
        if start_new:
            refresh_profiles(None, skip_auto_select=True)
            profiles_list.clearSelection()
            load_current()
        else:
            refresh_profiles(active)
            load_current()
        dialog.exec()
        self._refresh_profile_selector()

    def _current_requester_payload(self) -> tuple[dict, str]:
        profile = self._active_profile() or {}
        requester_profile = {
            "full_name": profile.get("full_name") or "",
            "building": profile.get("building") or "",
            "room": profile.get("room") or "",
            "phone": profile.get("phone") or "",
        }
        display_name = profile.get("display_name") or profile.get("full_name") or self.user_display_name
        return requester_profile, display_name

    def _spawn_task(self, coro) -> Optional[asyncio.Task]:
        if self._is_closing:
            try:
                coro.close()
            except Exception:
                pass
            return None
        task = asyncio.create_task(coro)
        self._pending_tasks.add(task)

        def _done(done_task: asyncio.Task) -> None:
            self._pending_tasks.discard(done_task)
            try:
                done_task.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.debug(f"Фоновая задача ChatPanel завершилась с ошибкой: {exc}")

        task.add_done_callback(_done)
        return task

    def _cancel_pending_tasks(self) -> None:
        self._is_closing = True
        for task in list(self._pending_tasks):
            task.cancel()
        self._pending_tasks.clear()

    def _refresh_ticket_list_async(self) -> None:
        self._spawn_task(self._async_refresh_ticket_list())

    def _refresh_ticket_detail_async(self) -> None:
        if self.active_ticket_id:
            self._spawn_task(self._async_refresh_ticket_detail())

    async def _async_refresh_ticket_list(self) -> None:
        if self._is_closing:
            return
        self._ticket_list_refresh_seq += 1
        my_seq = self._ticket_list_refresh_seq
        try:
            result = await self.ticket_client.list_tickets()
            if self._is_closing or my_seq != self._ticket_list_refresh_seq:
                return
            if result.get("status") != "ok":
                return
            self.tickets_cache = result.get("tickets", [])
            filtered = self._filtered_tickets_for_list()
            fp = self._fingerprint_visible_tickets(filtered)
            if fp == self._last_tickets_list_fingerprint:
                return
            self._update_tickets_list_ui()
        except Exception as exc:
            if not self._is_closing:
                logger.error(f"Ошибка загрузки списка тикетов: {exc}")

    def _update_tickets_list_ui(self) -> None:
        filtered_tickets = self._filtered_tickets_for_list()
        self._last_tickets_list_fingerprint = self._fingerprint_visible_tickets(filtered_tickets)

        sm = self.tickets_list.selectionModel()
        prev_tid: Optional[str] = None
        cur = sm.currentIndex()
        if cur.isValid() and self._tickets_model is not None:
            prev_ticket = self._tickets_model.ticket_at_row(cur.row())
            if prev_ticket:
                prev_tid = str(prev_ticket.get("ticket_id") or "")

        current_id = self.active_ticket_id or prev_tid
        scroll_bar = self.tickets_list.verticalScrollBar()
        scroll_value = scroll_bar.value()

        self.tickets_list.setUpdatesEnabled(False)
        try:
            assert self._tickets_model is not None
            self._tickets_model.set_rows(filtered_tickets)
            self.tickets_empty_label.setVisible(len(filtered_tickets) == 0)
            if not filtered_tickets:
                sm.clear()
                QTimer.singleShot(0, lambda: scroll_bar.setValue(0))
            else:
                row = self._tickets_model.row_for_ticket_id(current_id) if current_id else -1
                if row < 0:
                    row = 0
                idx = self._tickets_model.index(row, 0)
                self.tickets_list.setCurrentIndex(idx)
                QTimer.singleShot(0, lambda: scroll_bar.setValue(min(scroll_value, scroll_bar.maximum())))
        finally:
            self.tickets_list.setUpdatesEnabled(True)

    def _latest_requester_read_event_id(self, ticket: dict, messages: List[dict], events: List[dict]) -> int:
        counters = ticket.get("chat_counters") or {}
        unread_messages = int(counters.get("requester_unread_messages") or 0)
        unread_tools = int(counters.get("requester_unread_tool_calls") or 0)
        if unread_messages <= 0 and unread_tools <= 0:
            return 0

        latest_event_id = 0
        for message in messages:
            event_id = message.get("event_id")
            try:
                latest_event_id = max(latest_event_id, int(event_id))
            except (TypeError, ValueError):
                pass
        for event in events:
            event_id = event.get("id") or event.get("event_id")
            try:
                latest_event_id = max(latest_event_id, int(event_id))
            except (TypeError, ValueError):
                pass
        return latest_event_id

    def _maybe_mark_ticket_read(self, ticket: dict, messages: List[dict], events: List[dict]) -> None:
        ticket_id = str(ticket.get("ticket_id") or "")
        if not ticket_id:
            return
        last_read_event_id = self._latest_requester_read_event_id(ticket, messages, events)
        if last_read_event_id <= 0:
            return
        if last_read_event_id <= int(self._last_marked_read_event_id.get(ticket_id, 0)):
            return
        previous_value = int(self._last_marked_read_event_id.get(ticket_id, 0))
        self._last_marked_read_event_id[ticket_id] = last_read_event_id
        self._spawn_task(self._async_mark_ticket_read(ticket_id, last_read_event_id, previous_value))

    async def _async_mark_ticket_read(self, ticket_id: str, last_read_event_id: int, previous_value: int) -> None:
        try:
            await self.ticket_client.mark_ticket_read(ticket_id, last_read_event_id)
            await self._async_refresh_ticket_list()
        except Exception as exc:
            if not self._is_closing:
                logger.warning(f"Не удалось отметить сообщения как прочитанные для {ticket_id}: {exc}")
                self._last_marked_read_event_id[ticket_id] = previous_value

    async def _async_refresh_ticket_detail(self) -> None:
        if self._is_closing or not self.active_ticket_id:
            return
        self._ticket_detail_refresh_seq += 1
        my_seq = self._ticket_detail_refresh_seq
        try:
            result = await self.ticket_client.get_ticket(self.active_ticket_id)
            if self._is_closing or my_seq != self._ticket_detail_refresh_seq:
                return
            if result.get("status") != "ok":
                return
            self._update_ticket_detail_ui(
                result.get("ticket", {}),
                result.get("messages", []),
                result.get("events", []),
            )
        except Exception as exc:
            if not self._is_closing:
                logger.error(f"Ошибка загрузки тикета {self.active_ticket_id}: {exc}")

    def _detail_header_signature(self, ticket: dict, messages: List[dict]) -> str:
        return json.dumps(
            {
                "ticket_id": ticket.get("ticket_id"),
                "code": ticket.get("ticket_code"),
                "title": ticket.get("title"),
                "status": ticket.get("status"),
                "counters": ticket.get("chat_counters"),
                "updated_at": ticket.get("updated_at"),
                "resolved_at": ticket.get("resolved_at"),
                "closed_at": ticket.get("closed_at"),
                "public_access_url": ticket.get("public_access_url"),
                "public_access_code_hint": ticket.get("public_access_code_hint"),
                "extracted_code": self._extract_public_access_code(ticket, messages),
                "meta_html": self._build_ticket_meta_html(ticket),
            },
            sort_keys=True,
            default=str,
        )

    def _apply_ticket_detail_header(self, ticket: dict, messages: List[dict]) -> None:
        code = ticket.get("ticket_code") or ticket.get("ticket_id", "")
        title = ticket.get("title") or "Без названия"
        status = ticket.get("status") or "unknown"
        status_fg, status_bg = ticket_status_colors(status)
        counters = ticket.get("chat_counters") or {}
        unread_messages = int(counters.get("requester_unread_messages") or 0)
        unread_tools = int(counters.get("requester_unread_tool_calls") or 0)
        status_suffix_parts: List[str] = []
        if unread_messages > 0:
            status_suffix_parts.append(f"сообщения: {unread_messages}")
        if unread_tools > 0:
            status_suffix_parts.append(f"вызовы: {unread_tools}")
        status_suffix = ""
        if status_suffix_parts:
            status_suffix = " • Непрочитано " + ", ".join(status_suffix_parts)
        safe_code = self._escape_html(str(code))
        safe_title = self._escape_html(str(title))
        info_html = f"Тикет <a href='copy_ticket_code:{safe_code}'>#{safe_code}</a><br>{safe_title}"
        status_text = f"Статус тикета: {ticket_status_label(status)}{status_suffix}"
        status_style = (
            f"font-weight: 700; padding: 10px 14px; border-radius: 14px; background: {status_bg}; color: {status_fg};"
        )
        meta_html = self._build_ticket_meta_html(ticket)
        self.ticket_info_label.setText(info_html)
        self.ticket_status_top.setText(status_text)
        self.ticket_status_top.setStyleSheet(status_style)
        self.ticket_meta_label.setText(meta_html)
        self._refresh_top_pinned_info(ticket, messages)
        self._refresh_pinned_messages_label(ticket.get("ticket_id") or "")
        self._apply_ticket_background(status)

    def _build_timeline_items(self, ticket: dict, messages: List[dict], events: List[dict]) -> List[tuple[float, str, dict]]:
        requester_name = ticket.get("requester_display_name") or "Пользователь"
        requester_profile = ticket.get("requester_profile") or {}
        requester_full_name = (
            requester_profile.get("full_name")
            or ticket.get("requester_display_name")
            or "Пользователь"
        )
        assignee_name = ticket.get("assignee_id") or "Поддержка"
        message_index: Dict[str, dict] = {
            str(msg.get("message_id") or ""): msg
            for msg in messages
            if str(msg.get("message_id") or "").strip()
        }
        items: List[tuple[float, str, dict]] = []
        for message in messages:
            ts = message.get("ts")
            text = (message.get("text") or "").strip()
            sender_kind = message_visual_role(message)
            sender = requester_name if sender_kind == "self" else assignee_name if sender_kind == "support" else "Система"
            reply_to = self._resolve_reply_reference(
                message.get("reply_to") or ((message.get("metadata") or {}).get("reply_to")),
                message_index,
            )
            message_context = {
                "message_id": message.get("message_id"),
                "preview": text or " ".join(self._message_attachment_labels(message)),
                "sender_role": message.get("from_role"),
                "sender_display_name": requester_full_name if sender_kind == "self" else sender,
                "ts": ts,
            }
            items.append(
                (
                    self._ts_sort_value(ts),
                    "msg",
                    {
                        "bubble_role": "self" if sender_kind == "self" else "support" if sender_kind == "support" else "event",
                        "sender": requester_full_name if sender_kind == "self" else sender,
                        "text": text or "Вложение",
                        "attachments": self._message_attachment_labels(message),
                        "ts_text": self._format_ts(ts),
                        "menu_text": text or " ".join(self._message_attachment_labels(message)),
                        "reply_to": reply_to,
                        "message_context": message_context,
                    },
                )
            )
        _HIDDEN = frozenset({
            "chat_message", "job_started", "job_running", "job_succeeded", "job_completed",
            "chat_session", "chat_ended", "event_delivered", "tool_response", "routing_applied",
            "initial_message_sent_to_agent", "initial_message_pending_delivery", "initial_message_send_failed",
            "no_active_job", "message_read",
        })
        merged_events = list(events) + self.local_action_buffer.get(self.active_ticket_id, [])
        for event in merged_events:
            ev_type = event.get("type") or event.get("event_type") or ""
            if ev_type in _HIDDEN:
                continue
            ts = event.get("ts")
            line = self._format_event_text(event)
            items.append(
                (
                    self._ts_sort_value(ts),
                    "event",
                    {
                        "bubble_role": "event",
                        "sender": "",
                        "text": f"⚙ {line}",
                        "attachments": [],
                        "ts_text": self._format_ts(ts),
                        "menu_text": "",
                    },
                )
            )
        items.sort(key=lambda x: x[0])
        return items

    def _update_ticket_detail_ui(self, ticket: dict, messages: List[dict], events: List[dict]) -> None:
        if self._bubble_menu_open:
            self._pending_ticket_snapshot = (dict(ticket), list(messages), list(events))
            return

        timeline_sig = self._build_timeline_signature(ticket, messages, events)
        header_sig = self._detail_header_signature(ticket, messages)

        if timeline_sig == self._last_timeline_html and header_sig == self._last_detail_header_sig:
            self._maybe_mark_ticket_read(ticket, messages, events)
            return

        header_changed = header_sig != self._last_detail_header_sig
        timeline_changed = timeline_sig != self._last_timeline_html

        if header_changed:
            self._last_detail_header_sig = header_sig
            self._apply_ticket_detail_header(ticket, messages)

        self._maybe_prompt_resolution_confirmation(ticket)

        if not timeline_changed:
            self._pending_ticket_snapshot = None
            self._maybe_mark_ticket_read(ticket, messages, events)
            return

        items = self._build_timeline_items(ticket, messages, events)
        scroll_bar = self.timeline_scroll.verticalScrollBar()
        previous_value = scroll_bar.value()
        previous_max = scroll_bar.maximum()
        stick_to_bottom = previous_max == 0 or previous_value >= max(previous_max - 24, 0)
        self.timeline_scroll.setUpdatesEnabled(False)
        try:
            self._render_timeline_widgets(items)
        finally:
            self.timeline_scroll.setUpdatesEnabled(True)
        self._last_timeline_html = timeline_sig
        self._pending_ticket_snapshot = None
        self._restore_timeline_scroll(previous_value, stick_to_bottom)
        self._maybe_mark_ticket_read(ticket, messages, events)

    def _build_ticket_meta_html(self, ticket: dict) -> str:
        requester = ticket.get("requester_display_name") or "Пользователь"
        profile = ticket.get("requester_profile") or {}
        location = " ".join(
            part for part in (profile.get("building"), profile.get("room")) if part
        ).strip() or "—"
        rows = [
            ("Пользователь", requester),
            ("ФИО", profile.get("full_name") or "—"),
            ("Кабинет", location),
            ("Телефон", profile.get("phone") or "—"),
            ("Приоритет", ticket.get("priority_class") or ticket.get("priority") or "—"),
            ("Очередь", ticket.get("queue_code") or ticket.get("queue_id") or "—"),
            ("Исполнитель", ticket.get("assignee_id") or "Не назначен"),
            ("Создан", self._format_ts(ticket.get("created_at")) or "—"),
            ("Обновлён", self._format_ts(ticket.get("updated_at")) or "—"),
            ("Решён", self._format_ts(ticket.get("resolved_at")) or "—"),
            ("Закрыт", self._format_ts(ticket.get("closed_at")) or "—"),
            ("Описание", (ticket.get("description") or "—").replace("\n", " ")),
        ]
        return "".join(
            f"<div style='margin-bottom:8px; font-size:{theme.BODY_PT}pt; line-height:1.5;'>"
            f"<span style='color:{theme.TEXT_MUTED}; font-weight:600;'>{self._escape_html(label)}:</span> "
            f"<span style='color:{theme.TEXT_PRIMARY};'>{self._escape_html(str(value))}</span></div>"
            for label, value in rows
        )

    def _message_attachment_labels(self, message: dict) -> List[str]:
        attachments = message.get("attachments") or []
        attachment_refs = message.get("attachment_refs") or []
        labels: List[str] = []
        for item in attachments[:5]:
            if not isinstance(item, dict):
                continue
            label = item.get("name") or item.get("artifact_id") or item.get("mime_type") or "Вложение"
            mime = str(item.get("mime_type") or "").lower()
            prefix = "📷 " if mime.startswith("image/") else "📎 "
            labels.append(f"{prefix}{label}")
        if not labels and attachment_refs:
            labels = [f"📎 {ref}" for ref in attachment_refs[:5]]
        return labels

    def _resolve_reply_reference(self, raw_reply: Optional[dict], message_index: Optional[Dict[str, dict]] = None) -> Optional[dict]:
        if not isinstance(raw_reply, dict):
            return None
        parent_message_id = str(raw_reply.get("parent_message_id") or "").strip()
        preview = str(raw_reply.get("preview") or raw_reply.get("target_preview") or "").strip()
        sender_role = str(raw_reply.get("sender_role") or raw_reply.get("from_role") or "").strip().lower()
        sender_display_name = str(raw_reply.get("sender_display_name") or raw_reply.get("sender") or "").strip()
        ts = str(raw_reply.get("ts") or raw_reply.get("target_ts") or "").strip()
        if message_index and parent_message_id and parent_message_id in message_index:
            source = message_index[parent_message_id]
            preview = preview or str(source.get("text") or "").strip()
            sender_role = sender_role or str(source.get("from_role") or "").strip().lower()
            sender_display_name = sender_display_name or str(source.get("sender_display_name") or "").strip()
            ts = ts or str(source.get("ts") or "").strip()
        if not preview and not parent_message_id:
            return None
        if not sender_display_name:
            if sender_role in {"support", "admin"}:
                sender_display_name = "Поддержка"
            elif sender_role in {"user", "requester", "agent"}:
                sender_display_name = "Вы"
            else:
                sender_display_name = "Сообщение"
        return {
            "parent_message_id": parent_message_id,
            "preview": preview[:280],
            "sender_role": sender_role,
            "sender_display_name": sender_display_name,
            "ts": ts,
        }

    def _build_timeline_signature(self, ticket: dict, messages: List[dict], events: List[dict]) -> str:
        merged_events = list(events) + self.local_action_buffer.get(self.active_ticket_id, [])
        payload = {
            "ticket_id": ticket.get("ticket_id"),
            "ticket_status": ticket.get("status"),
            "ticket_updated_at": ticket.get("updated_at"),
            "messages": [
                {
                    "id": msg.get("message_id"),
                    "ts": msg.get("ts"),
                    "text": msg.get("text"),
                    "from_role": msg.get("from_role"),
                    "attachments": msg.get("attachments"),
                    "attachment_refs": msg.get("attachment_refs"),
                    "reply_to": msg.get("reply_to") or ((msg.get("metadata") or {}).get("reply_to")),
                }
                for msg in messages
            ],
            "events": merged_events,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)

    def _restore_timeline_scroll(self, previous_value: int, stick_to_bottom: bool) -> None:
        scroll_bar = self.timeline_scroll.verticalScrollBar()

        def apply_scroll() -> None:
            if stick_to_bottom:
                scroll_bar.setValue(scroll_bar.maximum())
            else:
                scroll_bar.setValue(min(previous_value, scroll_bar.maximum()))

        QTimer.singleShot(0, apply_scroll)
        QTimer.singleShot(30, apply_scroll)
        QTimer.singleShot(90, apply_scroll)

    def _clear_timeline_widgets(self) -> None:
        self._timeline_bubbles.clear()
        while self.timeline_layout.count():
            item = self.timeline_layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                while child_layout.count():
                    sub_item = child_layout.takeAt(0)
                    sub_widget = sub_item.widget()
                    if sub_widget is not None:
                        sub_widget.deleteLater()

    def _message_bubble_max_width(self) -> int:
        viewport_width = max(self.timeline_scroll.viewport().width(), 480)
        return int(viewport_width * 0.68)

    def _create_timeline_row(self, bubble: MessageBubbleWidget, alignment: str) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        bubble.setMaximumWidth(self._message_bubble_max_width())
        self._timeline_bubbles.append(bubble)

        if alignment == "right":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble)
        elif alignment == "center":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble)
            row_layout.addStretch(1)
        else:
            row_layout.addWidget(bubble)
            row_layout.addStretch(1)
        return row

    def _render_timeline_widgets(self, items: List[tuple[float, str, dict]]) -> None:
        self._clear_timeline_widgets()
        if not items:
            empty = MessageBubbleWidget(self, "event", "", "Пока нет сообщений.", "", [])
            self.timeline_layout.addWidget(self._create_timeline_row(empty, "center"))
            return

        for _sort_value, kind, payload in items:
            bubble = MessageBubbleWidget(
                self,
                payload.get("bubble_role", "event"),
                payload.get("sender", ""),
                payload.get("text", ""),
                payload.get("ts_text", ""),
                payload.get("attachments", []),
                payload.get("menu_text", ""),
                payload.get("reply_to"),
                payload.get("message_context"),
            )
            alignment = "center" if kind == "event" else ("right" if payload.get("bubble_role") == "support" else "left")
            self.timeline_layout.addWidget(self._create_timeline_row(bubble, alignment))
        self.timeline_layout.addStretch(1)

    def _update_timeline_bubble_widths(self) -> None:
        max_width = self._message_bubble_max_width()
        for bubble in self._timeline_bubbles:
            bubble.setMaximumWidth(max_width)

    def _maybe_prompt_resolution_confirmation(self, ticket: dict) -> None:
        if not ticket or not can_user_confirm_close(ticket):
            self.resolution_message_widget.hide()
            return
        ticket_id = str(ticket.get("ticket_id") or "")
        prompt_key = f"{ticket_id}:{ticket.get('resolved_at') or ticket.get('updated_at') or 'resolved'}"
        if not ticket_id or prompt_key in self._resolution_prompt_keys or self._resolution_prompt_open_for == ticket_id:
            return
        self._resolution_prompt_keys.add(prompt_key)
        self._resolution_prompt_open_for = ticket_id

        self.resolution_message_widget.show()

    def _ts_sort_value(self, value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            raw = normalize_iso_ts(value)
            if not raw:
                return 0.0
            try:
                return float(raw)
            except ValueError:
                pass
            try:
                return datetime.fromisoformat(raw).timestamp()
            except ValueError:
                return 0.0
        return 0.0

    def _format_ts(self, value) -> str:
        return format_ts_short(value)

    @staticmethod
    def _escape_html(s: str) -> str:
        if not s:
            return ""
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _format_event_text(self, event: dict) -> str:
        event_type = event.get("type") or event.get("event_type") or "event"
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        tool_name = str(event.get("tool_name") or payload.get("tool_name") or "").strip()
        action = str(event.get("action") or payload.get("action") or "").strip()
        status = str(event.get("status") or payload.get("status") or "").strip().lower()
        message = str(event.get("message") or payload.get("message") or payload.get("description") or "").strip()
        error = str(payload.get("error") or payload.get("error_message") or "").strip()

        tool_label = self._friendly_tool_name(tool_name or action)
        status_label = self._friendly_status_label(status)

        if event_type == "tool_requested":
            return f"Запрошено действие {tool_label}."
        if event_type == "tool_started":
            return f"Запущено действие {tool_label}."
        if event_type == "tool_running":
            return message or f"Действие {tool_label} выполняется."
        if event_type == "tool_finished":
            if error:
                return f"Действие {tool_label} завершилось с ошибкой: {error}"
            if status_label:
                return f"Действие {tool_label} завершено: {status_label}."
            return f"Действие {tool_label} завершено."
        if event_type == "tool_result":
            if message:
                return f"Результат действия {tool_label}: {message}"
            return f"Получен результат действия {tool_label}."
        if event_type == "collect_progress":
            return message or f"Идёт выполнение действия {tool_label}."
        if event_type == "consent_required":
            return f"Нужно подтвердить действие {tool_label}."
        if event_type == "notification":
            return message or "Получено уведомление."
        if event_type == "module_observation":
            return message or f"Получено сообщение от модуля {tool_label}."
        if event_type == "agent_action":
            if action:
                return f"Агент выполняет действие: {self._friendly_action_label(action)}."
            return message or "Агент выполняет действие."

        if message:
            return message
        if action:
            return f"Событие: {self._friendly_action_label(action)}."
        return self._friendly_action_label(event_type)

    @staticmethod
    def _friendly_status_label(status: str) -> str:
        mapping = {
            "ok": "успешно",
            "success": "успешно",
            "succeeded": "успешно",
            "done": "успешно",
            "finished": "завершено",
            "running": "выполняется",
            "pending": "ожидание",
            "queued": "в очереди",
            "failed": "ошибка",
            "error": "ошибка",
            "denied": "отклонено",
            "cancelled": "отменено",
            "canceled": "отменено",
        }
        return mapping.get((status or "").strip().lower(), status or "")

    @staticmethod
    def _friendly_tool_name(name: str) -> str:
        raw = (name or "").strip()
        if not raw:
            return "«действие»"
        mapping = {
            "screen.collect": "«Скриншот экрана»",
            "screen.record": "«Запись экрана»",
            "screen.capture": "«Снимок экрана»",
        }
        return mapping.get(raw, f"«{raw}»")

    @staticmethod
    def _friendly_action_label(action: str) -> str:
        raw = (action or "").strip()
        if not raw:
            return "действие"
        mapping = {
            "prepare_screen_capture": "подготовка скриншота",
            "screen_capture_done": "скриншот готов",
            "prepare_screen_recording": "подготовка записи экрана",
            "screen_recording_done": "запись экрана завершена",
        }
        return mapping.get(raw, raw.replace("_", " "))

    def _on_create_ticket(self) -> None:
        if not self.has_active_profile():
            QMessageBox.warning(self, "Профиль обязателен", "Сначала заполните и выберите профиль инициатора.")
            self.open_profile_manager(start_new=True)
            return
        dialog = TicketCreateDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.payload()
        self._spawn_task(self._async_create_ticket(payload))

    async def _async_create_ticket(self, payload: dict) -> None:
        description = payload.get("description", "").strip()
        if not description:
            QMessageBox.warning(self, "Ошибка", "Опишите проблему")
            return

        urgency = bool(payload.get("urgency"))
        importance = bool(payload.get("importance"))
        urgency_reason = payload.get("urgency_reason") or ("Срочно" if urgency else "Несрочно")
        importance_reason = payload.get("importance_reason") or ("Важно" if importance else "Неважно")
        requester_profile, display_name = self._current_requester_payload()

        self.create_ticket_btn.setEnabled(False)
        try:
            result = await self.ticket_client.create_ticket(
                description=description,
                title="Support Request",
                tags=[],
                requester_profile=requester_profile,
                user_display_name=display_name,
                urgency=urgency,
                importance=importance,
                urgency_reason=urgency_reason,
                importance_reason=importance_reason,
            )
            if result.get("status") != "ok":
                raise RuntimeError(str(result))

            ticket = result.get("ticket", {})
            self.active_ticket_id = ticket.get("ticket_id")
            self._last_timeline_html = None
            self._last_detail_header_sig = None
            self._pending_ticket_snapshot = None
            self._ticket_detail_timer.start(2500)
            await self._async_refresh_ticket_list()
            await self._async_refresh_ticket_detail()
            self._show_chat_screen()

            code = result.get("public_access_code") or "—"
            url = result.get("public_access_url") or ""
            QMessageBox.information(self, "Тикет создан", f"Код: {code}\n{url}")
        except Exception as exc:
            logger.error(f"Ошибка создания тикета: {exc}")
            QMessageBox.critical(self, "Ошибка", str(exc))
        finally:
            self.create_ticket_btn.setEnabled(True)

    def _on_open_ticket(self) -> None:
        cur = self.tickets_list.currentIndex()
        if not cur.isValid() or self._tickets_model is None:
            return
        ticket = self._tickets_model.ticket_at_row(cur.row())
        if not ticket:
            return
        self.active_ticket_id = ticket.get("ticket_id")
        self._last_timeline_html = None
        self._last_detail_header_sig = None
        self._pending_ticket_snapshot = None
        self._ticket_detail_timer.start(2500)
        self._refresh_ticket_detail_async()
        self._show_chat_screen()

    def _on_send(self) -> None:
        if not self.active_ticket_id:
            return
        text = self.input_line.text().strip()
        if not text:
            return
        self._spawn_task(self._async_send_message(text))

    async def _async_send_message(self, text: str) -> None:
        try:
            self.send_btn.setEnabled(False)
            metadata = None
            reply_to = None
            if self._reply_target:
                reply_to = {
                    "parent_message_id": self._reply_target.get("message_id"),
                    "preview": self._reply_target.get("preview", ""),
                    "sender_role": self._reply_target.get("sender_role"),
                    "sender_display_name": self._reply_target.get("sender_display_name"),
                    "target_ts": self._reply_target.get("ts"),
                }
                metadata = {
                    PINNED_STUB_META_KEY: {
                        "source": "agent_gui_stub",
                        "target_preview": self._reply_target.get("preview", ""),
                        "target_ts": self._reply_target.get("ts"),
                    }
                }
            await self.ticket_client.send_message(
                self.active_ticket_id,
                text,
                from_role="user",
                metadata=metadata,
                reply_to=reply_to,
            )
            self.input_line.clear()
            self._clear_reply_stub()
            await self._async_refresh_ticket_detail()
            self._restore_timeline_scroll(0, True)
        except Exception as exc:
            logger.error(f"Ошибка отправки сообщения: {exc}")
            QMessageBox.critical(self, "Ошибка", str(exc))
        finally:
            self.send_btn.setEnabled(True)

    def _on_attach_files(self) -> None:
        if not self.active_ticket_id:
            QMessageBox.information(self, "Тикет", "Сначала откройте тикет.")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите вложения")
        if not files:
            return
        self._spawn_task(self._async_attach_files(files))

    def _on_attach_photo(self) -> None:
        self._pick_and_attach_files("Выберите фото", "Изображения (*.png *.jpg *.jpeg *.bmp *.webp)")

    def _on_attach_document(self) -> None:
        self._pick_and_attach_files(
            "Выберите документ",
            "Документы (*.pdf *.doc *.docx *.txt *.rtf *.xls *.xlsx *.csv *.ppt *.pptx)"
        )

    def _on_attach_any_file(self) -> None:
        self._pick_and_attach_files("Выберите файл", "Все файлы (*.*)")

    def _pick_and_attach_files(self, title: str, file_filter: str) -> None:
        if not self.active_ticket_id:
            QMessageBox.information(self, "Тикет", "Сначала откройте тикет.")
            return
        files, _ = QFileDialog.getOpenFileNames(self, title, "", file_filter)
        if not files:
            return
        self._spawn_task(self._async_attach_files(files))

    async def _async_attach_files(self, files: List[str]) -> None:
        refs: List[str] = []
        try:
            self.tool_status_label.setText("Загружаю вложения...")
            for file_path in files:
                ext = Path(file_path).suffix.lower()
                kind = "file"
                if ext in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
                    kind = "screenshot"
                elif ext in {".mp4", ".mov", ".mkv", ".avi"}:
                    kind = "screen_recording"
                uploaded = await self.ticket_client.upload_attachment(
                    self.active_ticket_id,
                    file_path,
                    kind=kind,
                )
                artifact_id = uploaded.get("artifact_id")
                if artifact_id:
                    refs.append(artifact_id)
            if not refs:
                self.tool_status_label.setText("Нет загруженных файлов")
                return
            text = self.input_line.text().strip()
            if not text:
                text = "Вложение" if len(refs) == 1 else f"Вложения ({len(refs)})"
            reply_to = None
            metadata = None
            if self._reply_target:
                reply_to = {
                    "parent_message_id": self._reply_target.get("message_id"),
                    "preview": self._reply_target.get("preview", ""),
                    "sender_role": self._reply_target.get("sender_role"),
                    "sender_display_name": self._reply_target.get("sender_display_name"),
                    "target_ts": self._reply_target.get("ts"),
                }
                metadata = {
                    PINNED_STUB_META_KEY: {
                        "source": "agent_gui_stub",
                        "target_preview": self._reply_target.get("preview", ""),
                        "target_ts": self._reply_target.get("ts"),
                    }
                }
            await self.ticket_client.send_message(
                self.active_ticket_id,
                text,
                from_role="user",
                attachment_refs=refs,
                metadata=metadata,
                reply_to=reply_to,
            )
            self.input_line.clear()
            self._clear_reply_stub()
            self.tool_status_label.setText(f"Отправлено вложений: {len(refs)}")
            await self._async_refresh_ticket_detail()
            self._restore_timeline_scroll(0, True)
        except Exception as exc:
            logger.error(f"Ошибка отправки вложений: {exc}")
            self.tool_status_label.setText("Ошибка отправки вложений")
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _on_send_screenshot(self) -> None:
        if not self.active_ticket_id:
            QMessageBox.information(self, "Тикет", "Сначала откройте тикет.")
            return
        self._spawn_task(self._async_run_tool("screen.collect", {}, "Запрос на скриншот отправлен"))

    def _on_send_video(self) -> None:
        if not self.active_ticket_id:
            QMessageBox.information(self, "Тикет", "Сначала откройте тикет.")
            return
        self._spawn_task(
            self._async_run_tool(
                "screen.record",
                {"duration_sec": 60},
                "Запрос на запись видео отправлен",
            )
        )

    async def _async_run_tool(self, tool_name: str, params: dict, success_text: str) -> None:
        try:
            self.tool_status_label.setText("Запускаю инструмент...")
            await self.ticket_client.run_tool(
                device_id=self.device_id,
                ticket_id=self.active_ticket_id,
                tool_name=tool_name,
                params=params,
            )
            self.tool_status_label.setText(success_text)
            await self._async_refresh_ticket_detail()
        except Exception as exc:
            logger.error(f"Ошибка запуска инструмента {tool_name}: {exc}")
            self.tool_status_label.setText(f"Ошибка {tool_name}")
            QMessageBox.warning(self, "Инструмент", str(exc))

    def _on_reject_resolution(self) -> None:
        self.resolution_message_widget.hide()
        QMessageBox.information(self, "Решение отклонено", "Вы можете продолжить переписку в тикете.")

    async def _async_close_ticket(self) -> None:
        try:
            await self.ticket_client.close_ticket(
                self.active_ticket_id,
                reason="requester_confirmed_resolution",
                closed_by_role="user",
            )
            await self._async_refresh_ticket_list()
            await self._async_refresh_ticket_detail()
        except Exception as exc:
            logger.error(f"Ошибка закрытия тикета: {exc}")
            QMessageBox.critical(self, "Ошибка", str(exc))

    def add_local_event(self, ticket_id: str, event: dict) -> None:
        self.local_action_buffer.setdefault(ticket_id, []).append(event)
        if ticket_id == self.active_ticket_id:
            self._refresh_ticket_detail_async()

    def attach_to_job(self, job_id: str) -> None:
        self.current_job_id = job_id
        self.chatSessionChanged.emit(job_id or "")

    def append_event(self, event: dict, source: str = "agent") -> None:
        event_copy = dict(event or {})
        event_copy.setdefault("source", source)
        ticket_id = event_copy.get("ticket_id") or self.active_ticket_id
        if ticket_id:
            self.add_local_event(ticket_id, event_copy)

    def _stop_ticket_list_polling(self) -> None:
        if self._ticket_list_timer.isActive():
            self._ticket_list_timer.stop()
        self._cancel_pending_tasks()

    def _stop_ticket_detail_polling(self) -> None:
        if self._ticket_detail_timer.isActive():
            self._ticket_detail_timer.stop()
        self._cancel_pending_tasks()

    def _show_list_screen(self) -> None:
        self.stacked.setCurrentWidget(self.list_screen)
        self.stacked.update()
        self.list_screen.update()
        self.listNavigationVisibilityChanged.emit(True)

    def _show_chat_screen(self) -> None:
        self.stacked.setCurrentWidget(self.chat_screen)
        self.stacked.update()
        self.chat_screen.update()
        self.input_line.setFocus()
        self.listNavigationVisibilityChanged.emit(False)

    def _open_message_context_menu(self, global_pos, message_context: dict) -> None:
        menu = QMenu(self)
        copy_action = menu.addAction("Копировать текст")
        reply_action = menu.addAction("Ответить")
        pin_action = menu.addAction("Закрепить сообщение")
        self._bubble_menu_open = True
        try:
            chosen = menu.exec(global_pos)
        finally:
            self._bubble_menu_open = False
        preview = str(message_context.get("preview") or "").strip()
        if chosen == copy_action:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(preview)
        elif chosen == reply_action:
            self._set_reply_target(message_context)
        elif chosen == pin_action:
            self._pin_selected_message(preview)
        if self._pending_ticket_snapshot:
            snapshot = self._pending_ticket_snapshot
            self._pending_ticket_snapshot = None
            QTimer.singleShot(0, lambda: self._update_ticket_detail_ui(*snapshot))

    def _set_reply_target(self, message_context: dict) -> None:
        if not self.active_ticket_id:
            return
        preview = str(message_context.get("preview") or "").strip()
        if not preview:
            QMessageBox.information(self, "Ответ", "Сначала выделите текст сообщения для ответа.")
            return
        preview = preview[:180]
        self._reply_target = {
            "message_id": str(message_context.get("message_id") or "").strip(),
            "preview": preview,
            "ts": message_context.get("ts") or datetime.now().isoformat(),
            "sender_role": str(message_context.get("sender_role") or "").strip().lower(),
            "sender_display_name": str(message_context.get("sender_display_name") or "").strip(),
        }
        author = self._reply_target.get("sender_display_name") or "сообщение"
        self.reply_stub_label.setText(f"Ответ на {author}: {preview}")
        self.reply_stub_label.show()
        self.input_line.setFocus()

    def _clear_reply_stub(self) -> None:
        self._reply_target = None
        self.reply_stub_label.hide()
        self.reply_stub_label.setText("")

    def _pin_selected_message(self, selected_text: str) -> None:
        ticket_id = self.active_ticket_id
        if not ticket_id:
            return
        preview = (selected_text or "").strip()
        if not preview:
            QMessageBox.information(self, "Закрепить", "Сначала выделите текст сообщения для закрепления.")
            return
        items = self._pinned_messages.setdefault(ticket_id, [])
        items.append({"text": preview[:220], "ts": datetime.now().isoformat()})
        self._refresh_pinned_messages_label(ticket_id)

    def _refresh_pinned_messages_label(self, ticket_id: str) -> None:
        items = self._pinned_messages.get(ticket_id) or []
        if not items:
            self.pinned_messages_widget.hide()
            return
        lines = [f"• {item.get('text', '')}" for item in items[-3:]]
        self.pinned_messages_label.setText("Закреплённые сообщения:\n" + "\n".join(lines))
        self.pinned_messages_widget.show()

    def _extract_public_access_code(self, ticket: dict, messages: List[dict]) -> str:
        code = str(ticket.get("public_access_code") or "").strip().upper()
        if code:
            return code
        for msg in reversed(messages or []):
            metadata = msg.get("metadata") if isinstance(msg.get("metadata"), dict) else {}
            candidate = str(metadata.get("public_access_code") or "").strip().upper()
            if candidate:
                return candidate
            text = str(msg.get("text") or "")
            if "Код авторизации" in text:
                match = re.search(r"\b[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{8}\b", text.upper())
                if match:
                    return match.group(0)
        return ""

    @staticmethod
    def _append_access_code_to_url(url: str, code: str) -> str:
        if not url or not code:
            return url or ""
        glue = "&" if "?" in url else "?"
        return f"{url}{glue}code={code}"

    def _refresh_top_pinned_info(self, ticket: dict, messages: List[dict]) -> None:
        full_code = self._extract_public_access_code(ticket, messages)
        code_hint = str(ticket.get("public_access_code_hint") or "").strip().upper()
        shown_code = full_code or (f"****{code_hint}" if code_hint else "—")
        raw_url = str(ticket.get("public_access_url") or "").strip()
        url = self._append_access_code_to_url(raw_url, full_code)
        if url:
            self.top_pinned_info.setText(
                f"Код авторизации: <a href='copy_auth_code:{self._escape_html(str(full_code or shown_code))}'><b>{self._escape_html(str(shown_code))}</b></a><br>"
                f"Ссылка на веб-тикет: <a href='{self._escape_html(str(url))}'>{self._escape_html(str(url))}</a>"
            )
        else:
            self.top_pinned_info.setText(
                f"Код авторизации: <a href='copy_auth_code:{self._escape_html(str(full_code or shown_code))}'><b>{self._escape_html(str(shown_code))}</b></a><br>Ссылка: —"
            )

    def _apply_ticket_background(self, status: str) -> None:
        normalized = str(status or "").strip().lower()
        bg = theme.CHAT_SCREEN_SOLID_OPEN
        if normalized == "resolved":
            bg = theme.CHAT_SCREEN_SOLID_RESOLVED
        elif normalized == "closed":
            bg = theme.CHAT_SCREEN_SOLID_CLOSED
        self.chat_screen.setStyleSheet(
            f"QWidget#ChatScreenRoot {{ background-color: {bg}; border-radius: 10px; }}"
        )
        pal = QPalette(self.chat_screen.palette())
        pal.setColor(QPalette.ColorRole.Window, QColor(bg))
        self.chat_screen.setPalette(pal)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_timeline_bubble_widths()

    def _clear_pinned_messages_for_active_ticket(self) -> None:
        if not self.active_ticket_id:
            return
        self._pinned_messages.pop(self.active_ticket_id, None)
        self._refresh_pinned_messages_label(self.active_ticket_id)

    def _on_ticket_code_clicked(self, link: str) -> None:
        prefix = "copy_ticket_code:"
        if not link.startswith(prefix):
            return
        code = link[len(prefix):].strip()
        if not code:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(code)
        QMessageBox.information(self, "Скопировано", f"Номер тикета скопирован: {code}")

    def _on_top_info_link_activated(self, link: str) -> None:
        prefix = "copy_auth_code:"
        if not link.startswith(prefix):
            return
        code = link[len(prefix):].strip()
        if not code or code == "—":
            QMessageBox.information(self, "Код", "Код авторизации пока недоступен.")
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(code)
        QMessageBox.information(self, "Скопировано", f"Код авторизации скопирован: {code}")
