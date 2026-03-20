"""Ticket chat panel for the agent GUI."""

from __future__ import annotations

import asyncio
import json
import socket
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
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
    QScrollArea,
    QStackedWidget,
    QTextEdit,
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
    "resolved": ("#047857", "#d1fae5"),
    "closed": ("#475569", "#e2e8f0"),
    "unknown": ("#475569", "#e2e8f0"),
}

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
        self.profile_selector.addItem("Без профиля", "__no_profile__")
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
        self.panel._profiles_data["active_profile_id"] = None if profile_id == "__no_profile__" else profile_id
        self.panel._save_profiles()
        self.profile_summary.setText(self.panel.current_requester_profile_summary())

    def _on_manage_profiles(self) -> None:
        self.panel.open_profile_manager()
        self._refresh_profiles()

    def _on_accept(self) -> None:
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
        self._last_timeline_html: Optional[str] = None
        self._pending_ticket_snapshot: Optional[tuple[dict, List[dict], List[dict]]] = None
        self._resolution_prompt_keys: set[str] = set()
        self._resolution_prompt_open_for: Optional[str] = None
        self._pending_tasks: set[asyncio.Task] = set()
        self._is_closing = False

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
            QWidget { font-size: 13px; color: #1f2937; }
            QGroupBox { font-weight: 700; border: 1px solid #d9e7f4; border-radius: 20px; margin-top: 10px; background: #f7fbff; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 2px 6px; }
            QListWidget { border: none; background: transparent; outline: none; padding: 2px; }
            QListWidget::item { border: 1px solid #d9e7f4; border-radius: 22px; padding: 14px 16px; margin: 6px 4px; background: #ffffff; min-height: 34px; }
            QListWidget::item:hover { background: #eef6ff; border-color: #93c5fd; }
            QListWidget::item:selected { background: #cfe7ff; border-color: #2563eb; color: #0f172a; }
            QPushButton { border: 1px solid #cfe0f1; border-radius: 15px; background: #f4f8fd; padding: 8px 14px; }
            QPushButton:hover { background: #e6f0fb; }
            QPushButton#PrimaryButton { background: #4f9cf9; color: white; border-color: #4f9cf9; font-weight: 700; }
            QPushButton#PrimaryButton:hover { background: #3b8bf0; }
            QPushButton#DangerButton { background: #fef2f2; color: #b42318; border-color: #fca5a5; font-weight: 700; }
            QPushButton#DangerButton:hover { background: #fee2e2; }
            QPushButton#DangerButton:disabled { background: #f8fafc; color: #94a3b8; border-color: #e2e8f0; }
            QLineEdit, QTextEdit, QComboBox { border: 1px solid #d4e2f1; border-radius: 16px; background: #ffffff; padding: 8px 10px; }
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
            "padding: 6px 8px; color: #334155; background: #f8fafc; border: 1px solid #dbe2ea; border-radius: 8px;"
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
        self.auto_refresh_label = QLabel("Автообновление каждые 3 секунды")
        self.auto_refresh_label.setStyleSheet("color: #64748b; padding-left: 6px;")
        actions_row.addWidget(self.create_ticket_btn)
        actions_row.addWidget(self.manage_profiles_btn)
        actions_row.addWidget(self.ticket_search_input, 1)
        actions_row.addWidget(self.auto_refresh_label)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)

        tickets_group = QGroupBox("Список тикетов (только тикеты этого агента)")
        tickets_layout = QVBoxLayout(tickets_group)

        self.tickets_list = QListWidget()
        self.tickets_list.itemDoubleClicked.connect(lambda *_: self._on_open_ticket())
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
        left_panel.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;")
        left_panel.setFixedWidth(280)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)

        self.back_to_list_btn = QPushButton("← К списку тикетов")
        self.back_to_list_btn.clicked.connect(self._show_list_screen)
        left_layout.addWidget(self.back_to_list_btn)

        self.ticket_info_label = QLabel("Тикет не выбран")
        self.ticket_info_label.setWordWrap(True)
        self.ticket_info_label.setStyleSheet("font-weight: 700; padding: 12px 14px; border-radius: 18px; background: #dbeafe;")
        left_layout.addWidget(self.ticket_info_label)

        self.ticket_status_label = QLabel("Статус: —")
        self.ticket_status_label.setStyleSheet(
            "font-weight: 700; padding: 8px 12px; border-radius: 999px; background: #e2e8f0; color: #475569;"
        )
        left_layout.addWidget(self.ticket_status_label)

        self.ticket_meta_label = QLabel("Откройте тикет в списке.")
        self.ticket_meta_label.setWordWrap(True)
        self.ticket_meta_label.setStyleSheet(
            "padding: 10px 12px; color: #334155; background: #fff; border: 1px solid #dbe2ea; border-radius: 16px; font-size: 12px;"
        )
        left_layout.addWidget(self.ticket_meta_label)
        left_layout.addStretch(1)
        self.close_ticket_btn = QPushButton("Подтвердить и закрыть")
        self.close_ticket_btn.setObjectName("DangerButton")
        self.close_ticket_btn.setEnabled(False)
        self.close_ticket_btn.clicked.connect(self._on_close_ticket)
        left_layout.addWidget(self.close_ticket_btn)
        main_layout.addWidget(left_panel)

        right_center = QWidget()
        center_layout = QVBoxLayout(right_center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)

        self.timeline_view = QTextEdit()
        self.timeline_view.setReadOnly(True)
        self.timeline_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.timeline_view.setPlaceholderText("Здесь будут сообщения и события тикета")
        self.timeline_view.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.timeline_view.setStyleSheet(
            "QTextEdit { background: #eaf4ff; border: 1px solid #d8e7f6; border-radius: 22px; padding: 14px; font-size: 13px; }"
        )
        center_layout.addWidget(self.timeline_view, 1)

        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Сообщение в тикет")
        self.input_line.returnPressed.connect(self._on_send)
        center_layout.addWidget(self.input_line)

        actions = QHBoxLayout()
        self.send_btn = QPushButton("Отправить")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.clicked.connect(self._on_send)
        self.attach_file_btn = QPushButton("Файл")
        self.attach_file_btn.clicked.connect(self._on_attach_files)
        self.media_btn = QPushButton("Скриншот / Видео")
        media_menu = QMenu(self.media_btn)
        media_menu.addAction("Сделать скриншот", self._on_send_screenshot)
        media_menu.addAction("Записать видео до 60 секунд", self._on_send_video)
        self.media_btn.setMenu(media_menu)
        self.tool_status_label = QLabel("")
        actions.addWidget(self.send_btn)
        actions.addWidget(self.attach_file_btn)
        actions.addWidget(self.media_btn)
        actions.addWidget(self.tool_status_label, 1)
        center_layout.addLayout(actions)

        main_layout.addWidget(right_center, 1)

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
        filtered_tickets: List[dict] = []
        for row in self.tickets_cache:
            ticket = row.get("ticket", row)
            if ticket_matches_query(ticket, self._ticket_search_query):
                filtered_tickets.append(ticket)

        if not filtered_tickets:
            empty_item = QListWidgetItem("Ничего не найдено")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.tickets_list.addItem(empty_item)
            QTimer.singleShot(0, lambda: scroll_bar.setValue(0))
            return

        for ticket in filtered_tickets:
            title = ticket.get("title") or "Без названия"
            status = ticket.get("status") or "unknown"
            code = ticket.get("ticket_code") or ticket.get("ticket_id", "")[:8]
            priority = ticket.get("priority_class") or ticket.get("priority") or "—"
            requester = ticket.get("requester_display_name") or "Пользователь"
            updated_at = self._format_ts(ticket.get("updated_at") or ticket.get("created_at"))
            item = QListWidgetItem(
                f"#{code} • {ticket_status_label(status)} • {priority}\n"
                f"{title}\n{requester} • {updated_at}"
            )
            item.setData(Qt.ItemDataRole.UserRole, ticket.get("ticket_id"))
            item.setToolTip(
                "\n".join(
                    [
                        f"Статус: {ticket_status_label(status)}",
                        f"Приоритет: {priority}",
                        f"Очередь: {ticket.get('queue_code') or ticket.get('queue_id') or '—'}",
                        f"Исполнитель: {ticket.get('assignee_id') or 'Не назначен'}",
                    ]
                )
            )
            self.tickets_list.addItem(item)
            if current_id and ticket.get("ticket_id") == current_id:
                self.tickets_list.setCurrentItem(item)
        QTimer.singleShot(0, lambda: scroll_bar.setValue(min(scroll_value, scroll_bar.maximum())))

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
        self.ticket_info_label.setText(f"Тикет #{code}\n{title}")
        self.ticket_status_label.setText(f"Статус: {ticket_status_label(status)}")
        self.ticket_status_label.setStyleSheet(
            f"font-weight: 700; padding: 8px 12px; border-radius: 999px; background: {status_bg}; color: {status_fg};"
        )
        self.ticket_meta_label.setText(self._build_ticket_meta_html(ticket))
        self.close_ticket_btn.setEnabled(can_user_confirm_close(ticket))
        requester_name = ticket.get("requester_display_name") or "Пользователь"
        assignee_name = ticket.get("assignee_id") or "Поддержка"

        items: List[tuple[float, str, str]] = []

        for message in messages:
            ts = message.get("ts")
            text = (message.get("text") or "").strip()
            sender_kind = message_visual_role(message)
            sender = requester_name if sender_kind == "self" else assignee_name if sender_kind == "support" else "Система"
            attachments_html = self._render_message_attachments(message)
            text_html = self._escape_html(text).replace("\n", "<br>")
            if sender_kind == "self":
                block = (
                    "<table width='100%' cellspacing='0' cellpadding='0' style='margin:10px 0;'>"
                    "<tr><td align='right'>"
                    "<div style='font-size:11px; color:#53708c; margin-bottom:4px;'>Вы</div>"
                    "<table cellspacing='0' cellpadding='0' style='margin-left:auto;'><tr>"
                    f"<td style='background:#d9fdd3; color:#153d2a; padding:10px 14px; border:1px solid #bee9b8; border-radius:16px;'>"
                    f"{text_html or 'Вложение'}{attachments_html}</td>"
                    "</tr></table>"
                    f"<div style='font-size:11px; color:#7b91a8; margin-top:4px;'>{self._format_ts(ts)}</div>"
                    "</td></tr></table>"
                )
            elif sender_kind == "support":
                block = (
                    "<table width='100%' cellspacing='0' cellpadding='0' style='margin:10px 0;'>"
                    "<tr><td align='left'>"
                    f"<div style='font-size:11px; color:#53708c; margin-bottom:4px;'>{self._escape_html(sender)}</div>"
                    "<table cellspacing='0' cellpadding='0'><tr>"
                    f"<td style='background:#ffffff; color:#1f2937; padding:10px 14px; border:1px solid #d5e3f1; border-radius:16px;'>"
                    f"{text_html or 'Вложение'}{attachments_html}</td>"
                    "</tr></table>"
                    f"<div style='font-size:11px; color:#7b91a8; margin-top:4px;'>{self._format_ts(ts)}</div>"
                    "</td></tr></table>"
                )
            else:
                block = (
                    "<table width='100%' cellspacing='0' cellpadding='0' style='margin:10px 0;'>"
                    "<tr><td align='center'>"
                    "<table cellspacing='0' cellpadding='0'><tr>"
                    f"<td style='background:#f8fafc; color:#475569; padding:8px 12px; border:1px solid #dbe2ea; border-radius:16px;'>"
                    f"{text_html or 'Событие'}{attachments_html}</td>"
                    "</tr></table>"
                    f"<div style='font-size:11px; color:#7b91a8; margin-top:4px;'>{self._format_ts(ts)}</div>"
                    "</td></tr></table>"
                )
            items.append((self._ts_sort_value(ts), "msg", block))

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
            block = (
                f'<div style="text-align:center; margin:10px 0;"><span style="background:#f8fafc; color:#475569; padding:6px 12px; border-radius:999px; '
                f'font-size:12px; border: 1px solid #dbe2ea;">'
                f'⚙ {self._escape_html(line)}</span><br><span style="font-size:11px; color:#999;">{self._format_ts(ts)}</span></div>'
            )
            items.append((self._ts_sort_value(ts), "event", block))

        items.sort(key=lambda x: x[0])
        if items:
            html = "<div style='font-family: Segoe UI;'>" + "<br>".join(block for _, _, block in items) + "</div>"
        else:
            html = "<p style='color:#64748b;'>Пока нет сообщений.</p>"

        self._maybe_prompt_resolution_confirmation(ticket)

        if self.timeline_view.textCursor().hasSelection():
            self._pending_ticket_snapshot = (dict(ticket), list(messages), list(events))
            return

        if html == self._last_timeline_html:
            self._pending_ticket_snapshot = None
            return

        scroll_bar = self.timeline_view.verticalScrollBar()
        previous_value = scroll_bar.value()
        previous_max = scroll_bar.maximum()
        stick_to_bottom = previous_max == 0 or previous_value >= max(previous_max - 24, 0)
        self.timeline_view.setHtml(html)
        self._last_timeline_html = html
        self._pending_ticket_snapshot = None

        def restore_scroll() -> None:
            if stick_to_bottom:
                scroll_bar.setValue(scroll_bar.maximum())
            else:
                scroll_bar.setValue(min(previous_value, scroll_bar.maximum()))

        QTimer.singleShot(0, restore_scroll)

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
            ("Описание", ticket.get("description") or "—"),
        ]
        return "".join(
            f"<div style='margin-bottom:6px;'><span style='color:#64748b;'>{self._escape_html(label)}:</span> "
            f"<span style='color:#0f172a;'>{self._escape_html(str(value))}</span></div>"
            for label, value in rows
        )

    def _render_message_attachments(self, message: dict) -> str:
        attachments = message.get("attachments") or []
        attachment_refs = message.get("attachment_refs") or []
        labels: List[str] = []
        for item in attachments[:5]:
            if not isinstance(item, dict):
                continue
            label = item.get("name") or item.get("artifact_id") or item.get("mime_type") or "Вложение"
            labels.append(str(label))
        if not labels and attachment_refs:
            labels = [str(ref) for ref in attachment_refs[:5]]
        if not labels:
            return ""
        return "".join(
            f"<div style='margin-top:6px; font-size:11px; color:#53708c;'>📎 {self._escape_html(label)}</div>"
            for label in labels
        )

    def _maybe_prompt_resolution_confirmation(self, ticket: dict) -> None:
        if not ticket or not can_user_confirm_close(ticket):
            return
        ticket_id = str(ticket.get("ticket_id") or "")
        prompt_key = f"{ticket_id}:{ticket.get('resolved_at') or ticket.get('updated_at') or 'resolved'}"
        if not ticket_id or prompt_key in self._resolution_prompt_keys or self._resolution_prompt_open_for == ticket_id:
            return
        self._resolution_prompt_keys.add(prompt_key)
        self._resolution_prompt_open_for = ticket_id

        box = QMessageBox(self)
        box.setWindowTitle("Подтвердить решение")
        box.setText(
            "Поддержка перевела тикет в статус 'Решён'.\n"
            "Если всё действительно исправлено, подтвердите закрытие."
        )
        box.setIcon(QMessageBox.Icon.Question)
        confirm_btn = box.addButton("Подтвердить и закрыть", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Позже", QMessageBox.ButtonRole.RejectRole)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        def on_finished(_result: int) -> None:
            self._resolution_prompt_open_for = None
            if box.clickedButton() == confirm_btn and self.active_ticket_id == ticket_id:
                self._spawn_task(self._async_close_ticket())

        box.finished.connect(on_finished)
        box.open()

    def _ts_sort_value(self, value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return 0.0
            try:
                return float(raw)
            except ValueError:
                pass
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return 0.0
        return 0.0

    def _format_ts(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value)).strftime("%d.%m.%Y %H:%M:%S")
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return ""
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if dt.tzinfo is not None:
                    dt = dt.astimezone()
                return dt.strftime("%d.%m.%Y %H:%M:%S")
            except ValueError:
                return raw
        return str(value)

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

        details: List[str] = []
        for key in ("tool_name", "action", "status", "message"):
            value = event.get(key)
            if not value:
                value = payload.get(key)
            if value:
                details.append(f"{key}={value}")

        if not details and payload:
            summary_keys = ["result", "error", "code", "description"]
            for key in summary_keys:
                value = payload.get(key)
                if value:
                    details.append(f"{key}={value}")
                    break

        if details:
            return f"{event_type} | " + " | ".join(details)
        return event_type

    def _on_create_ticket(self) -> None:
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
            await self.ticket_client.send_message(self.active_ticket_id, text, from_role="user")
            self.input_line.clear()
            await self._async_refresh_ticket_detail()
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
            await self.ticket_client.send_message(
                self.active_ticket_id,
                text,
                from_role="user",
                attachment_refs=refs,
            )
            self.input_line.clear()
            self.tool_status_label.setText(f"Отправлено вложений: {len(refs)}")
            await self._async_refresh_ticket_detail()
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

    def _on_close_ticket(self) -> None:
        if not self.active_ticket_id:
            return
        ticket = next(
            (
                row.get("ticket", row)
                for row in self.tickets_cache
                if (row.get("ticket", row) or {}).get("ticket_id") == self.active_ticket_id
            ),
            {},
        )
        if not can_user_confirm_close(ticket):
            QMessageBox.information(
                self,
                "Закрытие недоступно",
                "Подтвердить закрытие можно только когда тикет уже переведён в статус 'Решён'.",
            )
            return
        confirm = QMessageBox.question(
            self,
            "Подтвердить закрытие",
            "Закрыть тикет как подтверждённо решённый?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._spawn_task(self._async_close_ticket())

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
