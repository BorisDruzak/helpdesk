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
from PySide6.QtWidgets import (
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


STATUS_LABELS = {
    "new": "Новый",
    "triaged": "Разобран",
    "in_progress": "В работе",
    "waiting_on_user": "Ждёт пользователя",
    "waiting_on_vendor": "Ждёт подрядчика",
    "resolved": "Решён",
    "closed": "Закрыт",
}

STATUS_COLORS = {
    "new": ("#1d4ed8", "#dbeafe"),
    "triaged": ("#7c3aed", "#ede9fe"),
    "in_progress": ("#0f766e", "#ccfbf1"),
    "waiting_on_user": ("#b45309", "#fef3c7"),
    "waiting_on_vendor": ("#92400e", "#fde68a"),
    "resolved": ("#065f46", "#064e3b"),
    "closed": ("#475569", "#e2e8f0"),
    "unknown": ("#475569", "#e2e8f0"),
}

PINNED_STUB_META_KEY = "agent_stub_reply_to_message"

OUTGOING_MESSAGE_ROLES = {"user", "agent", "requester"}
SUPPORT_MESSAGE_ROLES = {"support", "admin"}


def ticket_status_label(status: Optional[str]) -> str:
    normalized = str(status or "unknown").strip().lower()
    return STATUS_LABELS.get(normalized, normalized or "unknown")


def ticket_status_colors(status: Optional[str]) -> tuple[str, str]:
    normalized = str(status or "unknown").strip().lower()
    return STATUS_COLORS.get(normalized, STATUS_COLORS["unknown"])


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
                "#dbeafe",
                "#93c5fd",
                "#1e3a8a",
                "#53708c",
            ),
            "support": (
                "#dcfce7",
                "#86efac",
                "#14532d",
                "#53708c",
            ),
            "event": (
                "#f8fafc",
                "#dbe2ea",
                "#475569",
                "#7b91a8",
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
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(4)

        if sender:
            sender_label = QLabel(sender)
            sender_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            sender_label.setStyleSheet(f"font-size: 11px; color: {muted}; font-weight: 600; border: none; background: transparent;")
            layout.addWidget(sender_label)

        reply_info = self._panel._resolve_reply_reference(reply_to)
        if reply_info:
            reply_author = QLabel(reply_info.get("sender_display_name") or "Ответ")
            reply_author.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            reply_author.setStyleSheet("font-size: 10px; font-weight: 700; color: #2563eb; border: none; background: transparent;")
            reply_preview = QLabel(reply_info.get("preview") or "")
            reply_preview.setWordWrap(True)
            reply_preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            reply_preview.setStyleSheet("font-size: 11px; color: #475569; border: none; background: transparent;")
            reply_wrap = QFrame()
            reply_wrap.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            reply_wrap.setStyleSheet(
                "background: rgba(255,255,255,0.55); border: 1px solid rgba(37, 99, 235, 0.18); border-radius: 10px;"
            )
            reply_layout = QVBoxLayout(reply_wrap)
            reply_layout.setContentsMargins(8, 6, 8, 6)
            reply_layout.setSpacing(2)
            reply_layout.addWidget(reply_author)
            reply_layout.addWidget(reply_preview)
            layout.addWidget(reply_wrap)

        text_label = QLabel(text or "Вложение")
        text_label.setWordWrap(True)
        text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text_label.setStyleSheet(f"font-size: 13px; color: {fg}; border: none; background: transparent;")
        layout.addWidget(text_label)

        for attachment in attachments or []:
            chip = QLabel(attachment)
            chip.setWordWrap(True)
            chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            chip.setStyleSheet(
                f"font-size: 12px; color: {fg}; "
                "padding: 4px 8px; border-radius: 10px; border: none; "
                "background: rgba(255,255,255,0.45);"
            )
            layout.addWidget(chip)

        if ts_text:
            time_label = QLabel(ts_text)
            time_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            time_label.setStyleSheet(f"font-size: 11px; color: {muted}; border: none; background: transparent;")
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


class TicketListItemWidget(QFrame):
    """Compact ticket card with status tint and unread badges."""

    def __init__(self, ticket: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._ticket = ticket
        self._selected = False
        status = ticket.get("status") or "unknown"
        self._status_fg, self._status_bg = ticket_status_colors(status)

        self.setObjectName("TicketListCard")
        self.setStyleSheet("QFrame#TicketListCard { border-radius: 16px; }")

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(4)

        code = ticket.get("ticket_code") or str(ticket.get("ticket_id") or "")[:8]
        priority = ticket.get("priority_class") or ticket.get("priority") or "—"
        requester = ticket.get("requester_display_name") or "Пользователь"
        title = ticket.get("title") or "Без названия"
        updated_at = ticket.get("updated_at") or ticket.get("created_at") or ""

        top_label = QLabel(f"#{code}  •  {ticket_status_label(status)}  •  {priority}")
        top_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #0f172a; background: transparent; border: none;")
        top_label.setWordWrap(True)
        left.addWidget(top_label)

        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #0f172a; background: transparent; border: none;")
        left.addWidget(title_label)

        meta_label = QLabel(f"{requester} • {ChatPanel._format_ts_static(updated_at) or '—'}")
        meta_label.setWordWrap(True)
        meta_label.setStyleSheet("font-size: 11px; color: #475569; background: transparent; border: none;")
        left.addWidget(meta_label)

        root.addLayout(left, 1)

        counters = ticket.get("chat_counters") or {}
        badges_col = QVBoxLayout()
        badges_col.setSpacing(6)
        badges_col.setContentsMargins(0, 2, 0, 2)
        unread_messages = int(counters.get("requester_unread_messages") or 0)
        unread_tools = int(counters.get("requester_unread_tool_calls") or 0)
        if unread_messages > 0:
            badges_col.addWidget(self._badge(str(unread_messages), "#dc2626"))
        if unread_tools > 0:
            badges_col.addWidget(self._badge(str(unread_tools), "#2563eb"))
        if badges_col.count() == 0:
            spacer = QLabel("")
            spacer.setFixedWidth(8)
            badges_col.addWidget(spacer)
        root.addLayout(badges_col)

        self._apply_style()

    @staticmethod
    def _badge(text: str, bg: str) -> QLabel:
        badge = QLabel(text)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setMinimumSize(24, 24)
        badge.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: white; background: {bg}; border-radius: 12px; padding: 0 7px;"
        )
        return badge

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._apply_style()

    def _apply_style(self) -> None:
        border = "#3390ec" if self._selected else self._status_fg
        bg = self._status_bg if not self._selected else "#dff0ff"
        self.setStyleSheet(
            f"""
            QFrame#TicketListCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 16px;
            }}
            """
        )


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
        buttons.addWidget(self.create_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

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


class ChatPanel(QWidget):
    """Ticket UI used by the desktop agent."""

    chatSessionChanged = Signal(str)

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
        self._ticket_item_widgets: Dict[str, TicketListItemWidget] = {}
        self._last_marked_read_event_id: Dict[str, int] = {}

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
        self.setStyleSheet(
            """
            QWidget { font-size: 13px; color: #182533; background: #f4f8fb; }
            QGroupBox { font-weight: 700; border: 1px solid #d6e5f3; border-radius: 20px; margin-top: 10px; background: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 2px 6px; }
            QListWidget { border: none; background: transparent; outline: none; padding: 2px; }
            QListWidget::item { border: 1px solid #dce9f5; border-radius: 18px; padding: 14px 16px; margin: 6px 4px; background: #ffffff; min-height: 34px; }
            QListWidget::item:hover { background: #f0f7ff; border-color: #8cc8ff; }
            QListWidget::item:selected { background: #dff0ff; border-color: #3390ec; color: #102030; }
            QPushButton { border: 1px solid #d6e5f3; border-radius: 15px; background: #ffffff; padding: 8px 14px; }
            QPushButton:hover { background: #f0f7ff; }
            QToolButton { border: 1px solid #d6e5f3; border-radius: 15px; background: #ffffff; padding: 8px 12px; font-size: 16px; }
            QToolButton:hover { background: #f0f7ff; }
            QPushButton#PrimaryButton { background: #3390ec; color: white; border-color: #3390ec; font-weight: 700; }
            QPushButton#PrimaryButton:hover { background: #2586e6; }
            QPushButton#DangerButton { background: #fef2f2; color: #b42318; border-color: #fca5a5; font-weight: 700; }
            QPushButton#DangerButton:hover { background: #fee2e2; }
            QPushButton#DangerButton:disabled { background: #f8fafc; color: #94a3b8; border-color: #e2e8f0; }
            QLineEdit, QTextEdit, QComboBox { border: 1px solid #d6e5f3; border-radius: 16px; background: #ffffff; padding: 8px 10px; selection-background-color: #3390ec; }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        self.stacked = QStackedWidget()
        self._setup_list_screen()
        self._setup_chat_screen()
        self.stacked.addWidget(self.list_screen)
        self.stacked.addWidget(self.chat_screen)
        self.stacked.setCurrentWidget(self.list_screen)
        root_layout.addWidget(self.stacked)

        self._refresh_profile_selector()

    def _setup_list_screen(self) -> None:
        self.list_screen = QWidget()
        layout = QVBoxLayout(self.list_screen)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.profile_summary = QLabel("")
        self.profile_summary.setWordWrap(True)
        self.profile_summary.setStyleSheet(
            "padding: 8px 10px; color: #2b3c4d; background: #ffffff; border: 1px solid #d6e5f3; border-radius: 12px;"
        )
        layout.addWidget(self.profile_summary)

        actions_row = QHBoxLayout()
        self.create_ticket_btn = QPushButton("Создать тикет")
        self.create_ticket_btn.setObjectName("PrimaryButton")
        self.create_ticket_btn.clicked.connect(self._on_create_ticket)
        self.manage_profiles_btn = QPushButton("Профили")
        self.manage_profiles_btn.clicked.connect(self.open_profile_manager)
        self.ticket_search_input = QLineEdit()
        self.ticket_search_input.setPlaceholderText("Поиск по коду, названию, статусу")
        self.ticket_search_input.textChanged.connect(self._on_ticket_search_changed)
        self.filter_open_checkbox = QCheckBox("Открытые")
        self.filter_open_checkbox.setChecked(True)
        self.filter_open_checkbox.toggled.connect(self._on_ticket_filter_changed)
        self.filter_closed_checkbox = QCheckBox("Закрытые")
        self.filter_closed_checkbox.setChecked(False)
        self.filter_closed_checkbox.toggled.connect(self._on_ticket_filter_changed)
        self.auto_refresh_label = QLabel("Автообновление каждые 3 секунды")
        self.auto_refresh_label.setStyleSheet("color: #64748b; padding-left: 6px;")
        actions_row.addWidget(self.create_ticket_btn)
        actions_row.addWidget(self.manage_profiles_btn)
        actions_row.addWidget(self.ticket_search_input, 1)
        actions_row.addWidget(self.filter_open_checkbox)
        actions_row.addWidget(self.filter_closed_checkbox)
        actions_row.addWidget(self.auto_refresh_label)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)

        tickets_group = QGroupBox("Список тикетов (только тикеты этого агента)")
        tickets_layout = QVBoxLayout(tickets_group)

        self.tickets_list = QListWidget()
        self.tickets_list.itemDoubleClicked.connect(lambda *_: self._on_open_ticket())
        self.tickets_list.itemSelectionChanged.connect(self._refresh_ticket_list_selection_styles)
        tickets_layout.addWidget(self.tickets_list)

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
        main_layout = QHBoxLayout(self.chat_screen)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        left_panel = QFrame()
        left_panel.setFrameShape(QFrame.Shape.StyledPanel)
        left_panel.setStyleSheet("background: #ffffff; border: 1px solid #d6e5f3; border-radius: 16px;")
        left_panel.setFixedWidth(280)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)

        self.back_to_list_btn = QPushButton("← К списку тикетов")
        self.back_to_list_btn.clicked.connect(self._show_list_screen)
        left_layout.addWidget(self.back_to_list_btn)

        self.ticket_info_label = QLabel("Тикет не выбран")
        self.ticket_info_label.setWordWrap(True)
        self.ticket_info_label.setTextFormat(Qt.TextFormat.RichText)
        self.ticket_info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.ticket_info_label.linkActivated.connect(self._on_ticket_code_clicked)
        self.ticket_info_label.setStyleSheet("font-weight: 700; padding: 12px 14px; border-radius: 18px; background: #e8f3ff; color: #16456b;")
        left_layout.addWidget(self.ticket_info_label)

        self.ticket_meta_label = QLabel("Откройте тикет в списке.")
        self.ticket_meta_label.setWordWrap(True)
        self.ticket_meta_label.setTextFormat(Qt.TextFormat.RichText)
        self.ticket_meta_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.ticket_meta_label.setStyleSheet(
            "padding: 10px 12px; color: #334155; background: #f9fcff; border: 1px solid #d6e5f3; border-radius: 16px; font-size: 12px;"
        )
        left_layout.addWidget(self.ticket_meta_label, 1)
        left_layout.addStretch(1)
        main_layout.addWidget(left_panel)

        right_center = QWidget()
        center_layout = QVBoxLayout(right_center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)

        self.ticket_status_top = QLabel("Статус: —")
        self.ticket_status_top.setStyleSheet(
            "font-weight: 700; padding: 10px 14px; border-radius: 14px; background: #e8f3ff; color: #16456b;"
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
            "padding: 10px 12px; border: 1px solid #b9dbfb; border-radius: 12px; background: #e8f3ff; color: #1b5f93;"
        )
        center_layout.addWidget(self.top_pinned_info)

        self.pinned_messages_widget = QWidget()
        pinned_row = QHBoxLayout(self.pinned_messages_widget)
        pinned_row.setContentsMargins(8, 8, 8, 8)
        pinned_row.setSpacing(8)
        self.pinned_messages_label = QLabel("")
        self.pinned_messages_label.setWordWrap(True)
        self.pinned_messages_label.setStyleSheet(
            "color: #1e3a8a;"
        )
        self.pinned_clear_btn = QPushButton("✕")
        self.pinned_clear_btn.setFixedSize(28, 28)
        self.pinned_clear_btn.clicked.connect(self._clear_pinned_messages_for_active_ticket)
        pinned_row.addWidget(self.pinned_messages_label, 1)
        pinned_row.addWidget(self.pinned_clear_btn)
        self.pinned_messages_widget.setStyleSheet(
            "border: 1px dashed #9dcdf7; border-radius: 12px; background: #f3f9ff;"
        )
        self.pinned_messages_widget.hide()
        center_layout.addWidget(self.pinned_messages_widget)

        self.reply_stub_label = QLabel("")
        self.reply_stub_label.setWordWrap(True)
        self.reply_stub_label.setStyleSheet(
            "padding: 6px 10px; border-radius: 10px; background: #fff8e8; color: #8b5a11; border: 1px solid #f5cf71;"
        )
        self.reply_stub_label.hide()
        center_layout.addWidget(self.reply_stub_label)

        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.timeline_scroll.setStyleSheet(
            """
            QScrollArea { background: #edf6ff; border: 1px solid #d6e5f3; border-radius: 22px; }
            QScrollBar:vertical {
                background: transparent;
                width: 0px;
                margin: 8px 4px 8px 4px;
                border-radius: 8px;
            }
            QScrollBar::handle:vertical {
                background: rgba(30, 64, 175, 120);
                min-height: 40px;
                border-radius: 8px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar:vertical:hover, QScrollBar:vertical:pressed { width: 10px; background: rgba(148, 163, 184, 70); }
            """
        )
        self.timeline_container = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_container)
        self.timeline_layout.setContentsMargins(14, 14, 14, 14)
        self.timeline_layout.setSpacing(10)
        self.timeline_scroll.setWidget(self.timeline_container)
        center_layout.addWidget(self.timeline_scroll, 1)

        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Сообщение в тикет")
        self.input_line.returnPressed.connect(self._on_send)
        center_layout.addWidget(self.input_line)

        self.resolution_message_widget = QWidget()
        resolution_layout = QHBoxLayout(self.resolution_message_widget)
        resolution_layout.setContentsMargins(10, 8, 10, 8)
        self.resolution_message_widget.setStyleSheet(
            "background: #fff7ed; border: 1px solid #fdba74; border-radius: 12px;"
        )
        self.resolution_prompt_label = QLabel(
            "Поддержка перевела тикет в статус 'Решён'. Подтвердить закрытие?"
        )
        self.resolution_confirm_btn = QPushButton("Подтвердить")
        self.resolution_confirm_btn.clicked.connect(lambda: self._spawn_task(self._async_close_ticket()))
        self.resolution_reject_btn = QPushButton("Отклонить")
        self.resolution_reject_btn.clicked.connect(self._on_reject_resolution)
        resolution_layout.addWidget(self.resolution_prompt_label, 1)
        resolution_layout.addWidget(self.resolution_confirm_btn)
        resolution_layout.addWidget(self.resolution_reject_btn)
        self.resolution_message_widget.hide()
        center_layout.addWidget(self.resolution_message_widget)

        actions = QHBoxLayout()
        self.send_btn = QPushButton("Отправить")
        self.send_btn.setObjectName("PrimaryButton")
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

    def _profiles(self) -> List[dict]:
        profiles = self._profiles_data.get("profiles")
        return profiles if isinstance(profiles, list) else []

    def _refresh_profile_selector(self) -> None:
        if not hasattr(self, "profile_summary"):
            return
        self.profile_summary.setText(f"Активный профиль: {self.current_requester_profile_summary()}")

    def _on_ticket_search_changed(self, text: str) -> None:
        self._ticket_search_query = text or ""
        self._update_tickets_list_ui()

    def _on_ticket_filter_changed(self) -> None:
        self._show_open_tickets = bool(self.filter_open_checkbox.isChecked())
        self._show_closed_tickets = bool(self.filter_closed_checkbox.isChecked())
        if not self._show_open_tickets and not self._show_closed_tickets:
            self._show_open_tickets = True
            self.filter_open_checkbox.blockSignals(True)
            self.filter_open_checkbox.setChecked(True)
            self.filter_open_checkbox.blockSignals(False)
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

    def open_profile_manager(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Профили инициатора")
        dialog.setMinimumWidth(540)
        layout = QVBoxLayout(dialog)

        profiles_list = QListWidget()
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

        def refresh_profiles(selected_id: Optional[str] = None) -> None:
            profiles_list.clear()
            for profile in self._profiles():
                title = profile.get("display_name") or profile.get("full_name") or "Без имени"
                item = QListWidgetItem(title)
                item.setData(Qt.ItemDataRole.UserRole, profile.get("id"))
                profiles_list.addItem(item)
                if selected_id and profile.get("id") == selected_id:
                    profiles_list.setCurrentItem(item)
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
        buttons.addWidget(btn_new)
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_delete)
        buttons.addWidget(btn_select)
        layout.addLayout(buttons)

        def current_profile_id() -> Optional[str]:
            item = profiles_list.currentItem()
            return item.data(Qt.ItemDataRole.UserRole) if item else None

        def save_profile(force_new: bool = False) -> None:
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

        btn_new.clicked.connect(lambda: save_profile(True))
        btn_save.clicked.connect(lambda: save_profile(False))
        btn_delete.clicked.connect(delete_profile)
        btn_select.clicked.connect(select_active)

        refresh_profiles(self._profiles_data.get("active_profile_id"))
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
        try:
            result = await self.ticket_client.list_tickets()
            if result.get("status") != "ok":
                return
            self.tickets_cache = result.get("tickets", [])
            self._update_tickets_list_ui()
        except Exception as exc:
            if not self._is_closing:
                logger.error(f"Ошибка загрузки списка тикетов: {exc}")

    def _update_tickets_list_ui(self) -> None:
        current_item = self.tickets_list.currentItem()
        current_id = self.active_ticket_id or (
            current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        )
        scroll_bar = self.tickets_list.verticalScrollBar()
        scroll_value = scroll_bar.value()
        self.tickets_list.clear()
        self._ticket_item_widgets = {}
        filtered_tickets: List[dict] = []
        for row in self.tickets_cache:
            ticket = row.get("ticket", row)
            status = str(ticket.get("status") or "").strip().lower()
            is_closed = status == "closed"
            if is_closed and not self._show_closed_tickets:
                continue
            if (not is_closed) and not self._show_open_tickets:
                continue
            if ticket_matches_query(ticket, self._ticket_search_query):
                filtered_tickets.append(ticket)

        if not filtered_tickets:
            empty_item = QListWidgetItem("Ничего не найдено")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.tickets_list.addItem(empty_item)
            QTimer.singleShot(0, lambda: scroll_bar.setValue(0))
            return

        for ticket in filtered_tickets:
            status = ticket.get("status") or "unknown"
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, ticket.get("ticket_id"))
            item.setToolTip(
                "\n".join(
                    [
                        f"Статус: {ticket_status_label(status)}",
                        f"Приоритет: {ticket.get('priority_class') or ticket.get('priority') or '—'}",
                        f"Очередь: {ticket.get('queue_code') or ticket.get('queue_id') or '—'}",
                        f"Исполнитель: {ticket.get('assignee_id') or 'Не назначен'}",
                    ]
                )
            )
            self.tickets_list.addItem(item)
            widget = TicketListItemWidget(ticket, self.tickets_list)
            item.setSizeHint(widget.sizeHint())
            self.tickets_list.setItemWidget(item, widget)
            self._ticket_item_widgets[str(ticket.get("ticket_id") or "")] = widget
            if current_id and ticket.get("ticket_id") == current_id:
                self.tickets_list.setCurrentItem(item)
        self._refresh_ticket_list_selection_styles()
        QTimer.singleShot(0, lambda: scroll_bar.setValue(min(scroll_value, scroll_bar.maximum())))

    def _refresh_ticket_list_selection_styles(self) -> None:
        for index in range(self.tickets_list.count()):
            item = self.tickets_list.item(index)
            if item is None:
                continue
            ticket_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
            widget = self._ticket_item_widgets.get(ticket_id)
            if widget is not None:
                widget.set_selected(bool(item.isSelected()))

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
        try:
            result = await self.ticket_client.get_ticket(self.active_ticket_id)
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

    def _update_ticket_detail_ui(self, ticket: dict, messages: List[dict], events: List[dict]) -> None:
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
        self.ticket_info_label.setText(f"Тикет <a href='copy_ticket_code:{safe_code}'>#{safe_code}</a><br>{safe_title}")
        self.ticket_status_top.setText(f"Статус тикета: {ticket_status_label(status)}{status_suffix}")
        self.ticket_status_top.setStyleSheet(
            f"font-weight: 700; padding: 10px 14px; border-radius: 14px; background: {status_bg}; color: {status_fg};"
        )
        self.ticket_meta_label.setText(self._build_ticket_meta_html(ticket))
        self._refresh_top_pinned_info(ticket, messages)
        self._refresh_pinned_messages_label(ticket.get("ticket_id") or "")
        self._apply_ticket_background(status)
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

        items: List[tuple[float, str, str]] = []

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

        self._maybe_prompt_resolution_confirmation(ticket)

        if self._bubble_menu_open:
            self._pending_ticket_snapshot = (dict(ticket), list(messages), list(events))
            return

        signature = self._build_timeline_signature(ticket, messages, events)
        if signature == self._last_timeline_html:
            self._pending_ticket_snapshot = None
            return

        scroll_bar = self.timeline_scroll.verticalScrollBar()
        previous_value = scroll_bar.value()
        previous_max = scroll_bar.maximum()
        stick_to_bottom = previous_max == 0 or previous_value >= max(previous_max - 24, 0)
        self._render_timeline_widgets(items)
        self._last_timeline_html = signature
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
            f"<div style='margin-bottom:6px;'><span style='color:#64748b;'>{self._escape_html(label)}:</span> "
            f"<span style='color:#0f172a;'>{self._escape_html(str(value))}</span></div>"
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
            "chat_counters": ticket.get("chat_counters") or {},
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
            raw = self._normalize_iso_ts(value)
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
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value)).strftime("%d.%m.%Y %H:%M:%S")
        if isinstance(value, str):
            raw = self._normalize_iso_ts(value)
            if not raw:
                return ""
            try:
                dt = datetime.fromisoformat(raw)
                if dt.tzinfo is not None:
                    dt = dt.astimezone()
                return dt.strftime("%d.%m.%Y %H:%M:%S")
            except ValueError:
                return raw
        return str(value)

    @staticmethod
    def _format_ts_static(value) -> str:
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value)).strftime("%d.%m.%Y %H:%M:%S")
        if isinstance(value, str):
            raw = ChatPanel._normalize_iso_ts(value)
            if not raw:
                return ""
            try:
                dt = datetime.fromisoformat(raw)
                if dt.tzinfo is not None:
                    dt = dt.astimezone()
                return dt.strftime("%d.%m.%Y %H:%M:%S")
            except ValueError:
                return raw
        return str(value)

    @staticmethod
    def _normalize_iso_ts(value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return ""
        normalized = raw.replace("Z", "+00:00")
        if "." in normalized:
            dot_idx = normalized.find(".")
            tz_idx = len(normalized)
            plus_idx = normalized.find("+", dot_idx)
            minus_idx = normalized.find("-", dot_idx)
            if plus_idx != -1:
                tz_idx = min(tz_idx, plus_idx)
            if minus_idx != -1:
                tz_idx = min(tz_idx, minus_idx)
            frac = normalized[dot_idx + 1:tz_idx]
            if frac.isdigit() and len(frac) > 6:
                normalized = f"{normalized[:dot_idx + 1]}{frac[:6]}{normalized[tz_idx:]}"
        return normalized

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
            self.open_profile_manager()
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
        item = self.tickets_list.currentItem()
        if not item:
            return
        self.active_ticket_id = item.data(Qt.ItemDataRole.UserRole)
        self._last_timeline_html = None
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

    def _show_chat_screen(self) -> None:
        self.stacked.setCurrentWidget(self.chat_screen)
        self.input_line.setFocus()

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
        bg = "rgba(219, 234, 254, 0.25)"
        if normalized == "resolved":
            bg = "rgba(6, 78, 59, 0.18)"
        elif normalized == "closed":
            bg = "rgba(71, 85, 105, 0.14)"
        self.chat_screen.setStyleSheet(
            f"background: {bg}; border-radius: 10px;"
        )

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
