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
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from loguru import logger

from pc_agent.core.runtime_paths import resolve_data_root

from .server_api import ServerApiClient, TicketApiClient


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
                selected = self.profile_selector.currentData()
                if selected:
                    self.panel._profiles_data["active_profile_id"] = selected
                    self.panel._save_profiles()

        self.profile_selector.blockSignals(False)
        self.profile_summary.setText(self.panel.current_requester_profile_summary())

    def _on_profile_changed(self, *_args) -> None:
        profile_id = self.profile_selector.currentData()
        if not profile_id:
            return
        self.panel._profiles_data["active_profile_id"] = profile_id
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
                    base_url = "http://localhost:8666/api"
            self.client = ServerApiClient(base_url, device_id, actor_role)

        if base_url is None:
            try:
                from pc_agent.config.config_loader import get_config

                base_url = get_config().server.api_url
            except Exception:
                base_url = "http://localhost:8666/api"

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
            QWidget { font-size: 13px; }
            QGroupBox { font-weight: 700; border: 1px solid #dbe2ea; border-radius: 10px; margin-top: 8px; background: #f8fafc; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 2px 6px; }
            QListWidget { border: 1px solid #d6dee7; border-radius: 10px; background: #ffffff; }
            QPushButton { border: 1px solid #c8d3e0; border-radius: 8px; background: #eef3f8; padding: 6px 10px; }
            QPushButton:hover { background: #dde8f7; }
            QLineEdit, QTextEdit, QComboBox { border: 1px solid #cfd9e5; border-radius: 8px; background: #ffffff; padding: 6px; }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs)

        self._setup_tickets_tab()
        self._setup_ticket_chat_tab()
        self.tabs.setCurrentWidget(self.tickets_tab)

        self._refresh_profile_selector()

    def _setup_tickets_tab(self) -> None:
        self.tickets_tab = QWidget()
        layout = QVBoxLayout(self.tickets_tab)
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
        self.create_ticket_btn.clicked.connect(self._on_create_ticket)
        self.manage_profiles_btn = QPushButton("Профили")
        self.manage_profiles_btn.clicked.connect(self.open_profile_manager)
        self.refresh_list_btn = QPushButton("Обновить")
        self.refresh_list_btn.clicked.connect(self._refresh_ticket_list_async)
        actions_row.addWidget(self.create_ticket_btn)
        actions_row.addWidget(self.manage_profiles_btn)
        actions_row.addWidget(self.refresh_list_btn)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)

        tickets_group = QGroupBox("Список тикетов")
        tickets_layout = QVBoxLayout(tickets_group)

        self.tickets_list = QListWidget()
        self.tickets_list.itemClicked.connect(lambda *_: self._on_open_ticket())
        self.tickets_list.itemDoubleClicked.connect(lambda *_: self._on_open_ticket())
        tickets_layout.addWidget(self.tickets_list)

        open_row = QHBoxLayout()
        self.open_ticket_btn = QPushButton("Открыть тикет")
        self.open_ticket_btn.clicked.connect(self._on_open_ticket)
        open_row.addStretch(1)
        open_row.addWidget(self.open_ticket_btn)
        tickets_layout.addLayout(open_row)

        layout.addWidget(tickets_group, 1)
        self.tabs.addTab(self.tickets_tab, "Тикеты")

    def _setup_ticket_chat_tab(self) -> None:
        self.ticket_chat_tab = QWidget()
        layout = QVBoxLayout(self.ticket_chat_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.ticket_info_label = QLabel("Тикет не выбран")
        self.ticket_info_label.setStyleSheet("font-weight: 700; padding: 8px; border-radius: 8px; background: #dbeafe;")
        layout.addWidget(self.ticket_info_label)

        self.ticket_meta_label = QLabel("Откройте тикет в первой вкладке.")
        self.ticket_meta_label.setWordWrap(True)
        self.ticket_meta_label.setStyleSheet(
            "padding: 6px 8px; color: #334155; background: #f8fafc; border: 1px solid #dbe2ea; border-radius: 8px;"
        )
        layout.addWidget(self.ticket_meta_label)

        self.timeline_view = QTextEdit()
        self.timeline_view.setReadOnly(True)
        self.timeline_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.timeline_view.setPlaceholderText("Здесь будут сообщения и события тикета")
        self.timeline_view.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        layout.addWidget(self.timeline_view, 1)

        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Сообщение в тикет")
        self.input_line.returnPressed.connect(self._on_send)
        layout.addWidget(self.input_line)

        actions = QHBoxLayout()
        self.send_btn = QPushButton("Отправить")
        self.send_btn.clicked.connect(self._on_send)
        self.attach_file_btn = QPushButton("Файл")
        self.attach_file_btn.clicked.connect(self._on_attach_files)
        self.screenshot_btn = QPushButton("Скриншот")
        self.screenshot_btn.clicked.connect(self._on_send_screenshot)
        self.video_btn = QPushButton("Видео до 60с")
        self.video_btn.clicked.connect(self._on_send_video)
        self.close_ticket_btn = QPushButton("Закрыть тикет")
        self.close_ticket_btn.clicked.connect(self._on_close_ticket)
        self.tool_status_label = QLabel("")
        actions.addWidget(self.send_btn)
        actions.addWidget(self.attach_file_btn)
        actions.addWidget(self.screenshot_btn)
        actions.addWidget(self.video_btn)
        actions.addWidget(self.close_ticket_btn)
        actions.addWidget(self.tool_status_label, 1)
        layout.addLayout(actions)

        self.tabs.addTab(self.ticket_chat_tab, "Тикет")

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

    def _active_profile(self) -> Optional[dict]:
        active_id = self._profiles_data.get("active_profile_id")
        for profile in self._profiles():
            if profile.get("id") == active_id:
                return profile
        return self._profiles()[0] if self._profiles() else None

    def current_requester_profile_summary(self) -> str:
        profile = self._active_profile()
        if not profile:
            return "Профиль не выбран"
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

    def _refresh_ticket_list_async(self) -> None:
        asyncio.create_task(self._async_refresh_ticket_list())

    def _refresh_ticket_detail_async(self) -> None:
        if self.active_ticket_id:
            asyncio.create_task(self._async_refresh_ticket_detail())

    async def _async_refresh_ticket_list(self) -> None:
        try:
            result = await self.ticket_client.list_tickets()
            if result.get("status") != "ok":
                return
            self.tickets_cache = result.get("tickets", [])
            self._update_tickets_list_ui()
        except Exception as exc:
            logger.error(f"Ошибка загрузки списка тикетов: {exc}")

    def _update_tickets_list_ui(self) -> None:
        current_id = self.active_ticket_id
        self.tickets_list.clear()
        for row in self.tickets_cache:
            ticket = row.get("ticket", row)
            title = ticket.get("title") or "Без названия"
            status = ticket.get("status") or "unknown"
            code = ticket.get("ticket_code") or ticket.get("ticket_id", "")[:8]
            priority = ticket.get("priority_class") or ticket.get("priority") or "—"
            item = QListWidgetItem(f"#{code} • {status} • {priority}\n{title}")
            item.setData(Qt.ItemDataRole.UserRole, ticket.get("ticket_id"))
            self.tickets_list.addItem(item)
            if current_id and ticket.get("ticket_id") == current_id:
                self.tickets_list.setCurrentItem(item)

    async def _async_refresh_ticket_detail(self) -> None:
        if not self.active_ticket_id:
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
            logger.error(f"Ошибка загрузки тикета {self.active_ticket_id}: {exc}")

    def _update_ticket_detail_ui(self, ticket: dict, messages: List[dict], events: List[dict]) -> None:
        code = ticket.get("ticket_code") or ticket.get("ticket_id", "")
        self.ticket_info_label.setText(f"Тикет #{code} | Статус: {ticket.get('status', 'unknown')}")
        self.ticket_meta_label.setText(
            "Приоритет: {priority}\nОчередь: {queue}\nИсполнитель: {assignee}\nОписание: {description}".format(
                priority=ticket.get("priority_class") or ticket.get("priority") or "—",
                queue=ticket.get("queue_code") or ticket.get("queue_id") or "—",
                assignee=ticket.get("assignee_id") or "Не назначен",
                description=ticket.get("description") or "—",
            )
        )

        timeline_lines: List[tuple[float, str]] = []

        for message in messages:
            ts = message.get("ts")
            role = message.get("from_role") or "user"
            text = message.get("text") or ""
            attachment_refs = message.get("attachment_refs") or []
            suffix = ""
            if attachment_refs:
                refs_text = ", ".join(str(ref) for ref in attachment_refs)
                suffix = f" | вложения: {refs_text}"
            line = f"[{self._format_ts(ts)}] {role}: {text}{suffix}"
            timeline_lines.append((self._ts_sort_value(ts), line))

        merged_events = list(events) + self.local_action_buffer.get(self.active_ticket_id, [])
        for event in merged_events:
            ts = event.get("ts")
            line = f"[{self._format_ts(ts)}] EVENT: {self._format_event_text(event)}"
            timeline_lines.append((self._ts_sort_value(ts), line))

        timeline_lines.sort(key=lambda item: item[0])
        if timeline_lines:
            self.timeline_view.setPlainText("\n\n".join(line for _, line in timeline_lines))
        else:
            self.timeline_view.setPlainText("Пока нет сообщений или событий")

        self.timeline_view.moveCursor(self.timeline_view.textCursor().MoveOperation.End)

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
            return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, str):
            return value
        return str(value)

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
        asyncio.create_task(self._async_create_ticket(payload))

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
        self._ticket_detail_timer.start(2500)
        self._refresh_ticket_detail_async()
        self._show_chat_screen()

    def _on_send(self) -> None:
        if not self.active_ticket_id:
            return
        text = self.input_line.text().strip()
        if not text:
            return
        asyncio.create_task(self._async_send_message(text))

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
        asyncio.create_task(self._async_attach_files(files))

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
        asyncio.create_task(self._async_run_tool("screen.collect", {}, "Запрос на скриншот отправлен"))

    def _on_send_video(self) -> None:
        if not self.active_ticket_id:
            QMessageBox.information(self, "Тикет", "Сначала откройте тикет.")
            return
        asyncio.create_task(
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
        asyncio.create_task(self._async_close_ticket())

    async def _async_close_ticket(self) -> None:
        try:
            await self.ticket_client.close_ticket(self.active_ticket_id)
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

    def _stop_ticket_detail_polling(self) -> None:
        if self._ticket_detail_timer.isActive():
            self._ticket_detail_timer.stop()

    def _show_chat_screen(self) -> None:
        self.tabs.setCurrentWidget(self.ticket_chat_tab)
        self.input_line.setFocus()
