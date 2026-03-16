"""Ticket chat panel for the agent GUI."""

from __future__ import annotations

import asyncio
import json
import socket
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from loguru import logger

from pc_agent.core.runtime_paths import resolve_data_root

from .server_api import ServerApiClient, TicketApiClient


class ChatPanel(QWidget):
    """Compact ticket UI used by the desktop agent."""

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
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        create_group = QGroupBox("Новая заявка")
        create_layout = QVBoxLayout(create_group)
        self.profile_summary = QLabel(self.current_requester_profile_summary())
        self.profile_summary.setWordWrap(True)
        create_layout.addWidget(self.profile_summary)
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Опишите проблему")
        self.description_input.setMaximumHeight(120)
        create_layout.addWidget(self.description_input)
        create_buttons = QHBoxLayout()
        self.create_ticket_btn = QPushButton("Создать")
        self.create_ticket_btn.clicked.connect(self._on_create_ticket)
        self.manage_profiles_btn = QPushButton("Профили")
        self.manage_profiles_btn.clicked.connect(self.open_profile_manager)
        create_buttons.addWidget(self.create_ticket_btn)
        create_buttons.addWidget(self.manage_profiles_btn)
        create_layout.addLayout(create_buttons)
        left_layout.addWidget(create_group)

        tickets_group = QGroupBox("Мои тикеты")
        tickets_layout = QVBoxLayout(tickets_group)
        self.tickets_list = QListWidget()
        self.tickets_list.itemDoubleClicked.connect(lambda *_: self._on_open_ticket())
        tickets_layout.addWidget(self.tickets_list)
        tickets_buttons = QHBoxLayout()
        self.refresh_list_btn = QPushButton("Обновить")
        self.refresh_list_btn.clicked.connect(self._refresh_ticket_list_async)
        self.open_ticket_btn = QPushButton("Открыть")
        self.open_ticket_btn.clicked.connect(self._on_open_ticket)
        tickets_buttons.addWidget(self.refresh_list_btn)
        tickets_buttons.addWidget(self.open_ticket_btn)
        tickets_layout.addLayout(tickets_buttons)
        left_layout.addWidget(tickets_group, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.ticket_info_label = QLabel("Тикет не выбран")
        self.ticket_info_label.setStyleSheet("font-weight: 700; padding: 6px; background: #eef2ff;")
        right_layout.addWidget(self.ticket_info_label)

        lists_layout = QHBoxLayout()
        self.messages_list = QListWidget()
        self.actions_list = QListWidget()
        lists_layout.addWidget(self.messages_list, 2)
        lists_layout.addWidget(self.actions_list, 1)
        right_layout.addLayout(lists_layout, 1)

        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Сообщение")
        self.input_line.returnPressed.connect(self._on_send)
        right_layout.addWidget(self.input_line)

        actions = QHBoxLayout()
        self.send_btn = QPushButton("Отправить")
        self.send_btn.clicked.connect(self._on_send)
        self.close_ticket_btn = QPushButton("Закрыть тикет")
        self.close_ticket_btn.clicked.connect(self._on_close_ticket)
        self.tool_status_label = QLabel("")
        actions.addWidget(self.send_btn)
        actions.addWidget(self.close_ticket_btn)
        actions.addWidget(self.tool_status_label, 1)
        right_layout.addLayout(actions)

        layout.addWidget(left, 1)
        layout.addWidget(right, 2)

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
        self.profile_summary.setText(self.current_requester_profile_summary())

    def _profiles(self) -> List[dict]:
        profiles = self._profiles_data.get("profiles")
        return profiles if isinstance(profiles, list) else []

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
            display_name.setText(profile.get("display_name") or "" if profile else "")
            full_name.setText(profile.get("full_name") or "" if profile else "")
            building.setText(profile.get("building") or "" if profile else "")
            room.setText(profile.get("room") or "" if profile else "")
            phone.setText(profile.get("phone") or "" if profile else "")

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
        self.profile_summary.setText(self.current_requester_profile_summary())

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
            item = QListWidgetItem(f"[{code}] {title} ({status})")
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
        self.ticket_info_label.setText(f"Тикет {code} | Статус: {ticket.get('status', 'unknown')}")
        self.messages_list.clear()
        for message in messages:
            role = message.get("from_role") or "user"
            self.messages_list.addItem(f"[{message.get('ts', '')}] {role}: {message.get('text', '')}")
        merged_events = list(events) + self.local_action_buffer.get(self.active_ticket_id, [])
        self.actions_list.clear()
        for event in merged_events:
            event_type = event.get("type") or event.get("event_type") or "event"
            self.actions_list.addItem(f"[{event.get('ts', '')}] {event_type}")

    def _on_create_ticket(self) -> None:
        asyncio.create_task(self._async_create_ticket())

    async def _async_create_ticket(self) -> None:
        description = self.description_input.toPlainText().strip()
        if not description:
            QMessageBox.warning(self, "Ошибка", "Опишите проблему")
            return
        requester_profile, display_name = self._current_requester_payload()
        self.create_ticket_btn.setEnabled(False)
        try:
            result = await self.ticket_client.create_ticket(
                description=description,
                title="Support Request",
                tags=[],
                requester_profile=requester_profile,
                user_display_name=display_name,
                urgency=False,
                importance=False,
                urgency_reason="Не указано при создании",
                importance_reason="Не указано при создании",
            )
            if result.get("status") != "ok":
                raise RuntimeError(str(result))
            ticket = result.get("ticket", {})
            self.active_ticket_id = ticket.get("ticket_id")
            self.description_input.clear()
            self._ticket_detail_timer.start(2500)
            await self._async_refresh_ticket_list()
            await self._async_refresh_ticket_detail()
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

    def _show_chat_screen(self) -> None:
        self.input_line.setFocus()
