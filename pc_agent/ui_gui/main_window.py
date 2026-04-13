"""
Главное окно GUI приложения.
"""

import asyncio
import json
import time
from typing import Set, Optional, Dict, Any
import aiohttp
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QStatusBar, QLabel, QGroupBox, QHBoxLayout, QPushButton,
    QMessageBox, QApplication, QDialog, QLineEdit, QFormLayout,
    QCheckBox, QSpinBox, QSplitter, QScrollArea, QFrame,
    QComboBox, QPlainTextEdit,
)
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from loguru import logger

from .consent_dialog import ConsentDialog
from .chat_panel import ChatPanel, ProfileSidebarWidget
from . import theme
from pc_agent.version import AGENT_VERSION


class MainWindow(QMainWindow):
    """
    Главное окно приложения.
    
    Отображает логи событий и статус подключения.
    """
    
    def __init__(self, host: str, port: int, auth_token: Optional[str] = None, parent=None):
        """
        Инициализация главного окна.
        
        Args:
            host: Хост UI API сервера
            port: Порт UI API сервера
            auth_token: Токен аутентификации для API запросов
            parent: Родительское окно
        """
        super().__init__(parent)
        self.host = host
        self.port = port
        self.auth_token = auth_token  # Сохраняем токен для передачи в ChatPanel
        self.open_dialogs: Set[str] = set()  # Множество открытых consent_token
        self._seen_invites = set()  # Множество обработанных chat_invite по job_id
        
        # Этап 4: запись экрана — operation_id для STOP и виджет кнопки
        self._recording_operation_id: Optional[str] = None
        self._stop_button_widget: Optional[QWidget] = None
        
        # Текущий job_id активного чата (для привязки consent к чату)
        # session_key == текущий chat job_id, полученный из /api/chat_start
        self.current_chat_job_id: Optional[str] = None
        self._settings_form_loaded: bool = False
        self._settings_snapshot: Optional[Dict[str, Any]] = None
        self._bridge_connected: bool = False
        self._server_connection_state: str = "starting"
        self._server_connection_detail: str = ""
        self._runtime_logs_dir: Optional[str] = None
        
        self.setWindowTitle(f"Maria Agent v{AGENT_VERSION}")
        self.setMinimumSize(1200, 760)
        self.resize(1320, 840)
        
        self._setup_ui()
        self._render_connection_status()

    @staticmethod
    def _repair_text(text: str) -> str:
        if not isinstance(text, str) or not text:
            return text
        # Typical UTF-8/CP1251 mojibake marker set.
        if not any(ch in text for ch in ("Р", "С", "Ѓ", "Ћ", "™", "ќ", "Ђ", "№")):
            return text
        try:
            fixed = text.encode("cp1251").decode("utf-8")
        except Exception:
            return text
        return fixed if fixed and fixed != text else text

    def _repair_widget_texts(self, root: QWidget) -> None:
        if root is None:
            return
        try:
            root.setWindowTitle(self._repair_text(root.windowTitle()))
        except Exception:
            pass
        for w in root.findChildren(QWidget):
            try:
                w.setWindowTitle(self._repair_text(w.windowTitle()))
            except Exception:
                pass
            if isinstance(w, QGroupBox):
                w.setTitle(self._repair_text(w.title()))
            if isinstance(w, (QLabel, QPushButton, QCheckBox)):
                w.setText(self._repair_text(w.text()))
            if isinstance(w, QLineEdit):
                w.setPlaceholderText(self._repair_text(w.placeholderText()))
    
    def _setup_ui(self):
        """Настройка UI главного окна."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet(f"background: {theme.BG_PAGE};")

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(8)

        self.title_label = QLabel(f"Maria Agent v{AGENT_VERSION}")
        self.title_label.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {theme.TEXT_PRIMARY}; background: transparent;"
        )
        top_bar.addWidget(self.title_label)
        self.profile_top_status = QLabel("")
        self.profile_top_status.setStyleSheet(
            f"padding: 6px 10px; border-radius: 999px; background: {theme.INFO_BG}; color: {theme.INFO_FG}; font-weight: 700;"
        )
        top_bar.addWidget(self.profile_top_status)
        top_bar.addStretch()

        self.settings_btn = QPushButton("Настройки")
        self.settings_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {theme.BORDER}; border-radius: 14px; background: {theme.BG_INPUT}; padding: 8px 14px; color: {theme.TEXT_PRIMARY}; }}"
            f"QPushButton:hover {{ background: {theme.LIST_ITEM_HOVER}; }}"
        )
        self.settings_btn.clicked.connect(self._show_settings_dialog)
        top_bar.addWidget(self.settings_btn)
        layout.addLayout(top_bar)

        self.chat_panel = ChatPanel(base_url=None, auth_token=self.auth_token)
        self.profile_sidebar = ProfileSidebarWidget(self.chat_panel)
        self.chat_panel.set_profile_sidebar(self.profile_sidebar)

        self.body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.body_splitter.setChildrenCollapsible(False)
        self.body_splitter.addWidget(self.profile_sidebar)
        self.body_splitter.addWidget(self.chat_panel)
        self.body_splitter.setStretchFactor(0, 0)
        self.body_splitter.setStretchFactor(1, 1)
        self.body_splitter.setSizes([320, 980])
        self._split_sizes_with_profile = [320, 980]

        layout.addWidget(self.body_splitter, 1)
        self.chat_panel.chatSessionChanged.connect(self._on_chat_session_changed)
        self.chat_panel.requesterProfileChanged.connect(self._render_profile_status)
        self.chat_panel.listNavigationVisibilityChanged.connect(self._on_list_navigation_visibility_changed)
        self._render_profile_status()
        self._on_list_navigation_visibility_changed(True)

        self.settings_dialog = QDialog(self)
        self.settings_dialog.setWindowTitle("Настройки")
        self.settings_dialog.setModal(True)
        self.settings_dialog.setMinimumWidth(520)
        self.settings_dialog.setMinimumHeight(400)
        self.settings_dialog.setMaximumHeight(900)

        dlg_root = QVBoxLayout(self.settings_dialog)
        dlg_root.setContentsMargins(8, 8, 8, 8)
        dlg_root.setSpacing(8)

        scroll = QScrollArea(self.settings_dialog)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        settings_layout = QVBoxLayout(scroll_content)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        settings_layout.setSpacing(12)

        device_group = QGroupBox("Информация об устройстве")
        device_layout = QFormLayout(device_group)
        device_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        uuid_layout = QHBoxLayout()
        self.device_uuid_label = QLabel()
        self.device_uuid_label.setStyleSheet(
            f"font-family: monospace; font-size: 13px; padding: 8px; "
            f"background: {theme.BG_INPUT}; border: 1px solid {theme.BORDER}; border-radius: 10px; "
            f"color: {theme.TEXT_PRIMARY};"
        )
        self.device_uuid_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        uuid_layout.addWidget(self.device_uuid_label)
        copy_uuid_btn = QPushButton("Копировать")
        copy_uuid_btn.clicked.connect(self._copy_device_uuid)
        uuid_layout.addWidget(copy_uuid_btn)
        uuid_widget = QWidget()
        uuid_widget.setLayout(uuid_layout)
        device_layout.addRow("Device ID:", uuid_widget)

        self.config_path_label = QLabel("—")
        self.config_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        device_layout.addRow("Файл конфига:", self.config_path_label)
        self.config_path_hint = QLabel(
            "Агент читает и сохраняет настройки в этот файл (внутри data_root). "
            "Правка только pc_agent/config/settings.yaml в клоне репозитория не меняет работающий агент, "
            "если у него другой data_root — меняйте здесь или скопируйте YAML по указанному пути."
        )
        self.config_path_hint.setWordWrap(True)
        self.config_path_hint.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        device_layout.addRow(self.config_path_hint)
        settings_layout.addWidget(device_group)

        server_group = QGroupBox("Сервер")
        server_form = QFormLayout(server_group)
        self.api_url_input = QLineEdit()
        self.ws_url_input = QLineEdit()
        self.reconnect_spin = QSpinBox()
        self.reconnect_spin.setRange(1, 3600)
        self.reconnect_spin.setValue(5)
        server_form.addRow("API URL:", self.api_url_input)
        server_form.addRow("WS URL:", self.ws_url_input)
        server_form.addRow("Интервал reconnect (с):", self.reconnect_spin)
        settings_layout.addWidget(server_group)

        ui_bridge_group = QGroupBox("Локальный UI-мост (только этот компьютер)")
        ui_bridge_outer = QVBoxLayout(ui_bridge_group)
        ui_bridge_form = QFormLayout()
        ui_bridge_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.ui_host_input = QLineEdit()
        self.ui_port_spin = QSpinBox()
        self.ui_port_spin.setRange(1, 65535)
        self.ui_port_spin.setValue(8765)
        self.ui_enabled_checkbox = QCheckBox("Разрешить GUI (ui.enabled)")
        self.ui_autostart_checkbox = QCheckBox("Автозапуск окна при старте агента (ui.autostart_gui)")
        ui_bridge_form.addRow("Хост UI API:", self.ui_host_input)
        ui_bridge_form.addRow("Порт UI API:", self.ui_port_spin)
        ui_bridge_form.addRow("", self.ui_enabled_checkbox)
        ui_bridge_form.addRow("", self.ui_autostart_checkbox)
        ui_bridge_outer.addLayout(ui_bridge_form)
        self.ui_bridge_hint = QLabel(
            "Порт и хост — для связи окна Maria Agent с процессом ws_agent (SSE, настройки). "
            "На удалённый сервер (WS/API) не влияет. После смены порта или хоста нужен перезапуск агента."
        )
        self.ui_bridge_hint.setWordWrap(True)
        self.ui_bridge_hint.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        ui_bridge_outer.addWidget(self.ui_bridge_hint)
        settings_layout.addWidget(ui_bridge_group)

        runtime_group = QGroupBox("Always-on и логи")
        runtime_outer = QVBoxLayout(runtime_group)
        runtime_form = QFormLayout()
        runtime_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.ui_tray_enabled_checkbox = QCheckBox("Включить tray")
        self.ui_minimize_to_tray_checkbox = QCheckBox("Закрытие окна сворачивает в tray")
        self.ui_start_hidden_checkbox = QCheckBox("Запускать окно скрытым в tray")
        self.ui_notifications_checkbox = QCheckBox("Показывать tray-уведомления")
        self.logging_level_combo = QComboBox()
        self.logging_console_level_combo = QComboBox()
        for level_name in ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]:
            self.logging_level_combo.addItem(level_name)
            self.logging_console_level_combo.addItem(level_name)
        self.logging_rotation_input = QLineEdit()
        self.logging_retention_input = QLineEdit()
        self.logging_compression_input = QLineEdit()
        runtime_form.addRow("", self.ui_tray_enabled_checkbox)
        runtime_form.addRow("", self.ui_minimize_to_tray_checkbox)
        runtime_form.addRow("", self.ui_start_hidden_checkbox)
        runtime_form.addRow("", self.ui_notifications_checkbox)
        runtime_form.addRow("Уровень файла:", self.logging_level_combo)
        runtime_form.addRow("Уровень консоли:", self.logging_console_level_combo)
        runtime_form.addRow("Rotation:", self.logging_rotation_input)
        runtime_form.addRow("Retention:", self.logging_retention_input)
        runtime_form.addRow("Compression:", self.logging_compression_input)
        runtime_outer.addLayout(runtime_form)
        diagnostics_actions = QHBoxLayout()
        self.refresh_runtime_btn = QPushButton("Обновить диагностику")
        self.refresh_runtime_btn.setObjectName("SecondaryButton")
        self.refresh_runtime_btn.clicked.connect(self._on_refresh_runtime_clicked)
        diagnostics_actions.addWidget(self.refresh_runtime_btn)
        self.open_logs_btn = QPushButton("Открыть папку логов")
        self.open_logs_btn.setObjectName("SecondaryButton")
        self.open_logs_btn.clicked.connect(self._on_open_logs_clicked)
        diagnostics_actions.addWidget(self.open_logs_btn)
        diagnostics_actions.addStretch()
        runtime_outer.addLayout(diagnostics_actions)
        self.runtime_status_label = QLabel("Диагностика ещё не загружена.")
        self.runtime_status_label.setWordWrap(True)
        self.runtime_status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.runtime_status_label.setStyleSheet(
            f"padding: 8px; background: {theme.BG_INPUT}; border: 1px solid {theme.BORDER}; "
            f"border-radius: 10px; color: {theme.TEXT_SECONDARY};"
        )
        runtime_outer.addWidget(self.runtime_status_label)
        self.runtime_logs_view = QPlainTextEdit()
        self.runtime_logs_view.setReadOnly(True)
        self.runtime_logs_view.setMinimumHeight(180)
        self.runtime_logs_view.setPlaceholderText("Последние строки agent.log появятся здесь.")
        runtime_outer.addWidget(self.runtime_logs_view)
        settings_layout.addWidget(runtime_group)

        paths_group = QGroupBox("Пути (относительно data_root)")
        paths_form = QFormLayout(paths_group)
        self.data_dir_input = QLineEdit()
        paths_form.addRow("data_dir:", self.data_dir_input)
        settings_layout.addWidget(paths_group)

        modules_group = QGroupBox("Модули и безопасность")
        modules_form = QFormLayout(modules_group)
        self.enabled_modules_input = QLineEdit()
        self.enabled_modules_input.setPlaceholderText("system, screen, ...")
        self.allow_remote_code_checkbox = QCheckBox("Разрешить удалённое выполнение кода")
        self.installed_modules_label = QLabel("—")
        self.installed_modules_label.setWordWrap(True)
        self.installed_modules_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.installed_modules_label.setStyleSheet(
            f"font-family: Consolas, 'Courier New', monospace; font-size: 11px; padding: 8px; "
            f"background: {theme.BG_INPUT}; border: 1px solid {theme.BORDER}; border-radius: 10px; "
            f"color: {theme.TEXT_SECONDARY};"
        )
        modules_form.addRow("Включённые модули:", self.enabled_modules_input)
        self.enabled_modules_hint = QLabel(
            "В списке — встроенные модули, которые агент загружает при старте. "
            "«system» и «screen» всегда добавляются автоматически (их нельзя отключить через YAML). "
            "Остальные имена (например diag_logs) подключаются только если они есть в образе агента; "
            "пакеты из modules_store обрабатываются отдельно (см. установленные модули ниже)."
        )
        self.enabled_modules_hint.setWordWrap(True)
        self.enabled_modules_hint.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        modules_form.addRow(self.enabled_modules_hint)
        modules_form.addRow("", self.allow_remote_code_checkbox)
        modules_form.addRow("Установленные модули:", self.installed_modules_label)
        settings_layout.addWidget(modules_group)

        auth_group = QGroupBox("Токен агента")
        auth_form = QFormLayout(auth_group)
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Введите новый токен (или оставьте пустым)")
        self.clear_token_checkbox = QCheckBox("Очистить токен")
        self.token_hint_label = QLabel("Текущий токен: —")
        self.token_hint_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; background: transparent;")
        auth_form.addRow("Новый токен:", self.token_input)
        auth_form.addRow("", self.clear_token_checkbox)
        auth_form.addRow("", self.token_hint_label)
        settings_layout.addWidget(auth_group)

        profile_group = QGroupBox("Профиль инициатора")
        profile_form = QFormLayout(profile_group)
        self.profile_summary_label = QLabel(self.chat_panel.current_requester_profile_summary())
        self.profile_summary_label.setWordWrap(True)
        self.profile_manage_btn = QPushButton("Открыть профили")
        self.profile_manage_btn.setObjectName("PrimaryButton")
        self.profile_manage_btn.clicked.connect(self._on_manage_requester_profiles_clicked)
        profile_form.addRow("Активный профиль:", self.profile_summary_label)
        profile_form.addRow("", self.profile_manage_btn)
        settings_layout.addWidget(profile_group)

        self.settings_status_label = QLabel("")
        self.settings_status_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; background: transparent;")
        settings_layout.addWidget(self.settings_status_label)

        scroll.setWidget(scroll_content)
        dlg_root.addWidget(scroll, 1)

        buttons_layout = QHBoxLayout()
        self.test_connection_btn = QPushButton("Проверить соединение")
        self.test_connection_btn.setObjectName("SecondaryButton")
        self.test_connection_btn.clicked.connect(self._on_test_connection_clicked)
        buttons_layout.addWidget(self.test_connection_btn)

        self.save_settings_btn = QPushButton("Сохранить")
        self.save_settings_btn.setObjectName("PrimaryButton")
        self.save_settings_btn.clicked.connect(self._on_save_settings_clicked)
        buttons_layout.addWidget(self.save_settings_btn)

        self.restart_agent_btn = QPushButton("Перезапустить агент")
        self.restart_agent_btn.setObjectName("SecondaryButton")
        self.restart_agent_btn.clicked.connect(self._on_restart_agent_clicked)
        buttons_layout.addWidget(self.restart_agent_btn)
        buttons_layout.addStretch()

        close_settings_btn = QPushButton("Закрыть")
        close_settings_btn.setObjectName("SecondaryButton")
        close_settings_btn.clicked.connect(self.settings_dialog.reject)
        buttons_layout.addWidget(close_settings_btn)
        dlg_root.addLayout(buttons_layout)

        theme.apply_agent_dialog_theme(self.settings_dialog)

        self.api_url_input.textChanged.connect(self._on_settings_field_changed)
        self.ws_url_input.textChanged.connect(self._on_settings_field_changed)
        self.reconnect_spin.valueChanged.connect(self._on_settings_field_changed)
        self.ui_host_input.textChanged.connect(self._on_settings_field_changed)
        self.ui_port_spin.valueChanged.connect(self._on_settings_field_changed)
        self.ui_enabled_checkbox.toggled.connect(self._on_settings_field_changed)
        self.ui_autostart_checkbox.toggled.connect(self._on_settings_field_changed)
        self.ui_tray_enabled_checkbox.toggled.connect(self._on_settings_field_changed)
        self.ui_minimize_to_tray_checkbox.toggled.connect(self._on_settings_field_changed)
        self.ui_start_hidden_checkbox.toggled.connect(self._on_settings_field_changed)
        self.ui_notifications_checkbox.toggled.connect(self._on_settings_field_changed)
        self.logging_level_combo.currentIndexChanged.connect(self._on_settings_field_changed)
        self.logging_console_level_combo.currentIndexChanged.connect(self._on_settings_field_changed)
        self.logging_rotation_input.textChanged.connect(self._on_settings_field_changed)
        self.logging_retention_input.textChanged.connect(self._on_settings_field_changed)
        self.logging_compression_input.textChanged.connect(self._on_settings_field_changed)
        self.data_dir_input.textChanged.connect(self._on_settings_field_changed)
        self.enabled_modules_input.textChanged.connect(self._on_settings_field_changed)
        self.allow_remote_code_checkbox.toggled.connect(self._on_settings_field_changed)
        self.token_input.textChanged.connect(self._on_settings_field_changed)
        self.clear_token_checkbox.toggled.connect(self._on_settings_field_changed)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"padding: 6px 12px; border-radius: 999px; background: {theme.INFO_BG}; color: {theme.INFO_FG}; font-weight: 700;"
        )
        self.status_bar.addWidget(self.status_label)

        self._repair_widget_texts(self)
        self._repair_widget_texts(self.settings_dialog)
        self._add_log("GUI запущен", "info")
        self._load_device_uuid()

    def _on_list_navigation_visibility_changed(self, list_mode: bool) -> None:
        """В режиме чата скрываем панель профиля — область тикета на всю ширину."""
        if not list_mode:
            cur = self.body_splitter.sizes()
            if cur and cur[0] > 0:
                self._split_sizes_with_profile = list(cur)
        self.profile_sidebar.setVisible(list_mode)
        if list_mode:
            w = max(280, self._split_sizes_with_profile[0] if self._split_sizes_with_profile else 320)
            rest = max(400, self.body_splitter.width() - w - 12)
            self.body_splitter.setSizes([w, rest])

    def _add_log(self, message: str, level: str = "info"):
        """
        Добавляет запись в лог.
        
        Args:
            message: Текст сообщения
            level: Уровень (info, warning, error, success)
        """
        # В новом UI отдельной вкладки логов нет; не дублируем сообщения в терминал.
        # Это также предотвращает циклическое размножение event_type=log.
        return

    def _show_settings_dialog(self):
        """Открывает диалог настроек."""
        self._settings_form_loaded = False
        self._settings_snapshot = None
        self._load_device_uuid()
        self.profile_summary_label.setText(self.chat_panel.current_requester_profile_summary())
        self._render_profile_status()
        self._set_settings_status("Загрузка настроек...", error=False)
        QTimer.singleShot(0, lambda: asyncio.create_task(self._async_load_settings()))
        self.settings_dialog.exec()

    def _on_manage_requester_profiles_clicked(self):
        self.chat_panel.open_profile_manager()
        self.profile_summary_label.setText(self.chat_panel.current_requester_profile_summary())
        self._render_profile_status()

    def _render_profile_status(self) -> None:
        has_profile = bool(self.chat_panel.has_active_profile())
        if has_profile:
            text = f"Профиль: {self.chat_panel.current_requester_profile_summary()}"
            bg = "#e0ead8"
            fg = "#2d4a22"
        else:
            text = "Профиль не выбран (обязательно)"
            bg = "#f5e4e0"
            fg = "#8b2c1a"
        self.profile_top_status.setText(self._repair_text(text))
        self.profile_top_status.setStyleSheet(
            f"padding: 6px 10px; border-radius: 999px; background: {bg}; color: {fg}; font-weight: 700;"
        )

    def _ui_bridge_host_port(self) -> tuple[str, int]:
        """Адрес локального UiApiServer — из актуального get_config().ui (как при bind в ws_agent)."""
        try:
            from pc_agent.config.config_loader import get_config

            ui = get_config().ui
            h = str(ui.host or "").strip() or "127.0.0.1"
            p = int(ui.port)
            if not (1 <= p <= 65535):
                raise ValueError("ui.port out of range")
            return h, p
        except Exception:
            h = str(getattr(self, "host", None) or "").strip() or "127.0.0.1"
            try:
                p = int(getattr(self, "port", 8765))
            except (TypeError, ValueError):
                p = 8765
            if not (1 <= p <= 65535):
                p = 8765
            return h, p

    def _settings_api_url(self, path: str) -> str:
        h, p = self._ui_bridge_host_port()
        pth = path if path.startswith("/") else f"/{path}"
        return f"http://{h}:{p}{pth}"

    def _set_settings_status(self, text: str, error: bool = False) -> None:
        color = theme.DANGER_FG if error else theme.TEXT_MUTED
        self.settings_status_label.setStyleSheet(f"color: {color}; background: transparent;")
        self.settings_status_label.setText(self._repair_text(text))

    def _set_settings_buttons_enabled(self, enabled: bool) -> None:
        self.test_connection_btn.setEnabled(enabled)
        self.save_settings_btn.setEnabled(enabled)
        self.restart_agent_btn.setEnabled(enabled)

    def _show_nonblocking_message(
        self,
        title: str,
        text: str,
        icon: QMessageBox.Icon = QMessageBox.Icon.Information,
    ) -> None:
        """Показывает сообщение без modal exec(), чтобы не блокировать asyncio loop."""
        box = QMessageBox(self)
        box.setWindowTitle(self._repair_text(title))
        box.setText(self._repair_text(text))
        box.setIcon(icon)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        box.open()

    async def _ask_yes_no_async(self, title: str, text: str) -> bool:
        """Асинхронный вопрос Да/Нет без вложенного event-loop."""
        answer_future = asyncio.get_running_loop().create_future()

        box = QMessageBox(self)
        box.setWindowTitle(self._repair_text(title))
        box.setText(self._repair_text(text))
        box.setIcon(QMessageBox.Icon.Question)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.Yes)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        def on_finished(result: int) -> None:
            if not answer_future.done():
                answer_future.set_result(result == int(QMessageBox.StandardButton.Yes))

        box.finished.connect(on_finished)
        box.open()
        return bool(await answer_future)

    def _collect_settings_payload(self, include_auth: bool) -> Dict[str, Any]:
        modules = [m.strip() for m in self.enabled_modules_input.text().split(",") if m.strip()]
        payload: Dict[str, Any] = {
            "settings": {
                "server": {
                    "api_url": self.api_url_input.text().strip(),
                    "ws_url": self.ws_url_input.text().strip(),
                    "reconnect_interval": int(self.reconnect_spin.value()),
                },
                "security": {
                    "allow_remote_code": bool(self.allow_remote_code_checkbox.isChecked()),
                },
                "paths": {
                    "data_dir": self.data_dir_input.text().strip(),
                },
                "logging": {
                    "level": self.logging_level_combo.currentText().strip() or "INFO",
                    "console_level": self.logging_console_level_combo.currentText().strip() or "INFO",
                    "rotation": self.logging_rotation_input.text().strip() or "20 MB",
                    "retention": self.logging_retention_input.text().strip() or "14 days",
                    "compression": self.logging_compression_input.text().strip() or "zip",
                },
                "enabled_modules": modules,
                "ui": {
                    "enabled": bool(self.ui_enabled_checkbox.isChecked()),
                    "host": self.ui_host_input.text().strip() or "127.0.0.1",
                    "port": int(self.ui_port_spin.value()),
                    "autostart_gui": bool(self.ui_autostart_checkbox.isChecked()),
                    "tray_enabled": bool(self.ui_tray_enabled_checkbox.isChecked()),
                    "minimize_to_tray": bool(self.ui_minimize_to_tray_checkbox.isChecked()),
                    "start_hidden": bool(self.ui_start_hidden_checkbox.isChecked()),
                    "notifications_enabled": bool(self.ui_notifications_checkbox.isChecked()),
                },
            }
        }
        if include_auth:
            auth_payload: Dict[str, Any] = {}
            token_text = self.token_input.text().strip()
            if self.clear_token_checkbox.isChecked():
                auth_payload["token"] = ""
            elif token_text:
                auth_payload["token"] = token_text
            if auth_payload:
                payload["auth"] = auth_payload
        return payload

    def _is_settings_dirty(self) -> bool:
        if not self._settings_form_loaded or self._settings_snapshot is None:
            return False
        current = self._collect_settings_payload(include_auth=False).get("settings", {})
        if current != self._settings_snapshot:
            return True
        if self.clear_token_checkbox.isChecked():
            return True
        if bool(self.token_input.text().strip()):
            return True
        return False

    def _on_settings_field_changed(self, *_args):
        if not self._settings_form_loaded:
            return
        if self._is_settings_dirty():
            self._set_settings_status("Есть несохранённые изменения.", error=False)
        else:
            self._set_settings_status("Изменений нет.", error=False)

    async def _async_ui_request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self._settings_api_url(path)
        timeout = aiohttp.ClientTimeout(total=10)
        kw: Dict[str, Any] = {}
        if payload is not None and method.upper() != "GET":
            kw["json"] = payload
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method.upper(),
                url,
                headers={"Accept": "application/json"},
                **kw,
            ) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text) if text.strip() else {}
                except json.JSONDecodeError:
                    snippet = (text or "").strip().replace("\n", " ")[:280]
                    hint = ""
                    if resp.status == 404 and ("<!DOCTYPE" in text or "File not found" in text):
                        hint = (
                            f" Запрос: {url}. На этом адресе нет /ui/settings у pc_agent "
                            f"(нужен запущенный UiApiServer на ui.host/ui.port из data_root/settings.yaml)."
                        )
                    logger.error("Ответ UI-моста не JSON: HTTP {} — {}{}", resp.status, snippet, hint)
                    raise RuntimeError(
                        f"Ожидался JSON от локального моста (HTTP {resp.status}).{hint or ' Проверьте порт и процесс ws_agent.'}"
                    )
                if resp.status >= 400:
                    error = data.get("error") if isinstance(data, dict) else None
                    raise Exception(str(error or text or f"HTTP {resp.status}"))
                if not isinstance(data, dict):
                    return {"status": "ok", "result": data}
                return data

    def _on_refresh_runtime_clicked(self) -> None:
        asyncio.create_task(self._async_load_runtime_diagnostics())

    async def _async_load_runtime_diagnostics(self) -> None:
        try:
            status_data = await self._async_ui_request("GET", "/ui/agent/status")
            logs_data = await self._async_ui_request("GET", "/ui/agent/logs?source=agent&lines=120")
        except Exception as e:
            self.runtime_status_label.setText(self._repair_text(f"Ошибка диагностики: {e}"))
            self.runtime_logs_view.setPlainText("")
            return

        runtime = status_data
        log_runtime = runtime.get("log_runtime") if isinstance(runtime, dict) else {}
        self._runtime_logs_dir = str(runtime.get("logs_dir") or "") if isinstance(runtime, dict) else None
        summary_lines = [
            f"Device ID: {runtime.get('device_id', '—')}",
            f"Connection: {runtime.get('connection_state', '—')} / {runtime.get('connection_detail', '')}".strip(),
            f"Changed at: {runtime.get('connection_changed_at', '—')}",
            f"Uptime: {runtime.get('uptime_seconds', '—')} сек",
            f"UI bridge: {'up' if runtime.get('ui_bridge_running') else 'down'}",
            f"Subscribers: {runtime.get('event_bus_subscribers', 0)}",
            f"Log level: {log_runtime.get('level', '—')} (console {log_runtime.get('console_level', '—')})",
            f"Log file: {log_runtime.get('file', '—')}",
        ]
        self.runtime_status_label.setText(self._repair_text("\n".join(summary_lines)))
        self.runtime_logs_view.setPlainText(str(logs_data.get("text") or ""))

    def _on_open_logs_clicked(self) -> None:
        if not self._runtime_logs_dir:
            QMessageBox.information(self, "Логи", "Сначала обновите диагностику, чтобы получить путь к логам.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._runtime_logs_dir))

    def _format_installed_modules_text(self, modules_data: Any) -> str:
        if not isinstance(modules_data, list) or not modules_data:
            return "Нет установленных модулей."

        lines: list[str] = []
        for item in modules_data:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name") or "").strip()
            if not name:
                continue

            versions_raw = item.get("versions", [])
            versions: list[str] = []
            if isinstance(versions_raw, list):
                versions = [str(v).strip() for v in versions_raw if str(v).strip()]

            active_raw = item.get("active")
            active = str(active_raw).strip() if active_raw is not None else ""

            if versions:
                line = f"{name}: {', '.join(versions)}"
                if active:
                    line += f" (активная: {active})"
            else:
                line = f"{name}: версия не определена"
            lines.append(line)

        if not lines:
            return "Нет установленных модулей."
        return "\n".join(lines)

    def _apply_settings_to_form(self, settings_data: Dict[str, Any]) -> None:
        settings = settings_data.get("settings") if "settings" in settings_data else settings_data
        server = settings.get("server", {})
        security = settings.get("security", {})
        paths = settings.get("paths", {})
        logging_cfg = settings.get("logging", {}) or {}
        ui_cfg = settings.get("ui", {}) or {}
        enabled_modules = settings.get("enabled_modules", [])
        installed_modules = settings.get("installed_modules", [])
        auth = settings.get("auth", {})
        meta = settings.get("meta", {})

        self._settings_form_loaded = False
        self.api_url_input.setText(str(server.get("api_url", "")))
        self.ws_url_input.setText(str(server.get("ws_url", "")))
        self.reconnect_spin.setValue(int(server.get("reconnect_interval", 5) or 5))
        self.ui_host_input.setText(str(ui_cfg.get("host", "127.0.0.1")))
        self.ui_port_spin.setValue(int(ui_cfg.get("port", 8765) or 8765))
        self.ui_enabled_checkbox.setChecked(bool(ui_cfg.get("enabled", False)))
        self.ui_autostart_checkbox.setChecked(bool(ui_cfg.get("autostart_gui", False)))
        self.ui_tray_enabled_checkbox.setChecked(bool(ui_cfg.get("tray_enabled", True)))
        self.ui_minimize_to_tray_checkbox.setChecked(bool(ui_cfg.get("minimize_to_tray", True)))
        self.ui_start_hidden_checkbox.setChecked(bool(ui_cfg.get("start_hidden", False)))
        self.ui_notifications_checkbox.setChecked(bool(ui_cfg.get("notifications_enabled", True)))
        self.logging_level_combo.setCurrentText(str(logging_cfg.get("level", "INFO")))
        self.logging_console_level_combo.setCurrentText(str(logging_cfg.get("console_level", "INFO")))
        self.logging_rotation_input.setText(str(logging_cfg.get("rotation", "20 MB")))
        self.logging_retention_input.setText(str(logging_cfg.get("retention", "14 days")))
        self.logging_compression_input.setText(str(logging_cfg.get("compression", "zip")))
        self.data_dir_input.setText(str(paths.get("data_dir", "")))
        self.enabled_modules_input.setText(", ".join(enabled_modules if isinstance(enabled_modules, list) else []))
        self.installed_modules_label.setText(self._repair_text(self._format_installed_modules_text(installed_modules)))
        self.allow_remote_code_checkbox.setChecked(bool(security.get("allow_remote_code", False)))
        self.token_input.clear()
        self.clear_token_checkbox.setChecked(False)

        token_masked = auth.get("token_masked") or self._repair_text("нет")
        self.token_hint_label.setText(self._repair_text(f"Текущий токен: {token_masked}"))
        self.config_path_label.setText(str(meta.get("config_path", "—")))
        self._runtime_logs_dir = None
        self._repair_widget_texts(self.settings_dialog)

        self._settings_snapshot = self._collect_settings_payload(include_auth=False).get("settings", {})
        self._settings_form_loaded = True
        self._on_settings_field_changed()

    async def _async_load_settings(self) -> None:
        self._set_settings_buttons_enabled(False)
        try:
            data = await self._async_ui_request("GET", "/ui/settings")
            if data.get("status") != "ok":
                raise Exception(data.get("error", "Не удалось загрузить настройки"))
            self._apply_settings_to_form(data)
            await self._async_load_runtime_diagnostics()
            self._set_settings_status("Настройки загружены.", error=False)
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек: {e}")
            self._set_settings_status(f"Ошибка загрузки: {e}", error=True)
        finally:
            self._set_settings_buttons_enabled(True)

    def _on_test_connection_clicked(self):
        asyncio.create_task(self._async_test_connection())

    async def _async_test_connection(self):
        self._set_settings_buttons_enabled(False)
        self._set_settings_status("Проверка соединения...", error=False)
        try:
            payload = {"settings": self._collect_settings_payload(include_auth=False).get("settings", {})}
            result = await self._async_ui_request("POST", "/ui/settings/test_connection", payload)
            ws_result = result.get("ws", {})
            api_result = result.get("api", {})
            ok = bool(result.get("ok"))
            summary = (
                f"WS: {'OK' if ws_result.get('ok') else 'FAIL'} ({ws_result.get('message', '')})\n"
                f"API: {'OK' if api_result.get('ok') else 'FAIL'} ({api_result.get('message', '')})"
            )
            self._set_settings_status("Соединение проверено.", error=not ok)
            self._show_nonblocking_message("Проверка соединения", summary, QMessageBox.Icon.Information)
        except Exception as e:
            logger.error(f"Ошибка проверки соединения: {e}")
            self._set_settings_status(f"Ошибка проверки: {e}", error=True)
            self._show_nonblocking_message(
                "Ошибка",
                f"Не удалось проверить соединение:\n{e}",
                QMessageBox.Icon.Critical,
            )
        finally:
            self._set_settings_buttons_enabled(True)

    def _on_save_settings_clicked(self):
        asyncio.create_task(self._async_save_settings(request_restart=False))

    async def _async_save_settings(self, request_restart: bool):
        self._set_settings_buttons_enabled(False)
        self._set_settings_status("Сохранение настроек...", error=False)
        token_text = self.token_input.text().strip()
        token_clear = self.clear_token_checkbox.isChecked()
        try:
            payload = self._collect_settings_payload(include_auth=True)
            result = await self._async_ui_request("POST", "/ui/settings", payload)
            if result.get("status") != "ok":
                raise Exception(result.get("error", "Не удалось сохранить настройки"))

            config_changed = bool(result.get("config_changed"))
            token_changed = bool(result.get("token_changed"))
            changed_keys = result.get("changed_keys", [])

            settings_payload = payload.get("settings", {})
            api_url = settings_payload.get("server", {}).get("api_url")
            if api_url:
                self._apply_runtime_api_url(str(api_url))

            if token_changed:
                if token_clear:
                    self._apply_runtime_auth_token(None)
                elif token_text:
                    self._apply_runtime_auth_token(token_text)

            self.token_input.clear()
            self.clear_token_checkbox.setChecked(False)
            self._settings_snapshot = self._collect_settings_payload(include_auth=False).get("settings", {})
            self._settings_form_loaded = True

            changed_count = len(changed_keys) if isinstance(changed_keys, list) else 0
            self._set_settings_status(f"Сохранено. Изменено полей: {changed_count}.", error=False)

            should_restart = request_restart
            if config_changed and not request_restart:
                restart_msg = "Настройки сохранены. Перезапустить агент сейчас?"
                if isinstance(changed_keys, list) and any(
                    str(k).startswith("ui.") for k in changed_keys
                ):
                    restart_msg = (
                        "Настройки сохранены. Порт и хост UI-моста применяются только после перезапуска агента. "
                        "Перезапустить сейчас?"
                    )
                should_restart = await self._ask_yes_no_async("Перезапуск агента", restart_msg)

            if should_restart:
                await self._async_restart_agent()
            else:
                await self._async_load_settings()
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {e}")
            self._set_settings_status(f"Ошибка сохранения: {e}", error=True)
            self._show_nonblocking_message(
                "Ошибка",
                f"Не удалось сохранить настройки:\n{e}",
                QMessageBox.Icon.Critical,
            )
        finally:
            self._set_settings_buttons_enabled(True)

    def _on_restart_agent_clicked(self):
        if self._is_settings_dirty():
            msg = QMessageBox(self)
            msg.setWindowTitle(self._repair_text("Несохранённые изменения"))
            msg.setText(self._repair_text("Обнаружены несохранённые изменения настроек."))
            btn_save = msg.addButton(self._repair_text("Сохранить и перезапустить"), QMessageBox.ButtonRole.AcceptRole)
            btn_restart = msg.addButton(self._repair_text("Перезапустить без сохранения"), QMessageBox.ButtonRole.DestructiveRole)
            msg.addButton(self._repair_text("Отмена"), QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            clicked = msg.clickedButton()
            if clicked == btn_save:
                asyncio.create_task(self._async_save_settings(request_restart=True))
                return
            if clicked != btn_restart:
                return
        else:
            confirm = QMessageBox.question(
                self,
                self._repair_text("Перезапуск агента"),
                self._repair_text("Перезапустить агент сейчас?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        asyncio.create_task(self._async_restart_agent())

    async def _async_restart_agent(self):
        self._set_settings_buttons_enabled(False)
        self._set_settings_status("Запрос на перезапуск отправлен...", error=False)
        try:
            await self._async_ui_request("POST", "/ui/agent/restart", {"reason": "user_settings", "delay_sec": 0.8})
            self._set_settings_status("Агент перезапускается...", error=False)
            self._show_nonblocking_message(
                "Перезапуск",
                "Команда перезапуска отправлена.",
                QMessageBox.Icon.Information,
            )
        except Exception as e:
            logger.error(f"Ошибка перезапуска агента: {e}")
            self._set_settings_status(f"Ошибка перезапуска: {e}", error=True)
            self._show_nonblocking_message(
                "Ошибка",
                f"Не удалось перезапустить агент:\n{e}",
                QMessageBox.Icon.Critical,
            )
        finally:
            self._set_settings_buttons_enabled(True)

    def _apply_runtime_auth_token(self, token: Optional[str]) -> None:
        self.auth_token = token
        if hasattr(self.chat_panel, "ticket_client") and self.chat_panel.ticket_client:
            self.chat_panel.ticket_client.auth_token = token

    def _apply_runtime_api_url(self, api_url: str) -> None:
        base_url = api_url.rstrip("/")
        if hasattr(self.chat_panel, "ticket_client") and self.chat_panel.ticket_client:
            self.chat_panel.ticket_client.base_url = base_url
        if hasattr(self.chat_panel, "client") and self.chat_panel.client:
            self.chat_panel.client.base_url = base_url
    
    def _on_chat_session_changed(self, job_id: str):
        """
        Обработчик изменения сессии чата.
        
        Сохраняет job_id текущего активного чата для использования
        в качестве session_key при обработке consent_required.
        
        Args:
            job_id: Идентификатор job текущего чата
        """
        self.current_chat_job_id = job_id
        logger.info(f"Текущий chat job_id установлен: {job_id}")
    
    def _render_connection_status(self) -> None:
        if not self._bridge_connected:
            text = "GUI ↔ агент: нет связи"
            bg = "#fee2e2"
            fg = "#b42318"
        elif self._server_connection_state == "connected":
            text = "Сервер: подключено"
            bg = "#dcfce7"
            fg = "#166534"
        elif self._server_connection_state in {"connecting", "authorizing", "starting"}:
            text = "Сервер: подключение..."
            bg = "#fef3c7"
            fg = "#b45309"
        elif self._server_connection_state == "auth_required":
            text = "Сервер: нужен токен"
            bg = "#fee2e2"
            fg = "#b42318"
        elif self._server_connection_state == "rejected":
            text = "Сервер: доступ отклонён"
            bg = "#fee2e2"
            fg = "#b42318"
        else:
            text = "Сервер: отключено"
            bg = "#e2e8f0"
            fg = "#475569"

        if self._server_connection_detail:
            text = f"{text} • {self._server_connection_detail}"

        self.status_label.setText(self._repair_text(text))
        self.status_label.setStyleSheet(
            f"padding: 6px 12px; border-radius: 999px; background: {bg}; color: {fg}; font-weight: 700;"
        )

    def set_bridge_connected(self, connected: bool) -> None:
        self._bridge_connected = connected
        if not connected:
            self._server_connection_detail = ""
        self._render_connection_status()

    def set_connection_state(self, state: str, detail: str = "") -> None:
        self._server_connection_state = (state or "disconnected").strip().lower()
        self._server_connection_detail = detail.strip()
        self._render_connection_status()

    def set_connected(self, connected: bool):
        self.set_connection_state("connected" if connected else "disconnected")
    
    def handle_event(self, event: dict):
        """
        Обрабатывает событие от SSE клиента.
        
        Args:
            event: Словарь с данными события
        """
        # ====== ИНТЕГРАЦИЯ ЛОКАЛЬНЫХ СОБЫТИЙ В ACTIONS FEED ======
        # Проксируем определенные типы событий в ChatPanel для отображения в ленте действий
        event_type = event.get("event_type", "")
        
        # События, которые нужно показывать в Actions/Tools ленте
        actionable_events = [
            "tool_started", "tool_finished", "tool_running", "tool_result",
            "collect_progress", "module_observation", "notification",
            "agent_action", "tool_requested", "consent_required"
        ]
        
        if event_type in actionable_events:
            # Пытаемся определить ticket_id из события
            data = event.get("data", {})
            
            # Возможные источники ticket_id
            ticket_id = (
                data.get("ticket_id") or 
                event.get("ticket_id") or
                data.get("session_key") or
                event.get("session_key")
            )
            
            # Если есть активный тикет в ChatPanel и ticket_id не указан,
            # используем активный тикет
            if not ticket_id and self.chat_panel.active_ticket_id:
                ticket_id = self.chat_panel.active_ticket_id
            
            if ticket_id:
                # Преобразуем событие в формат для actions feed
                action_event = {
                    "type": event_type,
                    "ts": data.get("ts") or event.get("ts") or time.time(),
                    "tool_name": data.get("tool_name", ""),
                    "action": data.get("action", ""),
                    "status": data.get("status", ""),
                    "message": data.get("message", ""),
                    "source": "local"
                }
                
                # Добавляем в буфер локальных событий ChatPanel
                self.chat_panel.add_local_event(ticket_id, action_event)
                
                logger.debug(f"Локальное событие {event_type} добавлено в actions feed тикета {ticket_id[:8]}...")
        
        # ====== СТАРАЯ ОБРАБОТКА СОБЫТИЙ ======
        
        # Обработка chat_invite - автоматическое открытие чата (deprecated)
        if event.get("event") == "chat_invite":
            job_id = event.get("job_id")
            if job_id:
                if job_id in self._seen_invites:
                    return
                self._seen_invites.add(job_id)
                self.chat_panel.attach_to_job(job_id)
                self.chat_panel._show_chat_screen()
                # Опционально: добавляем системную строку в ленту
                self.chat_panel.append_event(event, source="agent")
                logger.info(f"Chat автоматически открыт для job_id={job_id}")
            else:
                logger.warning("chat_invite получен без job_id")
            return
        
        event_type = event.get("event_type", "unknown")
        data = event.get("data", {})

        if event_type == "connection_state":
            self.set_connection_state(
                str(data.get("state") or "disconnected"),
                str(data.get("detail") or ""),
            )
            return
        if event_type == "connection_rejected":
            self.set_connection_state("rejected", "подключение отклонено")
            return
        
        # Этап 4: скриншот/запись — минимизация окна и STOP-кнопка
        if event_type == "prepare_screen_capture":
            self.showMinimized()
            return
        if event_type == "screen_capture_done":
            self.showNormal()
            return
        if event_type == "prepare_screen_recording":
            self._recording_operation_id = data.get("operation_id") or ""
            self.showMinimized()
            self._show_stop_button()
            return
        if event_type == "screen_recording_done":
            self._hide_stop_button()
            self._recording_operation_id = None
            self.showNormal()
            return
        
        # Обработка событий типа "log" (логи из ws_agent.py)
        if event_type == "log":
            # Не ре-логируем входящие runtime-логи в GUI, чтобы не вызывать рекурсивный
            # цикл логирования и раздувание одинаковых строк в консоли.
            return
        
        # Обработка consent_required и tool_executed: проброс в ChatPanel, если относятся к текущему чату
        event_in_chat_timeline = False
        if event_type in ("consent_required", "tool_executed", "tool_denied"):
            # Пытаемся определить session_key
            session_key = data.get("session_key") or data.get("job_id") or ""
            
            # Проверяем, относится ли событие к текущему чату
            if (session_key 
                and self.chat_panel.current_job_id 
                and session_key == self.chat_panel.current_job_id):
                # Важно: агентские события в ленту
                # Преобразуем формат события для append_event
                normalized_event = {
                    "type": event_type,
                    "payload": data,
                    "ts": data.get("ts") or event.get("ts")
                }
                self.chat_panel.append_event(normalized_event, source="agent")
                logger.debug(f"Событие {event_type} добавлено в ленту чата (session_key={session_key[:8]}...)")
                event_in_chat_timeline = True
        
        # Логируем в таб "Agent events" только если событие не добавлено в ленту чата
        if not event_in_chat_timeline:
            # Формируем сообщение для лога (для событий, не относящихся к текущему чату)
            tool_name = data.get("tool_name", "")
            request_id = data.get("request_id", "")
            job_id = data.get("job_id", "")
            
            log_parts = [event_type]
            if tool_name:
                log_parts.append(f"tool={tool_name}")
            if request_id:
                log_parts.append(f"req_id={request_id[:8]}")
            if job_id:
                log_parts.append(f"job_id={job_id[:8]}")
            
            log_message = " | ".join(log_parts)
            
            # Определяем уровень логирования
            if event_type == "error":
                level = "error"
            elif event_type in ("consent_required", "job_started"):
                level = "warning"
            elif event_type in ("tool_executed", "job_completed"):
                level = "success"
            else:
                level = "info"
            
            self._add_log(log_message, level)
        
        # Обработка consent_required (диалог показываем всегда, независимо от ленты чата)
        if event_type == "consent_required":
            consent_token = data.get("consent_token", "")
            
            # Защита от двойных модалок
            if consent_token and consent_token not in self.open_dialogs:
                self.open_dialogs.add(consent_token)
                
                # Вычисляем session_key: приоритет - из события, затем текущий chat job_id
                # session_key == текущий chat job_id, полученный из /api/chat_start
                session_key = data.get("session_key") or self.current_chat_job_id or ""
                
                # Создаем и показываем диалог с session_key
                bh, bp = self._ui_bridge_host_port()
                dialog = ConsentDialog(event, bh, bp, self, session_key=session_key)
                
                # Удаляем токен из множества при закрытии диалога
                def on_finished(result):
                    if consent_token in self.open_dialogs:
                        self.open_dialogs.remove(consent_token)
                
                dialog.finished.connect(on_finished)
                dialog.open()  # Неблокирующий показ
            elif consent_token in self.open_dialogs:
                logger.debug(f"Диалог для consent_token={consent_token[:8]}... уже открыт, пропускаем")
    
    def _show_stop_button(self) -> None:
        """Показывает плавающую красную кнопку STOP (always-on-top, bottom-left)."""
        self._hide_stop_button()
        stop_btn = QPushButton("STOP")
        stop_btn.setFixedSize(100, 50)
        stop_btn.setStyleSheet(
            "background-color: #c00; color: white; font-weight: bold; font-size: 16px;"
            "border: 2px solid #800; border-radius: 8px;"
        )
        stop_btn.clicked.connect(self._on_stop_recording_clicked)
        widget = QWidget()
        widget.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(stop_btn)
        widget.setLayout(layout)
        # Позиция: bottom-left основного экрана
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            widget.move(geom.x() + 16, geom.bottom() - 16 - 60)
        widget.show()
        self._stop_button_widget = widget
    
    def _hide_stop_button(self) -> None:
        """Скрывает и уничтожает виджет кнопки STOP."""
        if self._stop_button_widget:
            try:
                self._stop_button_widget.close()
                self._stop_button_widget.deleteLater()
            except Exception:
                pass
            self._stop_button_widget = None
    
    def _on_stop_recording_clicked(self) -> None:
        """Отправляет запрос на досрочную остановку записи (POST /ui/stop_recording)."""
        op_id = self._recording_operation_id
        if not op_id:
            logger.warning("STOP нажата, но operation_id записи неизвестен")
            return
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._async_stop_recording(op_id))
        except RuntimeError as e:
            logger.error(f"Не удалось отправить stop_recording: {e}")
    
    async def _async_stop_recording(self, operation_id: str) -> None:
        """Асинхронная отправка сигнала остановки записи на UI API агента."""
        import aiohttp
        url = self._settings_api_url("/ui/stop_recording")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={"operation_id": operation_id}) as resp:
                    if resp.status == 200:
                        logger.info("Сигнал остановки записи отправлен")
                    else:
                        text = await resp.text()
                        logger.warning(f"stop_recording: HTTP {resp.status} {text}")
        except Exception as e:
            logger.error(f"Ошибка отправки stop_recording: {e}")

    def closeEvent(self, event):  # noqa: N802 (Qt API)
        """Безопасно останавливает фоновые UI-таймеры и виджеты при закрытии окна."""
        try:
            if hasattr(self, "chat_panel") and self.chat_panel:
                self.chat_panel._stop_ticket_list_polling()
                self.chat_panel._stop_ticket_detail_polling()
        except Exception as e:
            logger.debug(f"closeEvent: stop polling failed: {e}")
        self._hide_stop_button()
        super().closeEvent(event)
    
    def _load_device_uuid(self):
        """Загружает device UUID из identity manager."""
        try:
            from core.identity import IdentityManager
            identity_manager = IdentityManager()
            identity_data = identity_manager.load_or_create()
            device_uuid = identity_data.get('uuid', self._repair_text('Недоступно'))
            self.device_uuid_label.setText(device_uuid)
        except Exception as e:
            logger.error(f"Failed to load device UUID: {e}")
            self.device_uuid_label.setText(self._repair_text("Ошибка загрузки UUID"))
    
    def _copy_device_uuid(self):
        """Копирует device UUID в буфер обмена."""
        uuid_text = self.device_uuid_label.text()
        not_available = self._repair_text("Недоступно")
        load_error = self._repair_text("Ошибка загрузки UUID")
        if uuid_text and uuid_text != not_available and uuid_text != load_error:
            clipboard = QApplication.clipboard()
            clipboard.setText(uuid_text)
            QMessageBox.information(
                self,
                self._repair_text("Скопировано"),
                self._repair_text(f"UUID устройства скопирован в буфер:\n{uuid_text}")
            )
        else:
            QMessageBox.warning(
                self,
                self._repair_text("Ошибка"),
                self._repair_text("UUID устройства недоступен.")
            )
