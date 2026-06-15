"""
Главное окно GUI приложения.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Set, Optional, Dict, Any
from urllib.parse import urlsplit, urlunsplit
import aiohttp
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QStatusBar, QLabel, QGroupBox, QHBoxLayout, QPushButton,
    QMessageBox, QApplication, QDialog, QLineEdit, QFormLayout,
    QCheckBox, QSpinBox, QSplitter, QScrollArea, QFrame,
    QComboBox, QPlainTextEdit, QStackedWidget, QToolButton,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import QEvent, QSize, Qt, QThread, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPixmap
from loguru import logger

from .consent_dialog import ConsentDialog
from .remote_assist_dialog import RemoteAssistConsentDialog
from .user_consent_dialog import UserConsentPromptDialog
from .chat_panel import ChatPanel, ProfileSidebarWidget, TicketCreateWizardWidget, TicketsSidebarWidget
from .accessibility import account_description, connection_description, normalize_connection_state, set_uia_metadata
from .account_gate import AccountGateWidget, legacy_agent_registration_enabled
from .dynamic_form_widget import DynamicFormWidget
from . import theme
from .window_chrome import CustomTitleBar, FramelessResizeHandler
from pc_agent.config.config_loader import get_config
from pc_agent.core.account_session import (
    AccountSessionManager,
    account_session_error_action,
    account_session_error_code,
)
from pc_agent.core.user_profile import UserProfileManager
from pc_agent.remote_assist.runtime_host import create_remote_assist_thread
from pc_agent.version import AGENT_VERSION


_LOCAL_BROWSER_HOSTS = {"localhost", "127.0.0.1", "::1"}
_LEGACY_HTTP_SERVER_PORT = 8666
_PILOT_HTTPS_PROXY_PORT = 9443


def _browser_netloc(hostname: str, port: int | None) -> str:
    host = str(hostname or "").strip()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"{host}:{port}" if port else host


def _normalize_browser_handoff_origin(url: str) -> str:
    parsed = urlsplit(str(url or "").strip())
    if parsed.scheme == "http" and parsed.port == _LEGACY_HTTP_SERVER_PORT:
        hostname = parsed.hostname or ""
        if hostname and hostname.lower() not in _LOCAL_BROWSER_HOSTS:
            return urlunsplit(
                (
                    "https",
                    _browser_netloc(hostname, _PILOT_HTTPS_PROXY_PORT),
                    parsed.path,
                    parsed.query,
                    parsed.fragment,
                )
            )
    return url


def gui_soft_shadows_enabled() -> bool:
    raw = os.environ.get("PC_AGENT_ENABLE_GUI_SHADOWS", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def default_agent_registration_form() -> dict[str, Any]:
    return {
        "key": "agent_device_registration",
        "title": "Регистрация рабочего места",
        "description": "Подтвердите, кто работает за этим ПК. Данные создают заявку на регистрацию и не создают обращение.",
        "fields": [
            {"key": "full_name", "label": "ФИО", "type": "text", "required": True},
            {"key": "display_name", "label": "Отображаемое имя", "type": "text", "required": False},
            {"key": "login", "label": "Логин", "type": "text", "required": True},
            {"key": "email", "label": "Email", "type": "text", "required": False},
            {"key": "phone", "label": "Телефон", "type": "text", "required": False},
            {"key": "department", "label": "Подразделение", "type": "text", "required": False},
            {"key": "building", "label": "Здание", "type": "text", "required": False},
            {"key": "floor", "label": "Этаж", "type": "text", "required": False},
            {"key": "room", "label": "Кабинет", "type": "text", "required": False},
            {
                "key": "relationship_type",
                "label": "Тип ПК",
                "type": "select",
                "required": True,
                "options": [
                    {"value": "primary_user", "label": "Мой основной ПК"},
                    {"value": "shared_user", "label": "Общий ПК"},
                    {"value": "temporary_user", "label": "Временное рабочее место"},
                ],
            },
            {
                "key": "is_shared_device",
                "label": "Это общий ПК",
                "type": "checkbox",
                "placeholder": "Да",
                "visible_when": {"field": "relationship_type", "equals": "shared_user"},
            },
        ],
    }


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
        self._remote_assist_threads: Dict[str, QThread] = {}
        self._remote_assist_banners: Dict[str, QWidget] = {}
        self._remote_assist_banner_labels: Dict[str, QLabel] = {}
        self._remote_assist_modes: Dict[str, str] = {}
        self._remote_assist_dialogs: Dict[str, RemoteAssistConsentDialog] = {}
        self._user_consent_dialogs: Dict[str, UserConsentPromptDialog] = {}
        self._user_consent_refreshing: bool = False
        
        # Текущий job_id активного чата (для привязки consent к чату)
        # session_key == текущий chat job_id, полученный из /api/chat_start
        self.current_chat_job_id: Optional[str] = None
        self._settings_form_loaded: bool = False
        self._settings_snapshot: Optional[Dict[str, Any]] = None
        self._bridge_connected: bool = False
        self._server_connection_state: str = "starting"
        self._server_connection_detail: str = ""
        self._runtime_logs_dir: Optional[str] = None
        self._update_status_snapshot: Dict[str, Any] = {}
        self._runtime_status_refresh_in_flight: bool = False
        self._sidebar_expanded: bool = True
        self._sidebar_content_width: int = 296
        self._active_sidebar_view: str = "tickets"
        self._theme_combo_sync_in_progress: bool = False
        self._settings_sections: list[QFrame] = []
        self._settings_section_titles: list[QLabel] = []
        self._settings_section_subtitles: list[QLabel] = []
        self._account_session_manager = AccountSessionManager()
        self._account_session: dict[str, Any] = self._account_session_manager.load()
        self._account_state: dict[str, Any] = {}
        self._pending_initial_account_state_refresh: bool = False
        self._account_entry_mode: bool = False

        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self._resize_handler: Optional[FramelessResizeHandler] = None
        
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

    def _apply_soft_shadow(self, widget: QWidget, *, blur: int = 24, alpha: int = 28, y: int = 8) -> None:
        if not gui_soft_shadows_enabled():
            return
        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur)
        effect.setOffset(0, y)
        effect.setColor(QColor(0, 0, 0, alpha))
        widget.setGraphicsEffect(effect)
    
    def _setup_ui(self):
        """Настройка UI главного окна."""
        set_uia_metadata(
            self,
            object_name="agent.main_window",
            name=f"Maria Agent v{AGENT_VERSION}",
            description=f"id=agent.main_window; agent_version={AGENT_VERSION}",
        )
        central_widget = QWidget()
        central_widget.setObjectName("AgentRoot")
        set_uia_metadata(
            central_widget,
            name="agent.root",
            description=f"id=agent.root; agent_version={AGENT_VERSION}",
        )
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet(theme.main_window_stylesheet())

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self)
        self.title_bar.minimizeRequested.connect(self.showMinimized)
        self.title_bar.maximizeRestoreRequested.connect(self._toggle_window_maximized)
        self.title_bar.closeRequested.connect(self.close)
        layout.addWidget(self.title_bar, 0)

        content_widget = QWidget()
        content_widget.setObjectName("AgentContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(0)

        self.title_label = QLabel(f"Maria Agent v{AGENT_VERSION}")
        self.title_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {theme.TEXT_SECONDARY}; background: transparent;"
        )
        self.title_label.hide()

        self.chat_panel = ChatPanel(
            base_url=None,
            auth_token=self.auth_token,
            account_session_provider=self._active_account_session_for_tickets,
        )
        self.profile_sidebar = ProfileSidebarWidget(self.chat_panel)
        self.profile_sidebar.setMinimumWidth(0)
        self.profile_sidebar.setMaximumWidth(16777215)
        self.tickets_sidebar = TicketsSidebarWidget(self.chat_panel)
        self.tickets_sidebar.setMinimumWidth(0)
        self.tickets_sidebar.setMaximumWidth(16777215)
        self.ticket_create_page = TicketCreateWizardWidget(self.chat_panel)
        self.ticket_create_page.ticketCreated.connect(self._on_ticket_created_from_wizard)
        self.ticket_create_page.cancelled.connect(lambda: self._select_sidebar_view("tickets", expand=True))
        self.chat_panel.ticketFormPackChanged.connect(lambda _pack: self.ticket_create_page.refresh_from_panel())
        self.chat_panel.serviceCatalogChanged.connect(lambda _catalog: self.ticket_create_page.refresh_from_panel())
        self.chat_panel.accountSessionError.connect(self.handle_account_session_error)
        self.chat_panel.set_profile_sidebar(self.profile_sidebar)
        self.chat_panel.set_tickets_sidebar(self.tickets_sidebar)
        self.account_gate_page = AccountGateWidget()
        self.account_gate_page.browserLoginRequested.connect(self._on_browser_login_requested)
        self.account_gate_page.browserRegisterRequested.connect(self._on_browser_register_requested)
        self.account_gate_page.loginConfirmedRequested.connect(self._on_account_login_confirmed)
        self.account_gate_page.loginOtherRequested.connect(self._on_account_login_other)
        self.account_gate_page.registerRequested.connect(self._on_account_register_requested)
        self.account_gate_page.confirmRegistrationRequested.connect(self._on_confirm_registration_claim_clicked)
        self.account_gate_page.refreshRequested.connect(self._refresh_account_state)
        self.account_gate_page.settingsRequested.connect(self._show_settings_dialog)
        self.account_gate_page.checkOtherLoginRequestRequested.connect(self._on_check_other_login_request)
        if legacy_agent_registration_enabled():
            self.registration_entry_page = self._build_registration_entry_page()
        else:
            self.registration_entry_page = self._build_legacy_registration_disabled_page()
        self.account_page = self._build_account_page()

        self.body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.body_splitter.setChildrenCollapsible(False)
        self._sidebar_collapsed_width = 84

        self.sidebar_shell = QFrame()
        self.sidebar_shell.setObjectName("Sidebar")
        self.sidebar_shell.setStyleSheet(theme.main_window_stylesheet())
        sidebar_shell_layout = QVBoxLayout(self.sidebar_shell)
        sidebar_shell_layout.setContentsMargins(16, 18, 16, 18)
        sidebar_shell_layout.setSpacing(12)
        self.sidebar_shell_layout = sidebar_shell_layout

        sidebar_header = QHBoxLayout()
        sidebar_header.setContentsMargins(0, 0, 0, 0)
        sidebar_header.setSpacing(12)
        self.sidebar_logo_label = QLabel()
        self.sidebar_logo_label.setFixedSize(44, 44)
        self.sidebar_logo_label.setScaledContents(True)
        if theme.LOGO_PATH.exists():
            self.sidebar_logo_label.setPixmap(
                QPixmap(str(theme.LOGO_PATH)).scaled(
                    44,
                    44,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self.sidebar_logo_label.setStyleSheet("background: transparent; border: none;")
        sidebar_header.addWidget(self.sidebar_logo_label, 0, Qt.AlignmentFlag.AlignTop)
        self.sidebar_toggle_btn = QToolButton()
        self.sidebar_toggle_btn.setObjectName("SecondaryButton")
        self.sidebar_toggle_btn.setText("☰")
        self.sidebar_toggle_btn.setToolTip("Свернуть или развернуть навигацию")
        self.sidebar_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_toggle_btn.clicked.connect(self._toggle_sidebar_expanded)
        self.sidebar_toggle_btn.show()

        sidebar_header.addStretch(1)
        sidebar_header.addWidget(self.sidebar_toggle_btn, 0, Qt.AlignmentFlag.AlignTop)
        sidebar_shell_layout.addLayout(sidebar_header)

        self.sidebar_nav_label = QLabel("Навигация")
        self.sidebar_nav_label.setObjectName("SidebarSectionLabel")
        sidebar_shell_layout.addSpacing(18)
        sidebar_shell_layout.addWidget(self.sidebar_nav_label)

        self.sidebar_dashboard_btn = QPushButton()
        self.sidebar_dashboard_btn.setObjectName("SidebarButton")
        self.sidebar_dashboard_btn.setCheckable(True)
        self.sidebar_dashboard_btn.setIcon(QIcon(theme.icon_path("dashboard")))
        self.sidebar_dashboard_btn.setIconSize(QSize(22, 22))
        self.sidebar_dashboard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_dashboard_btn.clicked.connect(lambda: self._select_sidebar_view("dashboard", expand=True))
        sidebar_shell_layout.addWidget(self.sidebar_dashboard_btn)

        self.sidebar_create_ticket_btn = QPushButton()
        self.sidebar_create_ticket_btn.setObjectName("SidebarCreateButton")
        self.sidebar_create_ticket_btn.setIcon(QIcon(theme.icon_path("plus")))
        self.sidebar_create_ticket_btn.setIconSize(QSize(22, 22))
        self.sidebar_create_ticket_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_create_ticket_btn.clicked.connect(self._on_create_ticket_from_menu)
        sidebar_shell_layout.addWidget(self.sidebar_create_ticket_btn)

        self.sidebar_tickets_btn = QPushButton()
        self.sidebar_tickets_btn.setObjectName("SidebarButton")
        self.sidebar_tickets_btn.setCheckable(True)
        self.sidebar_tickets_btn.setIcon(QIcon(theme.icon_path("ticket")))
        self.sidebar_tickets_btn.setIconSize(QSize(22, 22))
        self.sidebar_tickets_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_tickets_btn.clicked.connect(lambda: self._select_sidebar_view("tickets", expand=True))
        sidebar_shell_layout.addWidget(self.sidebar_tickets_btn)

        self.sidebar_settings_btn = QPushButton()
        self.sidebar_settings_btn.setObjectName("SidebarButton")
        self.sidebar_settings_btn.setCheckable(True)
        self.sidebar_settings_btn.setIcon(QIcon(theme.icon_path("settings")))
        self.sidebar_settings_btn.setIconSize(QSize(22, 22))
        self.sidebar_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_settings_btn.clicked.connect(self._show_settings_dialog)
        sidebar_shell_layout.addWidget(self.sidebar_settings_btn)
        sidebar_shell_layout.addStretch(1)

        self.sidebar_profile_card = QFrame()
        self.sidebar_profile_card.setObjectName("ProfileCard")
        set_uia_metadata(
            self.sidebar_profile_card,
            name="agent.account.summary",
            description=account_description(None),
        )
        self.sidebar_profile_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_profile_card.mousePressEvent = lambda _event: self._select_sidebar_view("profile", expand=True)
        profile_card_layout = QHBoxLayout(self.sidebar_profile_card)
        profile_card_layout.setContentsMargins(14, 14, 12, 14)
        profile_card_layout.setSpacing(12)
        self.sidebar_avatar_label = QLabel("AD")
        self.sidebar_avatar_label.setObjectName("Avatar")
        self.sidebar_avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_avatar_label.setFixedSize(48, 48)
        profile_card_layout.addWidget(self.sidebar_avatar_label)
        profile_text_layout = QVBoxLayout()
        profile_text_layout.setContentsMargins(0, 0, 0, 0)
        profile_text_layout.setSpacing(2)
        self.sidebar_profile_kicker = QLabel("Аккаунт")
        self.sidebar_profile_kicker.setObjectName("CardKicker")
        self.sidebar_profile_name_label = QLabel("Без профиля")
        self.sidebar_profile_name_label.setObjectName("CardTitle")
        set_uia_metadata(self.sidebar_profile_name_label, name="agent.account.person", description="id=agent.account.person")
        self.sidebar_profile_meta_label = QLabel(self.chat_panel.user_display_name)
        self.sidebar_profile_meta_label.setObjectName("CardMeta")
        set_uia_metadata(self.sidebar_profile_meta_label, name="agent.account.mode", description="id=agent.account.mode")
        profile_text_layout.addWidget(self.sidebar_profile_kicker)
        profile_text_layout.addWidget(self.sidebar_profile_name_label)
        profile_text_layout.addWidget(self.sidebar_profile_meta_label)
        profile_card_layout.addLayout(profile_text_layout, 1)
        self.sidebar_profile_chevron = QLabel("›")
        self.sidebar_profile_chevron.setObjectName("CardMeta")
        self.sidebar_profile_chevron.setStyleSheet("font-size: 24px; background: transparent;")
        profile_card_layout.addWidget(self.sidebar_profile_chevron)
        sidebar_shell_layout.addWidget(self.sidebar_profile_card)

        self.dashboard_page = self._build_dashboard_page()

        self.main_content_stack = QStackedWidget()
        self.main_content_stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")
        self.main_content_stack.addWidget(self.account_gate_page)
        self.main_content_stack.addWidget(self.registration_entry_page)
        self.main_content_stack.addWidget(self.dashboard_page)
        self.main_content_stack.addWidget(self.tickets_sidebar)
        self.main_content_stack.addWidget(self.chat_panel)
        self.main_content_stack.addWidget(self.account_page)
        self.main_content_stack.addWidget(self.ticket_create_page)

        self.body_splitter.addWidget(self.sidebar_shell)
        self.body_splitter.addWidget(self.main_content_stack)
        self.body_splitter.setStretchFactor(0, 0)
        self.body_splitter.setStretchFactor(1, 1)
        self.body_splitter.setSizes([300, 1000])

        content_layout.addWidget(self.body_splitter, 1)
        self.security_footer = QFrame()
        self.security_footer.setObjectName("SecurityFooter")
        security_footer_layout = QHBoxLayout(self.security_footer)
        security_footer_layout.setContentsMargins(12, 8, 12, 0)
        security_footer_layout.setSpacing(8)
        security_footer_layout.addStretch(1)
        self.security_footer_icon = QLabel("▣")
        self.security_footer_icon.setObjectName("SecurityFooterIcon")
        self.security_footer_text = QLabel(
            "Ваше соединение защищено. Все данные передаются в зашифрованном виде."
        )
        self.security_footer_text.setObjectName("SecurityFooterText")
        security_footer_layout.addWidget(self.security_footer_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        security_footer_layout.addWidget(self.security_footer_text, 0, Qt.AlignmentFlag.AlignVCenter)
        security_footer_layout.addStretch(1)
        content_layout.addWidget(self.security_footer, 0)
        layout.addWidget(content_widget, 1)
        self._resize_handler = FramelessResizeHandler(self)
        self.chat_panel.chatSessionChanged.connect(self._on_chat_session_changed)
        self.chat_panel.requesterProfileChanged.connect(self._render_profile_status)
        self.chat_panel.listNavigationVisibilityChanged.connect(self._on_list_navigation_visibility_changed)
        self.chat_panel.ticketsListChanged.connect(self._refresh_dashboard)
        self._render_profile_status()
        self._refresh_dashboard()
        self._select_sidebar_view("account_gate", expand=True)
        self._pending_initial_account_state_refresh = True

        self.settings_page = QWidget()
        self.settings_page.setObjectName("AgentSettingsPage")
        self.settings_page.setMinimumWidth(520)
        settings_page_root = QVBoxLayout(self.settings_page)
        settings_page_root.setContentsMargins(8, 8, 8, 8)
        settings_page_root.setSpacing(8)

        settings_header_row = QHBoxLayout()
        settings_header_row.setContentsMargins(0, 0, 0, 0)
        settings_header_row.setSpacing(8)
        self.settings_header = QLabel("Настройки")
        self._settings_default_header_text = "Настройки"
        self.settings_header.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {theme.TEXT_PRIMARY}; background: transparent; padding: 4px 6px;"
        )
        settings_header_row.addWidget(self.settings_header, 1)
        self.settings_back_btn = QPushButton("Назад")
        self.settings_back_btn.setObjectName("SecondaryButton")
        self.settings_back_btn.clicked.connect(self._show_account_gate_entry)
        self.settings_back_btn.hide()
        settings_header_row.addWidget(self.settings_back_btn, 0)
        settings_page_root.addLayout(settings_header_row)
        self.settings_subtitle = QLabel(
            "Параметры сгруппированы по смыслу: сначала подключение, затем интерфейс, диагностика и локальные данные."
        )
        self._settings_default_subtitle_text = self.settings_subtitle.text()
        self.settings_subtitle.setWordWrap(True)
        self.settings_subtitle.setStyleSheet(
            f"font-size: 11px; color: {theme.TEXT_MUTED}; background: transparent; padding: 0 6px 4px 6px;"
        )
        settings_page_root.addWidget(self.settings_subtitle)

        scroll = QScrollArea(self.settings_page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        settings_layout = QVBoxLayout(scroll_content)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        settings_layout.setSpacing(14)

        def create_settings_section(title: str, subtitle: str) -> tuple[QFrame, QVBoxLayout]:
            section = QFrame()
            section.setStyleSheet(
                f"QFrame {{ background: {theme.BG_CARD_ALT}; border: 1px solid {theme.BORDER_SOFT}; border-radius: 22px; }}"
            )
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(18, 18, 18, 18)
            section_layout.setSpacing(12)
            title_label = QLabel(title)
            title_label.setStyleSheet(
                f"font-size: 15px; font-weight: 700; color: {theme.TEXT_PRIMARY}; background: transparent;"
            )
            subtitle_label = QLabel(subtitle)
            subtitle_label.setWordWrap(True)
            subtitle_label.setStyleSheet(
                f"font-size: 11px; color: {theme.TEXT_MUTED}; background: transparent;"
            )
            section_layout.addWidget(title_label)
            section_layout.addWidget(subtitle_label)
            self._settings_sections.append(section)
            self._settings_section_titles.append(title_label)
            self._settings_section_subtitles.append(subtitle_label)
            return section, section_layout

        identity_section, identity_section_layout = create_settings_section(
            "Устройство и хранение",
            "Параметры этого экземпляра агента: идентификатор, путь к рабочему конфигу и локальное хранилище.",
        )
        self.identity_settings_section = identity_section
        connection_section, connection_section_layout = create_settings_section(
            "Подключение",
            "Адреса сервера и токен доступа. Здесь всё, что влияет на соединение агента с backend.",
        )
        interface_section, interface_section_layout = create_settings_section(
            "Интерфейс",
            "Настройки окна, tray и локального UI-моста, через который GUI разговаривает с работающим агентом.",
        )
        diagnostics_section, diagnostics_section_layout = create_settings_section(
            "Диагностика и логи",
            "Логирование, статус always-on runtime и быстрый доступ к журналам без выхода из окна.",
        )
        modules_section, modules_section_layout = create_settings_section(
            "Модули и безопасность",
            "Что агент загружает локально, где хранит данные и какие расширенные возможности разрешены.",
        )

        device_group = QGroupBox("Информация об устройстве")
        self.device_settings_group = device_group
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
        identity_section_layout.addWidget(device_group)

        server_group = QGroupBox("Адреса сервера")
        server_form = QFormLayout(server_group)
        self.api_url_input = QLineEdit()
        self.ws_url_input = QLineEdit()
        self.reconnect_spin = QSpinBox()
        self.reconnect_spin.setRange(1, 3600)
        self.reconnect_spin.setValue(5)
        server_form.addRow("API URL:", self.api_url_input)
        server_form.addRow("WS URL:", self.ws_url_input)
        server_form.addRow("Интервал reconnect (с):", self.reconnect_spin)
        connection_section_layout.addWidget(server_group)

        ui_bridge_group = QGroupBox("Локальный UI-мост")
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
        interface_section_layout.addWidget(ui_bridge_group)

        appearance_group = QGroupBox("Внешний вид")
        appearance_form = QFormLayout(appearance_group)
        appearance_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.theme_mode_combo = QComboBox()
        self.theme_mode_combo.addItem("Светлая", "light")
        self.theme_mode_combo.addItem("Тёмная", "dark")
        appearance_form.addRow("Тема интерфейса:", self.theme_mode_combo)
        interface_section_layout.addWidget(appearance_group)

        tray_group = QGroupBox("Окно и tray")
        tray_outer = QVBoxLayout(tray_group)
        tray_form = QFormLayout()
        tray_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.ui_tray_enabled_checkbox = QCheckBox("Включить tray")
        self.ui_minimize_to_tray_checkbox = QCheckBox("Закрытие окна сворачивает в tray")
        self.ui_start_hidden_checkbox = QCheckBox("Запускать окно скрытым в tray")
        self.ui_notifications_checkbox = QCheckBox("Показывать tray-уведомления")
        tray_form.addRow("", self.ui_tray_enabled_checkbox)
        tray_form.addRow("", self.ui_minimize_to_tray_checkbox)
        tray_form.addRow("", self.ui_start_hidden_checkbox)
        tray_form.addRow("", self.ui_notifications_checkbox)
        tray_outer.addLayout(tray_form)
        interface_section_layout.addWidget(tray_group)

        logging_group = QGroupBox("Логи и состояние runtime")
        logging_outer = QVBoxLayout(logging_group)
        logging_form = QFormLayout()
        logging_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.logging_level_combo = QComboBox()
        self.logging_console_level_combo = QComboBox()
        for level_name in ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]:
            self.logging_level_combo.addItem(level_name)
            self.logging_console_level_combo.addItem(level_name)
        self.logging_rotation_input = QLineEdit()
        self.logging_retention_input = QLineEdit()
        self.logging_compression_input = QLineEdit()
        logging_form.addRow("Уровень файла:", self.logging_level_combo)
        logging_form.addRow("Уровень консоли:", self.logging_console_level_combo)
        logging_form.addRow("Rotation:", self.logging_rotation_input)
        logging_form.addRow("Retention:", self.logging_retention_input)
        logging_form.addRow("Compression:", self.logging_compression_input)
        logging_outer.addLayout(logging_form)
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
        logging_outer.addLayout(diagnostics_actions)
        self.runtime_status_label = QLabel("Диагностика ещё не загружена.")
        self.runtime_status_label.setWordWrap(True)
        self.runtime_status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.runtime_status_label.setStyleSheet(
            f"padding: 8px; background: {theme.BG_INPUT}; border: 1px solid {theme.BORDER}; "
            f"border-radius: 10px; color: {theme.TEXT_SECONDARY};"
        )
        logging_outer.addWidget(self.runtime_status_label)
        self.runtime_logs_view = QPlainTextEdit()
        self.runtime_logs_view.setReadOnly(True)
        self.runtime_logs_view.setMinimumHeight(180)
        self.runtime_logs_view.setPlaceholderText("Последние строки agent.log появятся здесь.")
        logging_outer.addWidget(self.runtime_logs_view)
        diagnostics_section_layout.addWidget(logging_group)

        paths_group = QGroupBox("Локальные папки")
        paths_form = QFormLayout(paths_group)
        self.data_dir_input = QLineEdit()
        paths_form.addRow("data_dir:", self.data_dir_input)
        identity_section_layout.addWidget(paths_group)

        modules_group = QGroupBox("Модули и безопасность")
        modules_form = QFormLayout(modules_group)
        self.enabled_modules_input = QLineEdit()
        self.enabled_modules_input.setPlaceholderText("system, screen, diag_logs, inventory, presence")
        self.core_modules_label = QLabel("system, screen, diag_logs, inventory, presence")
        self.core_modules_label.setWordWrap(True)
        self.core_modules_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.core_modules_label.setStyleSheet(
            f"font-family: Consolas, 'Courier New', monospace; font-size: 11px; padding: 8px; "
            f"background: {theme.BG_INPUT}; border: 1px solid {theme.BORDER}; border-radius: 10px; "
            f"color: {theme.TEXT_SECONDARY};"
        )
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
        modules_form.addRow("Всегда включены:", self.core_modules_label)
        self.enabled_modules_hint = QLabel(
            "В списке — встроенные модули, которые агент загружает при старте. "
            "«system», «screen», «diag_logs», «inventory» и «presence» всегда добавляются автоматически (их нельзя отключить через YAML). "
            "Остальные имена подключаются только если они есть в образе агента; "
            "пакеты из modules_store обрабатываются отдельно (см. установленные модули ниже)."
        )
        self.enabled_modules_hint.setWordWrap(True)
        self.enabled_modules_hint.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        modules_form.addRow(self.enabled_modules_hint)
        modules_form.addRow("", self.allow_remote_code_checkbox)
        modules_form.addRow("Установленные модули:", self.installed_modules_label)
        modules_section_layout.addWidget(modules_group)

        auth_group = QGroupBox("Доступ и токен")
        auth_form = QFormLayout(auth_group)
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Введите новый токен (или оставьте пустым)")
        self.clear_token_checkbox = QCheckBox("Очистить токен")
        self.token_hint_label = QLabel("Текущий токен: —")
        self.token_hint_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; background: transparent;")
        auth_form.addRow("Новый токен:", self.token_input)
        auth_form.addRow("", self.clear_token_checkbox)
        auth_form.addRow("", self.token_hint_label)
        connection_section_layout.addWidget(auth_group)

        settings_layout.addWidget(identity_section)
        settings_layout.addWidget(connection_section)
        settings_layout.addWidget(interface_section)
        settings_layout.addWidget(diagnostics_section)
        settings_layout.addWidget(modules_section)

        self.settings_status_label = QLabel("")
        self.settings_status_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; background: transparent;")
        settings_layout.addWidget(self.settings_status_label)

        scroll.setWidget(scroll_content)
        settings_page_root.addWidget(scroll, 1)

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
        settings_page_root.addLayout(buttons_layout)

        theme.apply_agent_dialog_theme(self.settings_page)
        self.main_content_stack.addWidget(self.settings_page)
        if self._pending_initial_account_state_refresh:
            self._pending_initial_account_state_refresh = False
            self._refresh_account_state()

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
        self.theme_mode_combo.currentIndexChanged.connect(self._on_theme_mode_changed)
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
        self.status_bar.hide()
        self.footer_status_block = QFrame()
        self.footer_status_block.setObjectName("AgentStatusCard")
        self.footer_status_block.setStyleSheet(
            f"QFrame#AgentStatusCard {{ background: {theme.current_palette().footer_block_bg}; "
            f"border: 1px solid {theme.current_palette().footer_block_border}; border-radius: 16px; }}"
        )
        footer_layout = QHBoxLayout(self.footer_status_block)
        footer_layout.setContentsMargins(14, 12, 10, 12)
        footer_layout.setSpacing(10)
        self.connection_status_dot = QLabel()
        self.connection_status_dot.setObjectName("StatusDot")
        footer_layout.addWidget(self.connection_status_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self.connection_status_btn = QPushButton("Офлайн")
        set_uia_metadata(
            self.connection_status_btn,
            name="agent.connection.state",
            description=connection_description(
                bridge_connected=self._bridge_connected,
                server_state=self._server_connection_state,
                detail=self._server_connection_detail,
            ),
        )
        self.connection_status_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connection_status_btn.clicked.connect(self._show_settings_dialog)
        self.connection_status_btn.hide()
        self.agent_footer_label = QLabel(f"Агент v{AGENT_VERSION}")
        self.agent_footer_label.setStyleSheet(
            f"color: {theme.current_palette().footer_label}; font-weight: 700; background: transparent;"
        )
        self.agent_footer_meta = QLabel("Подключение и версия")
        set_uia_metadata(
            self.agent_footer_meta,
            name="agent.connection.detail",
            description="id=agent.connection.detail; connection_state=disconnected",
        )
        self.agent_footer_meta.setStyleSheet(
            f"color: {theme.current_palette().footer_label_muted}; background: transparent;"
        )
        footer_texts = QVBoxLayout()
        footer_texts.setContentsMargins(0, 0, 0, 0)
        footer_texts.setSpacing(0)
        footer_texts.addWidget(self.agent_footer_label)
        footer_texts.addWidget(self.agent_footer_meta)
        self.update_agent_btn = QPushButton("")
        self.update_agent_btn.setObjectName("SecondaryButton")
        self.update_agent_btn.setIcon(QIcon(theme.icon_path("download")))
        self.update_agent_btn.setIconSize(QSize(18, 18))
        self.update_agent_btn.setFixedSize(42, 42)
        self.update_agent_btn.setToolTip("Обновить агент")
        self.update_agent_btn.clicked.connect(self._on_trigger_update_clicked)
        self.update_agent_btn.hide()
        footer_layout.addLayout(footer_texts, 1)
        footer_layout.addWidget(self.update_agent_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.sidebar_shell_layout.addWidget(self.footer_status_block)
        self._apply_soft_shadow(self.sidebar_shell, blur=30, alpha=34, y=10)
        self._apply_soft_shadow(self.tickets_sidebar, blur=28, alpha=24, y=8)

        self._repair_widget_texts(self)
        self._repair_widget_texts(self.settings_page)
        self._add_log("GUI запущен", "info")
        self._load_device_uuid()
        self._preview_theme_mode(theme.current_theme_mode())
        self._render_update_status()
        self._runtime_refresh_timer = QTimer(self)
        self._runtime_refresh_timer.setInterval(15000)
        self._runtime_refresh_timer.timeout.connect(lambda: self._queue_runtime_status_refresh(update_panel=False))
        self._runtime_refresh_timer.start()
        self._user_consent_timer = QTimer(self)
        self._user_consent_timer.setInterval(10000)
        self._user_consent_timer.timeout.connect(self._refresh_user_consents)
        self._user_consent_timer.start()
        QTimer.singleShot(250, lambda: asyncio.create_task(self._async_refresh_runtime_snapshot(update_panel=False)))
        QTimer.singleShot(1000, self._refresh_user_consents)

    def _on_list_navigation_visibility_changed(self, list_mode: bool) -> None:
        """Возвращаем пользователя к панели тикетов, когда чат просит список."""
        if list_mode:
            self._select_sidebar_view("tickets", expand=True)
        else:
            self._select_sidebar_view("ticket", expand=False)
            self._set_sidebar_expanded(False)

    def _set_sidebar_expanded(self, expanded: bool) -> None:
        self._sidebar_expanded = expanded
        target_width = self._sidebar_content_width if expanded else self._sidebar_collapsed_width
        self.sidebar_shell.setMinimumWidth(target_width)
        self.sidebar_shell.setMaximumWidth(target_width)
        if expanded:
            self.sidebar_shell_layout.setContentsMargins(16, 18, 16, 18)
            self.sidebar_toggle_btn.setText("‹")
            self.sidebar_toggle_btn.setToolTip("Свернуть навигацию")
        else:
            self.sidebar_shell_layout.setContentsMargins(10, 18, 10, 18)
            self.sidebar_toggle_btn.setText("☰")
            self.sidebar_toggle_btn.setToolTip("Развернуть навигацию")
        self.sidebar_nav_label.setVisible(expanded)
        self.sidebar_logo_label.setVisible(expanded)
        self.sidebar_profile_card.setVisible(expanded)
        if hasattr(self, "footer_status_block"):
            self.footer_status_block.setVisible(expanded)
        sizes = self.body_splitter.sizes()
        total = sum(sizes) if sizes else self.width()
        chat_width = max(640, total - target_width - 12)
        self.body_splitter.setSizes([target_width, chat_width])
        self._refresh_sidebar_labels()

    def _toggle_sidebar_expanded(self) -> None:
        self._set_sidebar_expanded(not self._sidebar_expanded)

    def _toggle_window_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._sync_title_bar_window_state()

    def _sync_title_bar_window_state(self) -> None:
        if hasattr(self, "title_bar"):
            self.title_bar.set_maximized(self.isMaximized())

    def changeEvent(self, event):  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._sync_title_bar_window_state()

    def _build_dashboard_page(self) -> QFrame:
        page = QFrame()
        page.setObjectName("MainPanel")
        page.setStyleSheet(theme.main_window_stylesheet())
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        title = QLabel("Рабочий стол")
        title.setObjectName("MainTitle")
        layout.addWidget(title)

        subtitle = QLabel("Краткая сводка агента по текущим обращениям и аккаунту.")
        subtitle.setObjectName("MainSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(14)
        total_card, self.dashboard_total_value = self._make_dashboard_metric("Все обращения", "0")
        open_card, self.dashboard_open_value = self._make_dashboard_metric("Открытые", "0")
        closed_card, self.dashboard_closed_value = self._make_dashboard_metric("Закрытые", "0")
        metrics_row.addWidget(total_card)
        metrics_row.addWidget(open_card)
        metrics_row.addWidget(closed_card)
        layout.addLayout(metrics_row)

        detail_row = QHBoxLayout()
        detail_row.setSpacing(14)
        profile_card, self.dashboard_profile_value = self._make_dashboard_metric("Аккаунт", "Аккаунт не выбран")
        status_card, self.dashboard_status_value = self._make_dashboard_metric("Статус агента", "Релиз актуален")
        detail_row.addWidget(profile_card)
        detail_row.addWidget(status_card)
        layout.addLayout(detail_row)

        actions_row = QHBoxLayout()
        actions_row.addStretch(1)
        dashboard_tickets_btn = QPushButton("  Перейти к обращениям")
        dashboard_tickets_btn.setObjectName("SecondaryButton")
        dashboard_tickets_btn.setIcon(QIcon(theme.icon_path("ticket")))
        dashboard_tickets_btn.setIconSize(QSize(20, 20))
        dashboard_tickets_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dashboard_tickets_btn.clicked.connect(lambda: self._select_sidebar_view("tickets", expand=True))
        actions_row.addWidget(dashboard_tickets_btn)

        dashboard_create_btn = QPushButton("  Создать обращение")
        dashboard_create_btn.setObjectName("PrimaryButton")
        dashboard_create_btn.setIcon(QIcon(theme.icon_path("plus")))
        dashboard_create_btn.setIconSize(QSize(20, 20))
        dashboard_create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dashboard_create_btn.clicked.connect(self._on_create_ticket_from_menu)
        actions_row.addWidget(dashboard_create_btn)
        layout.addLayout(actions_row)
        layout.addStretch(1)
        return page

    def _make_dashboard_metric(self, title: str, value: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("ProfileCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("CardKicker")
        value_label = QLabel(value)
        value_label.setObjectName("CardTitle")
        value_label.setWordWrap(True)
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        return card, value_label

    def _refresh_dashboard(self) -> None:
        if not hasattr(self, "dashboard_total_value"):
            return
        tickets = [row.get("ticket", row) for row in self.chat_panel.tickets_cache]
        closed_count = sum(1 for ticket in tickets if str(ticket.get("status") or "").strip().lower() == "closed")
        total_count = len(tickets)
        open_count = total_count - closed_count
        self.dashboard_total_value.setText(str(total_count))
        self.dashboard_open_value.setText(str(open_count))
        self.dashboard_closed_value.setText(str(closed_count))
        self.dashboard_profile_value.setText(self._account_summary())
        status_text = self.agent_footer_meta.text() if hasattr(self, "agent_footer_meta") else "Релиз актуален"
        self.dashboard_status_value.setText(status_text)

    def _active_account_session_for_tickets(self) -> Optional[dict]:
        if self._account_session.get("account_mode") in {"confirmed_binding", "verified_other_account"}:
            return self._account_session
        return None

    def _refresh_user_consents(self) -> None:
        if not self.auth_token:
            return
        if not self._active_account_session_for_tickets():
            self._close_user_consent_dialogs()
            return
        self._spawn_gui_task(self._async_refresh_user_consents(), name="user_consent.refresh")

    async def _async_refresh_user_consents(self) -> None:
        if self._user_consent_refreshing:
            return
        session = self._active_account_session_for_tickets()
        if not session:
            self._close_user_consent_dialogs()
            return
        self._user_consent_refreshing = True
        try:
            payload = await self.chat_panel.ticket_client.list_user_consents(
                account_session=session,
                statuses=["pending"],
            )
            if isinstance(payload, dict) and payload.get("status") == "error":
                self.handle_account_session_error(payload)
                logger.debug(f"[user_consent] refresh failed: {payload}")
                return
            consents = payload.get("consents") if isinstance(payload, dict) else []
            if not isinstance(consents, list):
                consents = []
            pending_ids = {
                str(consent.get("consent_id"))
                for consent in consents
                if isinstance(consent, dict) and str(consent.get("status") or "") == "pending"
            }
            for consent_id, dialog in list(self._user_consent_dialogs.items()):
                if consent_id not in pending_ids:
                    dialog.close()
                    self._user_consent_dialogs.pop(consent_id, None)
                    self.open_dialogs.discard(f"user_consent:{consent_id}")
            for consent in consents:
                if isinstance(consent, dict) and str(consent.get("status") or "") == "pending":
                    self._show_user_consent_dialog(consent)
        finally:
            self._user_consent_refreshing = False

    def _close_user_consent_dialogs(self) -> None:
        for consent_id, dialog in list(self._user_consent_dialogs.items()):
            dialog.close()
            self._user_consent_dialogs.pop(consent_id, None)
            self.open_dialogs.discard(f"user_consent:{consent_id}")

    def _show_user_consent_dialog(self, consent: dict) -> None:
        consent_id = str(consent.get("consent_id") or "").strip()
        if not consent_id:
            return
        dialog_key = f"user_consent:{consent_id}"
        if dialog_key in self.open_dialogs:
            return
        self.open_dialogs.add(dialog_key)
        dialog = UserConsentPromptDialog(consent, self)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self._user_consent_dialogs[consent_id] = dialog

        def cleanup() -> None:
            self.open_dialogs.discard(dialog_key)
            self._user_consent_dialogs.pop(consent_id, None)

        def approve() -> None:
            self._spawn_gui_task(
                self._post_user_consent_decision(consent_id, approve=True),
                name="user_consent.approve",
            )

        def deny() -> None:
            self._spawn_gui_task(
                self._post_user_consent_decision(consent_id, approve=False),
                name="user_consent.deny",
            )

        dialog.approved.connect(approve)
        dialog.denied.connect(deny)
        dialog.finished.connect(lambda _result: cleanup())
        dialog.open()
        dialog.raise_()
        dialog.activateWindow()

    async def _post_user_consent_decision(self, consent_id: str, *, approve: bool) -> None:
        session = self._active_account_session_for_tickets()
        if not session:
            self._add_log("user_consent | account session missing", "error")
            return
        decision = "approved" if approve else "denied"
        payload = await self.chat_panel.ticket_client.decide_user_consent(
            consent_id,
            decision,
            account_session=session,
            reason=None if approve else "user_denied",
        )
        if isinstance(payload, dict) and payload.get("status") == "error":
            self.handle_account_session_error(payload)
            self._add_log(f"user_consent | {decision} failed | {payload.get('error_code') or payload.get('error')}", "error")
            return
        self._add_log("Согласие подтверждено" if approve else "Согласие отклонено", "success" if approve else "warning")
        await self._async_refresh_user_consents()

    def _account_summary(self) -> str:
        session = self._active_account_session_for_tickets()
        if not session:
            return "Аккаунт не выбран"
        label = {
            "confirmed_binding": "Подтвержденный аккаунт",
            "registration_pending": "Регистрация ожидает подтверждения",
            "verified_other_account": "Другой аккаунт",
        }.get(str(session.get("account_mode")), "Аккаунт")
        name = session.get("display_name") or session.get("full_name") or session.get("login") or "Без имени"
        return f"{name} | {label}"

    def _refresh_account_state(self) -> None:
        if not hasattr(self, "account_gate_page"):
            return
        self.account_gate_page.render_loading()
        self._spawn_gui_task(self._async_refresh_account_state(), name="account.refresh_state")

    def _build_account_page(self) -> QWidget:
        page = QFrame()
        page.setObjectName("MainPanel")
        page.setStyleSheet(theme.main_window_stylesheet())
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Аккаунт")
        title.setObjectName("MainTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Текущий аккаунт обращения выдан сервером для этого устройства. "
            "Локальные старые профили не используются для входа и не могут заменить выбранный аккаунт."
        )
        subtitle.setObjectName("MainSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.account_page_warning_label = QLabel("")
        self.account_page_warning_label.setObjectName("ProfileHint")
        self.account_page_warning_label.setWordWrap(True)
        layout.addWidget(self.account_page_warning_label)

        details = QFrame()
        details.setObjectName("ProfileCard")
        details_layout = QFormLayout(details)
        details_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        details_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        details_layout.setHorizontalSpacing(16)
        details_layout.setVerticalSpacing(10)

        self.account_page_display_label = QLabel("—")
        self.account_page_full_name_label = QLabel("—")
        self.account_page_login_label = QLabel("—")
        self.account_page_email_label = QLabel("—")
        self.account_page_phone_label = QLabel("—")
        self.account_page_mode_label = QLabel("—")
        self.account_page_status_label = QLabel("—")
        self.account_page_verification_label = QLabel("—")
        self.account_page_registration_status_label = QLabel("—")
        self.account_page_binding_label = QLabel("—")
        self.account_page_session_label = QLabel("—")
        self.account_page_claim_label = QLabel("—")
        self.account_page_base_owner_label = QLabel("—")
        self.account_page_expires_label = QLabel("—")
        self.account_page_last_validated_label = QLabel("—")
        self.account_page_reason_label = QLabel("—")
        for value_label in (
            self.account_page_display_label,
            self.account_page_full_name_label,
            self.account_page_login_label,
            self.account_page_email_label,
            self.account_page_phone_label,
            self.account_page_mode_label,
            self.account_page_status_label,
            self.account_page_verification_label,
            self.account_page_registration_status_label,
            self.account_page_binding_label,
            self.account_page_session_label,
            self.account_page_claim_label,
            self.account_page_base_owner_label,
            self.account_page_expires_label,
            self.account_page_last_validated_label,
            self.account_page_reason_label,
        ):
            value_label.setObjectName("ProfileFieldValue")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        details_layout.addRow("Отображаемое имя", self.account_page_display_label)
        details_layout.addRow("ФИО", self.account_page_full_name_label)
        details_layout.addRow("Логин", self.account_page_login_label)
        details_layout.addRow("Email", self.account_page_email_label)
        details_layout.addRow("Телефон", self.account_page_phone_label)
        details_layout.addRow("Тип входа", self.account_page_mode_label)
        details_layout.addRow("Статус сессии", self.account_page_status_label)
        details_layout.addRow("Проверка", self.account_page_verification_label)
        details_layout.addRow("Статус регистрации", self.account_page_registration_status_label)
        details_layout.addRow("Session", self.account_page_session_label)
        details_layout.addRow("Binding", self.account_page_binding_label)
        details_layout.addRow("Claim", self.account_page_claim_label)
        details_layout.addRow("Зарегистрированный владелец ПК", self.account_page_base_owner_label)
        details_layout.addRow("Действует до", self.account_page_expires_label)
        details_layout.addRow("Последняя проверка", self.account_page_last_validated_label)
        details_layout.addRow("Причина", self.account_page_reason_label)
        layout.addWidget(details)

        actions = QHBoxLayout()
        self.account_page_refresh_btn = QPushButton("Обновить")
        self.account_page_refresh_btn.setObjectName("SecondaryButton")
        self.account_page_refresh_btn.clicked.connect(self._refresh_account_state)
        self.account_page_logout_btn = QPushButton("Выйти из аккаунта")
        self.account_page_logout_btn.setObjectName("SecondaryButton")
        self.account_page_logout_btn.clicked.connect(self._on_account_logout_clicked)
        actions.addWidget(self.account_page_refresh_btn)
        actions.addWidget(self.account_page_logout_btn)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)
        return page

    def _account_mode_label(self, mode: str) -> str:
        return {
            "confirmed_binding": "Подтвержденный аккаунт устройства",
            "registration_pending": "Регистрация ожидает подтверждения",
            "verified_other_account": "Другой аккаунт, подтвержденный администратором",
        }.get(mode, mode or "Аккаунт не выбран")

    def _refresh_account_page(self) -> None:
        if not hasattr(self, "account_page_display_label"):
            return
        session = self._active_account_session_for_tickets()
        if not session:
            values = {
                "display": "Аккаунт не выбран",
                "full_name": "—",
                "login": "—",
                "email": "—",
                "phone": "—",
                "mode": "Аккаунт не выбран",
                "status": "none",
                "verification": "—",
                "registration_status": "—",
                "session": "—",
                "binding": "—",
                "claim": "—",
                "base_owner": "—",
                "expires": "—",
                "last_validated": "—",
                "reason": "—",
                "warning": "Для работы с обращениями выберите подтвержденный аккаунт или пройдите регистрацию.",
            }
        else:
            mode = str(session.get("account_mode") or "")
            session_id = session.get("account_session_id") or session.get("session_id") or "—"
            binding = session.get("binding_id") or session.get("base_binding_id") or "—"
            claim = session.get("claim_id") or session.get("last_claim_id") or "—"
            base_owner = session.get("base_display_name") or session.get("base_person_id") or "—"
            metadata = session.get("metadata") if isinstance(session.get("metadata"), dict) else {}
            warning = ""
            if mode == "verified_other_account":
                warning = "Вы вошли не под зарегистрированным пользователем этого ПК. Новые обращения будут помечены для поддержки."
            if mode == "registration_pending":
                warning = "Регистрация ожидает подтверждения. Обращения будут помечены как созданные до подтверждения регистрации."
            values = {
                "display": session.get("display_name") or session.get("full_name") or session.get("login") or "Без имени",
                "full_name": session.get("full_name") or "—",
                "login": session.get("login") or "—",
                "email": session.get("email") or "—",
                "phone": session.get("phone") or "—",
                "mode": self._account_mode_label(mode),
                "status": session.get("verification_status") or session.get("registration_status") or "—",
                "verification": session.get("verification_method") or "—",
                "registration_status": session.get("registration_status") or "—",
                "session": str(session_id),
                "binding": str(binding),
                "claim": str(claim),
                "base_owner": str(base_owner),
                "expires": session.get("expires_at") or "—",
                "last_validated": metadata.get("last_validated_at") or session.get("last_validated_at") or "—",
                "reason": session.get("reason") or metadata.get("reason") or "—",
                "warning": warning,
            }
        self.account_page_display_label.setText(str(values["display"]))
        self.account_page_full_name_label.setText(str(values["full_name"]))
        self.account_page_login_label.setText(str(values["login"]))
        self.account_page_email_label.setText(str(values["email"]))
        self.account_page_phone_label.setText(str(values["phone"]))
        self.account_page_mode_label.setText(str(values["mode"]))
        self.account_page_status_label.setText(str(values["status"]))
        self.account_page_verification_label.setText(str(values["verification"]))
        self.account_page_registration_status_label.setText(str(values["registration_status"]))
        self.account_page_session_label.setText(str(values["session"]))
        self.account_page_binding_label.setText(str(values["binding"]))
        self.account_page_claim_label.setText(str(values["claim"]))
        self.account_page_base_owner_label.setText(str(values["base_owner"]))
        self.account_page_expires_label.setText(str(values["expires"]))
        self.account_page_last_validated_label.setText(str(values["last_validated"]))
        self.account_page_reason_label.setText(str(values["reason"]))
        self.account_page_warning_label.setText(str(values["warning"]))
        self.account_page_warning_label.setVisible(bool(values["warning"]))

    def _on_account_logout_clicked(self) -> None:
        self._spawn_gui_task(self._async_account_logout(), name="account.logout")

    async def _async_account_logout(self) -> None:
        session_id = str(self._account_session.get("account_session_id") or "").strip()
        session_token = str(self._account_session.get("session_token") or "").strip() or None
        if session_id:
            payload = await self.chat_panel.ticket_client.logout_account_session(session_id, session_token=session_token)
            if isinstance(payload, dict) and payload.get("status") == "error":
                logger.warning(f"[account] server logout failed; clearing local session only: {payload}")
        self._account_session = {"schema_version": 1, "account_mode": "none"}
        self._account_session_manager.clear()
        self.chat_panel.tickets_cache = []
        self.chat_panel.active_ticket_id = None
        try:
            self.chat_panel._update_tickets_list_ui()
        except Exception as exc:
            logger.debug(f"[account] failed to clear ticket list after logout: {exc}")
        self.account_gate_page.render(self._account_state, local_session=self._account_session)
        self._render_profile_status()
        self._select_sidebar_view("account_gate", expand=True)

    def _clear_local_account_session_state(self) -> None:
        self._account_session = {"schema_version": 1, "account_mode": "none"}
        self._account_session_manager.clear()
        self.chat_panel.tickets_cache = []
        self.chat_panel.active_ticket_id = None
        try:
            if hasattr(self.chat_panel, "_ticket_detail_timer"):
                self.chat_panel._ticket_detail_timer.stop()
            self.chat_panel._reset_active_ticket_cache()
            self.chat_panel._update_tickets_list_ui()
        except Exception as exc:
            logger.debug(f"[account] failed to reset ticket state: {exc}")

    def handle_account_session_error(self, error: Any) -> bool:
        action = account_session_error_action(error)
        code = account_session_error_code(error)
        if action == "clear_session":
            self._clear_local_account_session_state()
            self.account_gate_page.render(
                self._account_state,
                local_session=self._account_session,
                error="Сессия аккаунта недействительна. Войдите снова.",
            )
            self._render_profile_status()
            self._select_sidebar_view("account_gate", expand=True)
            return True
        if action == "refresh_account_state":
            self._clear_local_account_session_state()
            self._refresh_account_state()
            self._show_nonblocking_message(
                "Аккаунт обновлён",
                "Регистрация подтверждена. Обновите состояние и войдите как подтверждённый аккаунт.",
                QMessageBox.Icon.Information,
            )
            return True
        if action == "deny_access":
            self.chat_panel.active_ticket_id = None
            try:
                self.chat_panel._reset_active_ticket_cache()
                self.chat_panel._show_list_screen()
            except Exception as exc:
                logger.debug(f"[account] failed to leave denied ticket: {exc}")
            self._show_nonblocking_message(
                "Нет доступа",
                "У этого аккаунта нет доступа к выбранному обращению.",
                QMessageBox.Icon.Warning,
            )
            return True
        if code:
            logger.debug(f"[account] unhandled account-session error: {code}")
        return False

    def _build_legacy_registration_disabled_page(self) -> QWidget:
        page = QFrame()
        page.setObjectName("MainPanel")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Привязка устройства через браузер")
        title.setObjectName("MainTitle")
        header_row.addWidget(title, 1)
        back_btn = QPushButton("Назад")
        back_btn.setObjectName("SecondaryButton")
        back_btn.clicked.connect(self._show_account_gate_entry)
        header_row.addWidget(back_btn, 0)
        outer.addLayout(header_row)

        subtitle = QLabel(
            "Профиль заполняется в веб-кабинете. Агент создаёт только ссылку или код для привязки этого устройства."
        )
        subtitle.setObjectName("MainSubtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        actions = QHBoxLayout()
        browser_btn = QPushButton("Привязать через браузер")
        browser_btn.setObjectName("PrimaryButton")
        browser_btn.clicked.connect(self._on_browser_register_requested)
        actions.addWidget(browser_btn)
        refresh_btn = QPushButton("Проверить статус")
        refresh_btn.setObjectName("SecondaryButton")
        refresh_btn.clicked.connect(self._refresh_account_state)
        actions.addWidget(refresh_btn)
        actions.addStretch(1)
        outer.addLayout(actions)
        outer.addStretch(1)
        page.setStyleSheet(theme.main_window_stylesheet())
        return page

    def _build_registration_entry_page(self) -> QWidget:
        page = QFrame()
        page.setObjectName("MainPanel")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Регистрация пользователя")
        title.setObjectName("MainTitle")
        header_row.addWidget(title, 1)
        back_btn = QPushButton("Назад")
        back_btn.setObjectName("SecondaryButton")
        back_btn.clicked.connect(self._show_account_gate_entry)
        header_row.addWidget(back_btn, 0)
        outer.addLayout(header_row)

        subtitle = QLabel(
            "Заполните данные аккаунта для регистрации этого рабочего места. "
            "Это не создаёт обращение и не меняет технический токен агента."
        )
        subtitle.setObjectName("MainSubtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        self.registration_status_label = QLabel("Не загружено")
        self.registration_status_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px;")
        outer.addWidget(self.registration_status_label)

        self._registration_form_def = default_agent_registration_form()
        self._registration_registry_options: dict[str, Any] = {}
        self.registration_form_widget = DynamicFormWidget()
        self.registration_form_widget.set_form(self._registration_form_def)

        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.registration_form_widget)
        outer.addWidget(scroll, 1)

        self.registration_entry_status_label = QLabel("")
        self.registration_entry_status_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; background: transparent;")
        outer.addWidget(self.registration_entry_status_label)

        actions = QHBoxLayout()
        self.registration_save_btn = QPushButton("Сохранить локально")
        self.registration_save_btn.setObjectName("SecondaryButton")
        self.registration_save_btn.clicked.connect(self._on_save_registration_profile_clicked)
        self.registration_submit_btn = QPushButton("Отправить на сервер")
        self.registration_submit_btn.setObjectName("PrimaryButton")
        self.registration_submit_btn.clicked.connect(self._on_submit_registration_profile_clicked)
        self.registration_confirm_btn = QPushButton("Подтвердить данные")
        self.registration_confirm_btn.setObjectName("SecondaryButton")
        self.registration_confirm_btn.clicked.connect(self._on_confirm_registration_claim_clicked)
        self.registration_refresh_btn = QPushButton("Обновить форму")
        self.registration_refresh_btn.setObjectName("SecondaryButton")
        self.registration_refresh_btn.clicked.connect(self._on_refresh_registration_form_clicked)
        for button in (
            self.registration_save_btn,
            self.registration_submit_btn,
            self.registration_confirm_btn,
            self.registration_refresh_btn,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        outer.addLayout(actions)
        page.setStyleSheet(theme.main_window_stylesheet())
        return page

    async def _async_refresh_account_state(self) -> None:
        try:
            state = await self.chat_panel.ticket_client.get_account_state()
        except Exception as exc:
            self.account_gate_page.render({}, local_session=self._account_session, error=str(exc))
            return
        if isinstance(state, dict) and state.get("status") == "error":
            message = str(state.get("error") or state.get("body") or "Ошибка проверки аккаунта")
            self.account_gate_page.render({}, local_session=self._account_session, error=message)
            return
        self._account_state = state if isinstance(state, dict) else {}
        try:
            local_session_valid = await self._validate_local_account_session_with_server(
                self._account_session,
                self._account_state,
            )
        except Exception as exc:
            if account_session_error_action(exc) != "clear_session":
                raise
            self._clear_local_account_session_state()
            self.account_gate_page.render(
                self._account_state,
                local_session=self._account_session,
                error="Сессия аккаунта недействительна. Войдите снова.",
            )
            self._render_profile_status()
            self._select_sidebar_view("account_gate", expand=True)
            return
        if not local_session_valid:
            self._account_session = {"schema_version": 1, "account_mode": "none"}
            self._account_session_manager.clear()
        else:
            enriched = self._account_session_manager.enrich_from_account_state(self._account_session, self._account_state)
            if enriched != self._account_session:
                self._account_session = self._account_session_manager.save(enriched)
        self.account_gate_page.render(self._account_state, local_session=self._account_session)
        if not self._active_account_session_for_tickets() and self._active_sidebar_view not in {"account_gate", "registration", "settings"}:
            self._select_sidebar_view("account_gate", expand=True)
        self._render_profile_status()

    def _is_local_account_session_valid(self, session: dict[str, Any], state: dict[str, Any]) -> bool:
        return self._account_session_manager.matches_account_state(session, state)

    async def _validate_local_account_session_with_server(self, session: dict[str, Any], state: dict[str, Any]) -> bool:
        mode = str(session.get("account_mode") or "")
        if mode == "pending_other_account_request":
            return bool(str(session.get("pending_login_request_id") or "").strip())
        if mode not in {"confirmed_binding", "verified_other_account", "registration_pending"}:
            return False
        session_id = str(session.get("account_session_id") or "").strip()
        if not session_id:
            return False
        validated = await self.chat_panel.ticket_client.validate_account_session(
            session_id,
            session_token=str(session.get("session_token") or "").strip() or None,
        )
        return isinstance(validated, dict) and validated.get("valid") is True

    def _on_browser_login_requested(self) -> None:
        self._spawn_gui_task(self._async_browser_pairing("login"), name="account.browser_login")

    def _on_browser_register_requested(self) -> None:
        self._spawn_gui_task(self._async_browser_pairing("registration"), name="account.browser_register")

    def _browser_pairing_url(self, browser_url: str) -> str:
        browser_url = str(browser_url or "").strip()
        if browser_url.startswith(("http://", "https://")):
            return _normalize_browser_handoff_origin(browser_url)
        base_url = str(getattr(self.chat_panel.ticket_client, "base_url", "") or "").rstrip("/")
        if base_url.endswith("/api"):
            base_url = base_url[:-4]
        base_url = _normalize_browser_handoff_origin(base_url)
        if browser_url.startswith("/"):
            return f"{base_url}{browser_url}" if base_url else browser_url
        return browser_url

    def _browser_pairing_open_url(self, url: str) -> None:
        if url:
            QDesktopServices.openUrl(QUrl(url))

    async def _async_browser_pairing(
        self,
        purpose: str,
        *,
        poll_interval_seconds: float = 2.0,
        max_polls: int = 90,
    ) -> None:
        purpose = "registration" if str(purpose or "").strip() == "registration" else "login"
        action_label = "регистрации" if purpose == "registration" else "входа"
        payload = await self.chat_panel.ticket_client.create_browser_pairing(purpose)
        if isinstance(payload, dict) and payload.get("status") == "error":
            self.account_gate_page.render(
                self._account_state,
                local_session=self._account_session,
                error=str(payload.get("error") or f"Не удалось создать ссылку {action_label} через браузер"),
            )
            return
        pairing_id = str(payload.get("pairing_id") or "").strip() if isinstance(payload, dict) else ""
        browser_url = self._browser_pairing_url(str(payload.get("browser_url") or "")) if isinstance(payload, dict) else ""
        pairing_code = str(payload.get("pairing_code") or "").strip() if isinstance(payload, dict) else ""
        if not pairing_id or not browser_url:
            self.account_gate_page.render(
                self._account_state,
                local_session=self._account_session,
                error=f"Сервер вернул неполные данные {action_label} через браузер.",
            )
            return
        self._browser_pairing_open_url(browser_url)
        message = "Открылся браузер. Подтвердите действие на веб-странице."
        if pairing_code:
            message = f"{message} Код привязки: {pairing_code}."
        self.account_gate_page.render(
            {**self._account_state, "message": message, "browser_pairing_code": pairing_code},
            local_session=self._account_session,
        )
        for attempt in range(max(1, int(max_polls))):
            result = await self.chat_panel.ticket_client.get_browser_pairing(pairing_id)
            if isinstance(result, dict) and result.get("status") == "error":
                self.account_gate_page.render(
                    self._account_state,
                    local_session=self._account_session,
                    error=str(result.get("error") or f"Не удалось проверить {action_label} через браузер"),
                )
                return
            status = str((result or {}).get("status") or "").strip().lower()
            if purpose == "login" and status == "consumed":
                session_payload = result.get("session") if isinstance(result.get("session"), dict) else {}
                token = str(result.get("session_token") or "").strip()
                if not session_payload or not token:
                    self.account_gate_page.render(
                        self._account_state,
                        local_session=self._account_session,
                        error="Сервер не вернул токен сессии аккаунта. Создайте новую ссылку входа.",
                    )
                    return
                session_payload = {**session_payload, "session_token": token}
                self._account_session = self._account_session_manager.save(
                    self._account_session_manager.build_confirmed_binding_session(
                        session_payload,
                        device_id=self.chat_panel.device_id,
                    )
                )
                self.account_gate_page.render(self._account_state, local_session=self._account_session)
                self._set_account_entry_mode(False)
                self._render_profile_status()
                self._select_sidebar_view("tickets", expand=True)
                return
            if purpose == "registration" and status in {"confirmed", "consumed"}:
                refreshed = await self.chat_panel.ticket_client.get_account_state()
                if isinstance(refreshed, dict) and refreshed.get("status") != "error":
                    self._account_state = refreshed
                self.account_gate_page.render(
                    {**self._account_state, "message": "Регистрация подтверждена через браузер."},
                    local_session=self._account_session,
                )
                return
            if status in {"expired", "superseded"}:
                self.account_gate_page.render(
                    self._account_state,
                    local_session=self._account_session,
                    error=f"Ссылка {action_label} больше не активна. Создайте новую ссылку.",
                )
                return
            if attempt + 1 < max_polls:
                await asyncio.sleep(max(0.0, float(poll_interval_seconds)))
        self.account_gate_page.render(
            self._account_state,
            local_session=self._account_session,
            error=f"Не дождались подтверждения {action_label} через браузер.",
        )

    def _on_account_login_confirmed(self, account: dict[str, Any]) -> None:
        self._spawn_gui_task(self._async_account_login_confirmed(account), name="account.login_confirmed")

    async def _async_account_login_confirmed(self, account: dict[str, Any]) -> None:
        payload = await self.chat_panel.ticket_client.create_confirmed_binding_account_session(str(account.get("binding_id") or ""))
        if isinstance(payload, dict) and payload.get("status") == "error":
            self.account_gate_page.render(
                self._account_state,
                local_session=self._account_session,
                error=str(payload.get("error") or "Не удалось войти"),
            )
            return
        session_payload = payload.get("session") if isinstance(payload.get("session"), dict) else {}
        session_payload = {**session_payload, "session_token": payload.get("session_token")}
        self._account_session = self._account_session_manager.save(
            self._account_session_manager.build_confirmed_binding_session(session_payload, device_id=self.chat_panel.device_id)
        )
        self.account_gate_page.render(self._account_state, local_session=self._account_session)
        self._set_account_entry_mode(False)
        self._render_profile_status()
        self._select_sidebar_view("tickets", expand=True)

    def _on_account_login_other(self, profile: dict[str, Any]) -> None:
        self._spawn_gui_task(self._async_account_login_other(profile), name="account.login_other")

    async def _async_account_login_other(self, profile: dict[str, Any]) -> None:
        if str(profile.get("account_mode") or "") == "verified_other_account" and str(profile.get("session_id") or "").strip():
            if not str(profile.get("session_token") or "").strip() and str(profile.get("source_request_id") or "").strip():
                request_payload = await self.chat_panel.ticket_client.get_account_login_request(
                    str(profile.get("source_request_id") or "").strip()
                )
                if isinstance(request_payload, dict) and request_payload.get("session_token"):
                    profile = {
                        **profile,
                        "session_token": request_payload.get("session_token"),
                        "session": request_payload.get("session"),
                    }
                    if isinstance(request_payload.get("session"), dict):
                        profile = {**request_payload["session"], "session_token": request_payload.get("session_token")}
            if not str(profile.get("session_token") or "").strip():
                self.account_gate_page.render(
                    self._account_state,
                    local_session=self._account_session,
                    error="Не удалось получить серверный токен сессии аккаунта. Обновите состояние и попробуйте снова.",
                )
                return
            self._account_session = self._account_session_manager.save(
                self._account_session_manager.build_verified_other_account_session(
                    profile,
                    profile,
                    device_id=self.chat_panel.device_id,
                )
            )
            self.account_gate_page.reset_other_form()
            self.account_gate_page.render(self._account_state, local_session=self._account_session)
            self._set_account_entry_mode(False)
            self._render_profile_status()
            self._select_sidebar_view("tickets", expand=True)
            return
        payload = await self.chat_panel.ticket_client.request_other_account_login(profile)
        if isinstance(payload, dict) and payload.get("status") == "error":
            self.account_gate_page.render(
                self._account_state,
                local_session=self._account_session,
                error=str(payload.get("error") or "Не удалось отправить заявку"),
            )
            return
        self._account_session = self._account_session_manager.save(
            self._account_session_manager.build_pending_other_account_request_session(
                profile,
                payload,
                device_id=self.chat_panel.device_id,
            )
        )
        self.account_gate_page.reset_other_form()
        refreshed = await self.chat_panel.ticket_client.get_account_state()
        if isinstance(refreshed, dict) and refreshed.get("status") != "error":
            self._account_state = refreshed
        self.account_gate_page.render(
            {**self._account_state, "message": "Заявка на вход в другой аккаунт отправлена. Ожидает подтверждения администратора."},
            local_session=self._account_session,
        )

    def _on_check_other_login_request(self, request_id: str) -> None:
        self._spawn_gui_task(self._async_check_other_login_request(request_id), name="account.check_other_request")

    async def _async_check_other_login_request(self, request_id: str) -> None:
        payload = await self.chat_panel.ticket_client.get_account_login_request(request_id)
        if isinstance(payload, dict) and payload.get("status") == "error":
            self.account_gate_page.render(
                self._account_state,
                local_session=self._account_session,
                error=str(payload.get("error") or "Не удалось проверить заявку на вход"),
            )
            return
        status = str(payload.get("status") or "").strip()
        if status == "approved":
            session_payload = payload.get("session") if isinstance(payload.get("session"), dict) else {}
            token = str(payload.get("session_token") or "").strip()
            if session_payload and token:
                session_payload = {**session_payload, "session_token": token}
                self._account_session = self._account_session_manager.save(
                    self._account_session_manager.build_verified_other_account_session(
                        payload.get("requested_account") if isinstance(payload.get("requested_account"), dict) else {},
                        session_payload,
                        device_id=self.chat_panel.device_id,
                    )
                )
                refreshed = await self.chat_panel.ticket_client.get_account_state()
                if isinstance(refreshed, dict) and refreshed.get("status") != "error":
                    self._account_state = refreshed
                self.account_gate_page.reset_other_form()
                self.account_gate_page.render(self._account_state, local_session=self._account_session)
                self._set_account_entry_mode(False)
                self._render_profile_status()
                self._select_sidebar_view("tickets", expand=True)
                return
            self.account_gate_page.render(
                self._account_state,
                local_session=self._account_session,
                error="Токен подтверждения уже был выдан. Обновите заявку или обратитесь к администратору.",
            )
            return
        if status in {"rejected", "expired", "canceled"}:
            self._account_session_manager.clear()
            self._account_session = {"schema_version": 1, "account_mode": "none"}
            refreshed = await self.chat_panel.ticket_client.get_account_state()
            if isinstance(refreshed, dict) and refreshed.get("status") != "error":
                self._account_state = refreshed
            if status == "rejected":
                message = str(payload.get("rejection_reason") or "Заявка на вход отклонена.")
            elif status == "expired":
                message = "Заявка на вход устарела. Обновите состояние и создайте новую заявку."
            else:
                message = str(
                    payload.get("rejection_reason")
                    or "Заявка на вход отменена после изменения привязки устройства. Обновите состояние и создайте новую заявку."
                )
            self.account_gate_page.render({**self._account_state, "message": message}, local_session=self._account_session)
            self._render_profile_status()
            return
        self._account_session = self._account_session_manager.save(
            self._account_session_manager.build_pending_other_account_request_session(
                payload.get("requested_account") if isinstance(payload.get("requested_account"), dict) else {},
                payload,
                device_id=self.chat_panel.device_id,
            )
        )
        message = "Заявка на вход в другой аккаунт ожидает подтверждения администратора."
        if status == "rejected":
            message = str(payload.get("rejection_reason") or "Заявка на вход отклонена.")
        self.account_gate_page.render({**self._account_state, "message": message}, local_session=self._account_session)

    def _on_account_register_requested(self) -> None:
        self._show_registration_entry()

    async def _save_registration_pending_account_session(self, profile: dict[str, Any], registration: dict[str, Any]) -> None:
        claim_id = str(registration.get("claim_id") or registration.get("pending_claim_id") or "").strip()
        if not claim_id:
            raise RuntimeError("Не удалось создать account session: claim_id отсутствует")
        payload = await self.chat_panel.ticket_client.create_registration_pending_account_session(claim_id)
        if isinstance(payload, dict) and payload.get("status") == "error":
            raise RuntimeError(str(payload.get("error") or "Не удалось создать pending account session"))
        server_session = payload.get("session") if isinstance(payload.get("session"), dict) else {}
        server_session = {**server_session, "session_token": payload.get("session_token")}
        self._account_session = self._account_session_manager.save(
            self._account_session_manager.build_registration_pending_session(
                profile,
                registration,
                device_id=self.chat_panel.device_id,
                server_session=server_session,
            )
        )
        refreshed = await self.chat_panel.ticket_client.get_account_state()
        if isinstance(refreshed, dict) and refreshed.get("status") != "error":
            self._account_state = refreshed
        if hasattr(self, "account_gate_page"):
            self.account_gate_page.render(self._account_state, local_session=self._account_session)
        self._set_account_entry_mode(True)
        self._render_profile_status()

    def _set_account_entry_mode(self, enabled: bool) -> None:
        self._account_entry_mode = enabled
        if hasattr(self, "sidebar_shell"):
            self.sidebar_shell.setVisible(not enabled)
        if hasattr(self, "security_footer"):
            self.security_footer.setVisible(not enabled)
        if hasattr(self, "settings_back_btn"):
            self.settings_back_btn.setVisible(enabled and self._active_sidebar_view == "settings")
        if hasattr(self, "body_splitter"):
            if enabled:
                self.body_splitter.setSizes([0, 1200])
            else:
                sidebar_width = self._sidebar_content_width if self._sidebar_expanded else self._sidebar_collapsed_width
                self.sidebar_shell.setMinimumWidth(sidebar_width)
                self.sidebar_shell.setMaximumWidth(sidebar_width)
                self.body_splitter.setSizes([sidebar_width, 1000])

    def _show_registration_entry(self) -> None:
        if not legacy_agent_registration_enabled():
            self._on_browser_register_requested()
            self._show_account_gate_entry()
            return
        self._select_sidebar_view("registration", expand=True)
        self._load_registration_profile_to_form()
        self._set_registration_entry_status("Заполните форму регистрации пользователя.", error=False)

    def _show_account_gate_entry(self) -> None:
        self._select_sidebar_view("account_gate", expand=True)

    def _update_account_uia_metadata(self) -> None:
        session = self._active_account_session_for_tickets()
        description = account_description(session)
        display_name = ""
        mode = "none"
        if session:
            display_name = str(session.get("display_name") or session.get("full_name") or session.get("login") or "")
            mode = str(session.get("account_mode") or "unknown")
        set_uia_metadata(self.sidebar_profile_card, name="agent.account.summary", description=description)
        set_uia_metadata(
            self.sidebar_profile_name_label,
            name="agent.account.person",
            description=f"id=agent.account.person; display_name={display_name or 'none'}",
        )
        set_uia_metadata(
            self.sidebar_profile_meta_label,
            name="agent.account.mode",
            description=f"id=agent.account.mode; account_mode={mode}; account_exists={str(bool(session)).lower()}",
        )

    def _refresh_sidebar_labels(self) -> None:
        self._update_account_uia_metadata()
        if not self._sidebar_expanded:
            self.sidebar_dashboard_btn.setText("")
            self.sidebar_create_ticket_btn.setText("")
            self.sidebar_tickets_btn.setText("")
            self.sidebar_settings_btn.setText("")
            return
        self.sidebar_dashboard_btn.setText("  Рабочий стол")
        self.sidebar_create_ticket_btn.setText("  Создать обращение")
        self.sidebar_tickets_btn.setText("  Обращения")
        self.sidebar_settings_btn.setText("  Настройки")
        session = self._active_account_session_for_tickets()
        if session:
            full_name = str(session.get("full_name") or session.get("display_name") or session.get("login") or "Без имени")
            display = str(session.get("display_name") or full_name)
            self.sidebar_profile_name_label.setText(display)
            self.sidebar_profile_meta_label.setText(self._account_summary())
            initials_src = display or full_name
        else:
            self.sidebar_profile_name_label.setText("Аккаунт не выбран")
            self.sidebar_profile_meta_label.setText("Войдите для работы с обращениями")
            initials_src = self.chat_panel.user_display_name
        initials = "".join(part[:1] for part in str(initials_src or "AD").replace("-", " ").split()[:2]).upper()
        self.sidebar_avatar_label.setText(initials or "AD")

    def _set_sidebar_selection_state(
        self,
        *,
        dashboard: bool = False,
        settings: bool = False,
        tickets: bool = False,
        profile: bool = False,
    ) -> None:
        self.sidebar_dashboard_btn.setChecked(dashboard)
        self.sidebar_settings_btn.setChecked(settings)
        self.sidebar_tickets_btn.setChecked(tickets)
        self.sidebar_profile_card.setProperty("active", profile)
        border = theme.current_palette().border_active if profile else theme.current_palette().border
        self.sidebar_profile_card.setStyleSheet(
            f"QFrame#ProfileCard {{ background: {theme.current_palette().bg_card_alt if theme.current_theme_mode() == 'dark' else theme.current_palette().bg_card}; "
            f"border: 1px solid {border}; border-radius: 16px; }}"
        )
        for button in (self.sidebar_dashboard_btn, self.sidebar_settings_btn, self.sidebar_tickets_btn):
            button.setObjectName("SidebarButtonActive" if button.isChecked() else "SidebarButton")
            button.style().unpolish(button)
            button.style().polish(button)

    def _on_create_ticket_from_menu(self) -> None:
        logger.info("[ui] open create ticket wizard requested")
        if not self._active_account_session_for_tickets():
            self._select_sidebar_view("account_gate", expand=True)
            return
        self._select_sidebar_view("create", expand=False)
        self.ticket_create_page.reset_wizard()
        self.ticket_create_page._set_status("Открываю форму обращения...", error=False)
        self._spawn_gui_task(self.ticket_create_page.async_prepare(), name="gui.create_ticket.prepare")

    def _spawn_gui_task(self, coro, *, name: str = "gui.task") -> Optional[asyncio.Task]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop_policy().get_event_loop()
            except RuntimeError:
                logger.error(f"[ui] cannot schedule {name}: asyncio loop is not available")
                try:
                    coro.close()
                except Exception:
                    pass
                return None
        if not loop.is_running():
            logger.error(f"[ui] cannot schedule {name}: asyncio loop is not running")
            try:
                coro.close()
            except Exception:
                pass
            return None
        task = loop.create_task(coro, name=name)

        def _done(done_task: asyncio.Task) -> None:
            try:
                done_task.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.error(f"[ui] background task failed: {name}: {exc}")

        task.add_done_callback(_done)
        return task

    def _select_sidebar_view(self, view_name: str, *, expand: bool) -> None:
        if view_name == "registration" and not legacy_agent_registration_enabled():
            view_name = "account_gate"
            expand = True
        if view_name in {"dashboard", "tickets", "ticket", "profile", "create"} and not self._active_account_session_for_tickets():
            view_name = "account_gate"
            expand = True
        self._active_sidebar_view = view_name
        self._set_account_entry_mode(view_name in {"account_gate", "registration", "settings"} and not self._active_account_session_for_tickets())
        if view_name in {"create", "ticket"}:
            self._set_sidebar_expanded(False)
        elif expand:
            self._set_sidebar_expanded(True)
        if view_name == "account_gate":
            self._set_sidebar_selection_state(profile=True)
            self.main_content_stack.setCurrentWidget(self.account_gate_page)
            self.account_gate_page.render(self._account_state, local_session=self._account_session)
        elif view_name == "registration":
            self._set_sidebar_selection_state()
            self.main_content_stack.setCurrentWidget(self.registration_entry_page)
        elif view_name == "tickets":
            self._set_sidebar_selection_state(tickets=True)
            self.main_content_stack.setCurrentWidget(self.tickets_sidebar)
            self.chat_panel._refresh_ticket_list_async()
        elif view_name == "ticket":
            self._set_sidebar_selection_state(tickets=True)
            self.main_content_stack.setCurrentWidget(self.chat_panel)
        elif view_name == "dashboard":
            self._set_sidebar_selection_state(dashboard=True)
            self.main_content_stack.setCurrentWidget(self.dashboard_page)
            self._refresh_dashboard()
            self.chat_panel._refresh_ticket_list_async()
        elif view_name == "profile":
            self._set_sidebar_selection_state(profile=True)
            self.main_content_stack.setCurrentWidget(self.account_page)
            self._refresh_account_page()
        elif view_name == "create":
            self._set_sidebar_selection_state()
            self.main_content_stack.setCurrentWidget(self.ticket_create_page)
        elif view_name == "settings":
            self._set_sidebar_selection_state(settings=True)
            self.main_content_stack.setCurrentWidget(self.settings_page)
        else:
            self._set_sidebar_selection_state()

    def _on_ticket_created_from_wizard(self, _ticket_id: str) -> None:
        self._select_sidebar_view("ticket", expand=False)

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
        """Открывает страницу настроек."""
        self._select_sidebar_view("settings", expand=True)
        self._settings_form_loaded = False
        self._settings_snapshot = None
        self._load_device_uuid()
        self._render_profile_status()
        self._set_settings_status("Загрузка настроек...", error=False)
        QTimer.singleShot(0, lambda: asyncio.create_task(self._async_load_settings()))

    def _render_profile_status(self) -> None:
        self._refresh_sidebar_labels()
        self._refresh_dashboard()
        self._refresh_account_page()

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

    def _set_registration_entry_status(self, text: str, error: bool = False) -> None:
        color = theme.DANGER_FG if error else theme.TEXT_MUTED
        if hasattr(self, "registration_entry_status_label"):
            self.registration_entry_status_label.setStyleSheet(f"color: {color}; background: transparent;")
            self.registration_entry_status_label.setText(self._repair_text(text))

    def _set_settings_buttons_enabled(self, enabled: bool) -> None:
        self.test_connection_btn.setEnabled(enabled)
        self.save_settings_btn.setEnabled(enabled)
        self.restart_agent_btn.setEnabled(enabled)

    def _apply_settings_page_theme(self) -> None:
        self.settings_header.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {theme.TEXT_PRIMARY}; background: transparent; padding: 4px 6px;"
        )
        self.settings_subtitle.setStyleSheet(
            f"font-size: 11px; color: {theme.TEXT_MUTED}; background: transparent; padding: 0 6px 4px 6px;"
        )
        for section in self._settings_sections:
            section.setStyleSheet(
                f"QFrame {{ background: {theme.BG_CARD_ALT}; border: 1px solid {theme.BORDER_SOFT}; border-radius: 22px; }}"
            )
        for label in self._settings_section_titles:
            label.setStyleSheet(
                f"font-size: 15px; font-weight: 700; color: {theme.TEXT_PRIMARY}; background: transparent;"
            )
        for label in self._settings_section_subtitles:
            label.setStyleSheet(
                f"font-size: 11px; color: {theme.TEXT_MUTED}; background: transparent;"
            )
        self.device_uuid_label.setStyleSheet(
            f"font-family: monospace; font-size: 13px; padding: 8px; "
            f"background: {theme.BG_INPUT}; border: 1px solid {theme.BORDER}; border-radius: 10px; "
            f"color: {theme.TEXT_PRIMARY};"
        )
        self.config_path_hint.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        self.ui_bridge_hint.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        self.runtime_status_label.setStyleSheet(
            f"padding: 8px; background: {theme.BG_INPUT}; border: 1px solid {theme.BORDER}; "
            f"border-radius: 10px; color: {theme.TEXT_SECONDARY};"
        )
        self.installed_modules_label.setStyleSheet(
            f"font-family: Consolas, 'Courier New', monospace; font-size: 11px; padding: 8px; "
            f"background: {theme.BG_INPUT}; border: 1px solid {theme.BORDER}; border-radius: 10px; "
            f"color: {theme.TEXT_SECONDARY};"
        )
        self.enabled_modules_hint.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        self.token_hint_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; background: transparent;")
        if not self.settings_status_label.text():
            self.settings_status_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; background: transparent;")

    def _preview_theme_mode(self, mode: str) -> None:
        app = QApplication.instance()
        if app is not None:
            theme.apply_application_theme(app, mode)
        self.centralWidget().setStyleSheet(theme.main_window_stylesheet())
        if hasattr(self, "title_bar"):
            self.title_bar.refresh_theme()
        self.title_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {theme.TEXT_SECONDARY}; background: transparent;"
        )
        self.sidebar_shell.setStyleSheet(theme.main_window_stylesheet())
        if hasattr(self, "dashboard_page"):
            self.dashboard_page.setStyleSheet(theme.main_window_stylesheet())
        self.footer_status_block.setStyleSheet(
            f"QFrame#AgentStatusCard {{ background: {theme.current_palette().footer_block_bg}; "
            f"border: 1px solid {theme.current_palette().footer_block_border}; border-radius: 16px; }}"
        )
        self.agent_footer_label.setStyleSheet(
            f"color: {theme.current_palette().footer_label}; font-weight: 700; background: transparent;"
        )
        self.agent_footer_meta.setStyleSheet(
            f"color: {theme.current_palette().footer_label_muted}; background: transparent;"
        )
        self.chat_panel.setStyleSheet(theme.chat_panel_stylesheet())
        if hasattr(self.chat_panel, "refresh_theme"):
            self.chat_panel.refresh_theme()
        self.profile_sidebar.setStyleSheet(theme.profile_sidebar_stylesheet())
        self.tickets_sidebar.setStyleSheet(theme.chat_panel_stylesheet() + theme.profile_sidebar_stylesheet())
        if hasattr(self.tickets_sidebar, "refresh_theme"):
            self.tickets_sidebar.refresh_theme()
        self.ticket_create_page.setStyleSheet(theme.chat_panel_stylesheet() + theme.profile_sidebar_stylesheet())
        if hasattr(self.ticket_create_page, "refresh_theme"):
            self.ticket_create_page.refresh_theme()
        theme.apply_agent_dialog_theme(self.settings_page)
        self._apply_settings_page_theme()
        self._render_connection_status()
        self._render_update_status()
        self._refresh_sidebar_labels()
        self._set_sidebar_selection_state(
            dashboard=self._active_sidebar_view == "dashboard",
            tickets=self._active_sidebar_view == "tickets",
            settings=self._active_sidebar_view == "settings",
            profile=self._active_sidebar_view == "profile",
        )

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
                    "theme_mode": str(self.theme_mode_combo.currentData() or "light"),
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

    def _on_theme_mode_changed(self, *_args) -> None:
        if self._theme_combo_sync_in_progress:
            return
        self._preview_theme_mode(str(self.theme_mode_combo.currentData() or "light"))
        self._on_settings_field_changed()

    async def _async_ui_request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        timeout_sec: float = 10,
    ) -> Dict[str, Any]:
        url = self._settings_api_url(path)
        timeout = aiohttp.ClientTimeout(total=timeout_sec)
        kw: Dict[str, Any] = {}
        if payload is not None and method.upper() != "GET":
            kw["json"] = payload
        try:
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
        except asyncio.TimeoutError as exc:
            logger.error(f"Таймаут UI-запроса: method={method} path={path} timeout={timeout_sec}s")
            raise RuntimeError(f"Локальный UI-мост не ответил за {timeout_sec:.0f} сек.") from exc

    def _on_refresh_runtime_clicked(self) -> None:
        asyncio.create_task(self._async_load_runtime_diagnostics())

    def _queue_runtime_status_refresh(self, *, update_panel: bool) -> None:
        if not self._bridge_connected or self._runtime_status_refresh_in_flight:
            return
        asyncio.create_task(self._async_refresh_runtime_snapshot(update_panel=update_panel))

    def _schedule_update_refresh_burst(self) -> None:
        for delay_ms in (400, 1200, 2500, 5000, 9000):
            QTimer.singleShot(delay_ms, lambda _delay=delay_ms: self._queue_runtime_status_refresh(update_panel=False))

    def _render_update_status(self) -> None:
        snapshot = self._update_status_snapshot or {}
        version = str(snapshot.get("agent_version") or AGENT_VERSION)
        is_release = bool(snapshot.get("is_release"))
        update_available = bool(snapshot.get("update_available"))
        recommended_version = str(snapshot.get("recommended_version") or "").strip()
        comparison = str(snapshot.get("comparison") or "unknown").strip()
        recommendation_source = str(snapshot.get("recommendation_source") or "none").strip()
        assigned_rollout = snapshot.get("assigned_rollout") if isinstance(snapshot.get("assigned_rollout"), dict) else None
        assigned_version = str((assigned_rollout or {}).get("version") or "").strip()
        pending_version = str(snapshot.get("pending_update_version") or "").strip()
        request_state = str(snapshot.get("update_request_state") or "").strip().lower()
        request_version = str(snapshot.get("update_request_version") or pending_version or recommended_version).strip()
        request_operation_id = str(snapshot.get("update_request_operation_id") or "").strip()

        version_text = f"Агент v{version}"
        if not is_release:
            version_text = f"{version_text} • test build"
        self.agent_footer_label.setText(self._repair_text(version_text))
        button_text = ""
        button_enabled = False
        meta_text = "Релиз актуален" if is_release else "Подключён тестовый билд"
        if request_state == "pending_restart" and request_version:
            button_text = f"Готовим {request_version}"
            meta_text = f"Пакет {request_version} уже загружен, ожидается перезапуск агента"
        elif request_state == "requested" and request_version:
            button_text = f"Ждём {request_version}"
            meta_text = f"Ожидаем доставку команды обновления до {request_version}"
        elif request_state == "requesting" and request_version:
            button_text = f"Запрашиваем {request_version}"
            meta_text = f"Отправляем запрос на обновление до {request_version}"
        elif update_available and recommended_version:
            if comparison == "recommended_release_is_older":
                button_text = f"Откатить до {recommended_version}"
            elif recommendation_source == "assigned_rollout":
                button_text = f"Привести к {recommended_version}"
            else:
                button_text = f"Обновить до {recommended_version}"
            button_enabled = True
            target_version = assigned_version or recommended_version
            meta_text = f"Доступно действие для версии {target_version or version}"

        if request_operation_id and request_state in {"requested", "pending_restart"}:
            meta_text = f"{meta_text} (op {request_operation_id})"

        self.update_agent_btn.setText(self._repair_text(button_text))
        self.update_agent_btn.setEnabled(button_enabled)
        if button_text:
            self.update_agent_btn.show()
        else:
            self.update_agent_btn.hide()
        self.agent_footer_meta.setText(self._repair_text(meta_text))
        return

        if update_available and recommended_version:
            if comparison == "recommended_release_is_older":
                button_text = f"Откатить до {recommended_version}"
            elif recommendation_source == "assigned_rollout":
                button_text = f"Привести к {recommended_version}"
            else:
                button_text = f"Обновить до {recommended_version}"
            self.update_agent_btn.setText(self._repair_text(button_text))
            self.update_agent_btn.setEnabled(True)
        else:
            self.update_agent_btn.setText("")
            self.update_agent_btn.setEnabled(False)

        target_version = assigned_version or recommended_version
        if self.update_agent_btn.text():
            self.update_agent_btn.show()
            self.agent_footer_meta.setText(
                self._repair_text(f"Доступно действие для версии {target_version or version}")
            )
        else:
            self.update_agent_btn.hide()
            self.agent_footer_meta.setText(
                self._repair_text("Релиз актуален" if is_release else "Подключён тестовый билд")
            )

    def _apply_runtime_status_snapshot(self, runtime: Dict[str, Any], *, update_panel: bool) -> None:
        self._update_status_snapshot = {
            "agent_version": runtime.get("agent_version", AGENT_VERSION),
            "is_release": runtime.get("is_release"),
            "release_channel": runtime.get("release_channel"),
            "update_available": runtime.get("update_available"),
            "recommended_version": runtime.get("recommended_version"),
            "recommended_channel": runtime.get("recommended_channel"),
            "recommended_reason": runtime.get("recommended_reason"),
            "recommended_build": runtime.get("recommended_build"),
            "comparison": runtime.get("comparison"),
            "recommendation_source": runtime.get("recommendation_source"),
            "assigned_rollout": runtime.get("assigned_rollout"),
            "update_status_error": runtime.get("update_status_error"),
            "update_checked_at": runtime.get("update_checked_at"),
            "pending_update_version": runtime.get("pending_update_version"),
            "pending_update_operation_id": runtime.get("pending_update_operation_id"),
            "pending_update_received_at": runtime.get("pending_update_received_at"),
            "pending_update_reason": runtime.get("pending_update_reason"),
            "update_request_state": runtime.get("update_request_state"),
            "update_request_version": runtime.get("update_request_version"),
            "update_request_operation_id": runtime.get("update_request_operation_id"),
            "update_request_requested_at": runtime.get("update_request_requested_at"),
            "update_request_reason": runtime.get("update_request_reason"),
        }
        self._render_update_status()

        if not update_panel:
            return

        log_runtime = runtime.get("log_runtime") if isinstance(runtime, dict) else {}
        self._runtime_logs_dir = str(runtime.get("logs_dir") or "") if isinstance(runtime, dict) else None
        release_line = f"Release: {'yes' if runtime.get('is_release') else 'no'} / {runtime.get('release_channel', '—')}"
        recommended_line = f"Recommended: {runtime.get('recommended_version') or '—'} / {runtime.get('recommended_channel') or '—'}"
        if runtime.get("recommended_reason"):
            recommended_line = f"{recommended_line} / {runtime.get('recommended_reason')}"
        if runtime.get("comparison"):
            recommended_line = f"{recommended_line} / {runtime.get('comparison')}"
        rollout = runtime.get("assigned_rollout") if isinstance(runtime.get("assigned_rollout"), dict) else {}
        rollout_line = (
            f"Server rollout: {rollout.get('target', '—')} / {rollout.get('channel', '—')} / {rollout.get('version', '—')}"
            if rollout else "Server rollout: —"
        )
        summary_lines = [
            f"Device ID: {runtime.get('device_id', '—')}",
            f"Agent: {runtime.get('agent_version', AGENT_VERSION)}",
            f"Connection: {runtime.get('connection_state', '—')} / {runtime.get('connection_detail', '')}".strip(),
            release_line,
            f"Update available: {'yes' if runtime.get('update_available') else 'no'}",
            recommended_line,
            f"Recommendation source: {runtime.get('recommendation_source', '—')}",
            rollout_line,
            f"Changed at: {runtime.get('connection_changed_at', '—')}",
            f"Uptime: {runtime.get('uptime_seconds', '—')} сек",
            f"UI bridge: {'up' if runtime.get('ui_bridge_running') else 'down'}",
            f"Subscribers: {runtime.get('event_bus_subscribers', 0)}",
            f"Log level: {log_runtime.get('level', '—')} (console {log_runtime.get('console_level', '—')})",
            f"Log file: {log_runtime.get('file', '—')}",
        ]
        if runtime.get("pending_update_version"):
            summary_lines.append(
                f"Pending update: {runtime.get('pending_update_version')} / op {runtime.get('pending_update_operation_id') or '—'}"
            )
        if runtime.get("pending_update_received_at"):
            summary_lines.append(f"Pending received: {runtime.get('pending_update_received_at')}")
        if runtime.get("pending_update_reason"):
            summary_lines.append(f"Pending reason: {runtime.get('pending_update_reason')}")
        if runtime.get("last_applied_update_version"):
            summary_lines.append(
                f"Last applied: {runtime.get('last_applied_update_version')} at {runtime.get('last_applied_update_at') or '—'}"
            )
        if runtime.get("last_failed_update_version"):
            failure_line = (
                f"Last failed: {runtime.get('last_failed_update_version')} at {runtime.get('last_failed_update_at') or '—'}"
            )
            if runtime.get("last_failed_update_reason"):
                failure_line = f"{failure_line} / {runtime.get('last_failed_update_reason')}"
            summary_lines.append(failure_line)
        if runtime.get("last_failed_update_message"):
            summary_lines.append(f"Last failed message: {runtime.get('last_failed_update_message')}")
        if runtime.get("update_checked_at"):
            summary_lines.append(f"Update checked: {runtime.get('update_checked_at')}")
        if runtime.get("update_status_error"):
            summary_lines.append(f"Update error: {runtime.get('update_status_error')}")
        self.runtime_status_label.setText(self._repair_text("\n".join(summary_lines)))

    async def _async_refresh_runtime_snapshot(self, *, update_panel: bool) -> Dict[str, Any]:
        self._runtime_status_refresh_in_flight = True
        try:
            runtime = await self._async_ui_request("GET", "/ui/agent/status")
            self._apply_runtime_status_snapshot(runtime, update_panel=update_panel)
            return runtime
        finally:
            self._runtime_status_refresh_in_flight = False

    async def _async_load_runtime_diagnostics(self) -> None:
        try:
            status_data = await self._async_refresh_runtime_snapshot(update_panel=True)
            logs_data = await self._async_ui_request("GET", "/ui/agent/logs?source=agent&lines=120")
        except Exception as e:
            self.runtime_status_label.setText(self._repair_text(f"Ошибка диагностики: {e}"))
            self.runtime_logs_view.setPlainText("")
            return

        self.runtime_logs_view.setPlainText(str(logs_data.get("text") or ""))

    def _on_trigger_update_clicked(self) -> None:
        asyncio.create_task(self._async_trigger_update())

    async def _async_trigger_update(self) -> None:
        self.update_agent_btn.setEnabled(False)
        requested_version = str(self._update_status_snapshot.get("recommended_version") or "").strip()
        if requested_version:
            self._update_status_snapshot["update_request_state"] = "requesting"
            self._update_status_snapshot["update_request_version"] = requested_version
            self._render_update_status()
        try:
            response = await self._async_ui_request("POST", "/ui/agent/update", payload={}, timeout_sec=30)
            if response.get("status") == "accepted":
                recommended = response.get("recommendation") or {}
                server_response = response.get("server_response") if isinstance(response.get("server_response"), dict) else {}
                resolved_version = str(recommended.get("recommended_version") or "").strip()
                version = resolved_version or "новой версии"
                if version != "новой версии":
                    self._update_status_snapshot["update_available"] = False
                    self._update_status_snapshot["update_request_state"] = "requested"
                    self._update_status_snapshot["update_request_version"] = version
                    self._update_status_snapshot["update_request_operation_id"] = server_response.get("operation_id")
                    self._render_update_status()
                self._schedule_update_refresh_burst()
                version = recommended.get("recommended_version") or "новой версии"
                self._show_nonblocking_message(
                    "Обновление",
                    f"Запрос на обновление до {version} отправлен.",
                    QMessageBox.Icon.Information,
                )
            else:
                self._update_status_snapshot.pop("update_request_state", None)
                self._update_status_snapshot.pop("update_request_version", None)
                self._update_status_snapshot.pop("update_request_operation_id", None)
                self._render_update_status()
                self._show_nonblocking_message(
                    "Обновление",
                    str(response.get("message") or "Рекомендованное обновление сейчас недоступно."),
                    QMessageBox.Icon.Information,
                )
        except Exception as e:
            logger.error(f"Ошибка запуска update: {e}")
            self._show_nonblocking_message(
                "Ошибка обновления",
                f"Не удалось запросить обновление:\n{e}",
                QMessageBox.Icon.Critical,
            )
        finally:
            try:
                await self._async_refresh_runtime_snapshot(update_panel=False)
            except Exception:
                pass

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
        core_enabled_modules = settings.get("core_enabled_modules", [])
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
        theme_idx = self.theme_mode_combo.findData(str(ui_cfg.get("theme_mode", "light")))
        self._theme_combo_sync_in_progress = True
        self.theme_mode_combo.blockSignals(True)
        self.theme_mode_combo.setCurrentIndex(theme_idx if theme_idx >= 0 else 0)
        self.theme_mode_combo.blockSignals(False)
        self._theme_combo_sync_in_progress = False
        self.logging_level_combo.setCurrentText(str(logging_cfg.get("level", "INFO")))
        self.logging_console_level_combo.setCurrentText(str(logging_cfg.get("console_level", "INFO")))
        self.logging_rotation_input.setText(str(logging_cfg.get("rotation", "20 MB")))
        self.logging_retention_input.setText(str(logging_cfg.get("retention", "14 days")))
        self.logging_compression_input.setText(str(logging_cfg.get("compression", "zip")))
        self.data_dir_input.setText(str(paths.get("data_dir", "")))
        self.core_modules_label.setText(", ".join(core_enabled_modules if isinstance(core_enabled_modules, list) else []))
        self.enabled_modules_input.setText(", ".join(enabled_modules if isinstance(enabled_modules, list) else []))
        self.installed_modules_label.setText(self._repair_text(self._format_installed_modules_text(installed_modules)))
        self.allow_remote_code_checkbox.setChecked(bool(security.get("allow_remote_code", False)))
        self.token_input.clear()
        self.clear_token_checkbox.setChecked(False)

        token_masked = auth.get("token_masked") or self._repair_text("нет")
        self.token_hint_label.setText(self._repair_text(f"Текущий токен: {token_masked}"))
        self.config_path_label.setText(str(meta.get("config_path", "—")))
        self._runtime_logs_dir = None
        self._repair_widget_texts(self.settings_page)
        self._apply_settings_page_theme()

        self._settings_snapshot = self._collect_settings_payload(include_auth=False).get("settings", {})
        self._settings_form_loaded = True
        self._on_settings_field_changed()

    def _load_registration_profile_to_form(self) -> None:
        try:
            profile = UserProfileManager().load()
        except Exception as exc:
            logger.warning(f"[ui] failed to load registration profile: {exc}")
            profile = {}
        self.registration_status_label.setText(str(profile.get("registration_status") or "unregistered"))
        self.registration_form_widget.set_form(
            self._registration_form_def,
            values=profile,
            registry_options=self._registration_registry_options,
        )
        api_url = self.api_url_input.text().strip() if hasattr(self, "api_url_input") else ""
        if api_url:
            self._apply_runtime_api_url(api_url)
        self._spawn_gui_task(self._async_load_registration_form(), name="registration.load_form")

    def _apply_registration_form_payload(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        form = payload.get("form")
        if isinstance(form, dict):
            self._registration_form_def = form
        registry_options = payload.get("registry_options")
        if isinstance(registry_options, dict):
            self._registration_registry_options = registry_options
        manager = UserProfileManager()
        profile = manager.load()
        registration = payload.get("registration") if isinstance(payload.get("registration"), dict) else {}
        if registration:
            profile["registration_status"] = str(registration.get("status") or profile.get("registration_status") or "unknown")
            pending_claim = registration.get("pending_claim") if isinstance(registration.get("pending_claim"), dict) else {}
            pending_claim_id = registration.get("pending_claim_id") or pending_claim.get("claim_id")
            if pending_claim_id:
                profile["last_claim_id"] = str(pending_claim_id)
            profile = manager.save(profile)
        self.registration_status_label.setText(str(profile.get("registration_status") or "unregistered"))
        self.registration_form_widget.set_form(
            self._registration_form_def,
            values=profile,
            registry_options=self._registration_registry_options,
        )

    async def _async_load_registration_form(self) -> None:
        try:
            payload = await self.chat_panel.ticket_client.get_registration_form()
        except Exception as exc:
            logger.info(f"[ui] registration form unavailable, using local fallback: {exc}")
            return
        if isinstance(payload, dict) and payload.get("status") == "error":
            logger.info(f"[ui] registration form unavailable: {payload.get('http_status') or payload.get('error')}")
            return
        self._apply_registration_form_payload(payload)

    def _collect_registration_profile_from_form(self) -> dict:
        try:
            current_profile = UserProfileManager().load()
        except Exception:
            current_profile = {}
        profile = self.registration_form_widget.values(visible_only=True)
        profile["relationship_type"] = str(profile.get("relationship_type") or "primary_user")
        profile["is_shared_device"] = bool(profile.get("is_shared_device") or profile["relationship_type"] == "shared_user")
        for key in ("last_claim_id", "last_submitted_at", "registration_status"):
            if current_profile.get(key):
                profile[key] = current_profile[key]
        return profile

    def _validate_registration_form(self) -> bool:
        missing = self.registration_form_widget.validate_required_fields(show_feedback=True)
        if missing:
            self._set_registration_entry_status("Заполните обязательные поля регистрации: " + ", ".join(missing), error=True)
            return False
        return True

    def _on_save_registration_profile_clicked(self) -> None:
        if not self._validate_registration_form():
            return
        profile = UserProfileManager().save(self._collect_registration_profile_from_form())
        self.registration_status_label.setText(str(profile.get("registration_status") or "local"))
        self._set_registration_entry_status("Профиль регистрации сохранён локально.", error=False)

    def _on_refresh_registration_form_clicked(self) -> None:
        self._spawn_gui_task(self._async_load_registration_form(), name="registration.refresh_form")

    def _on_submit_registration_profile_clicked(self) -> None:
        self._spawn_gui_task(self._async_submit_registration_profile(), name="registration.submit_profile")

    async def _async_submit_registration_profile(self) -> None:
        if not self._validate_registration_form():
            return
        profile = UserProfileManager().save(self._collect_registration_profile_from_form())
        result = await self.chat_panel.ticket_client.submit_registration_profile(profile, user_confirmed=False)
        registration = result.get("registration") if isinstance(result, dict) else {}
        if not isinstance(registration, dict):
            raise RuntimeError("Некорректный ответ регистрации")
        profile["last_claim_id"] = registration.get("claim_id") or profile.get("last_claim_id")
        profile["registration_status"] = registration.get("status") or profile.get("registration_status")
        profile["last_submitted_at"] = datetime.now(timezone.utc).isoformat()
        saved = UserProfileManager().save(profile)
        await self._save_registration_pending_account_session(saved, registration)
        self.registration_status_label.setText(str(saved.get("registration_status") or "unknown"))
        self._set_registration_entry_status("Профиль регистрации отправлен.", error=False)
        self._select_sidebar_view("account_gate", expand=True)

    def _on_confirm_registration_claim_clicked(self) -> None:
        self._spawn_gui_task(self._async_confirm_registration_claim(), name="registration.confirm_claim")

    async def _async_confirm_registration_claim(self) -> None:
        manager = UserProfileManager()
        profile = manager.load()
        claim_id = str(profile.get("last_claim_id") or "").strip()
        if not claim_id:
            if not self._validate_registration_form():
                return
            profile = manager.save(self._collect_registration_profile_from_form())
            result = await self.chat_panel.ticket_client.submit_registration_profile(profile, user_confirmed=True)
            registration = result.get("registration") if isinstance(result, dict) else {}
            if isinstance(registration, dict):
                profile["last_claim_id"] = registration.get("claim_id") or profile.get("last_claim_id")
                profile["registration_status"] = registration.get("status") or profile.get("registration_status")
                profile["last_submitted_at"] = datetime.now(timezone.utc).isoformat()
                saved = manager.save(profile)
                await self._save_registration_pending_account_session(saved, registration)
                self.registration_status_label.setText(str(saved.get("registration_status") or "unknown"))
                self._set_registration_entry_status("Данные регистрации отправлены и подтверждены.", error=False)
                self._select_sidebar_view("account_gate", expand=True)
            else:
                self._set_registration_entry_status("Некорректный ответ регистрации.", error=True)
            return
        result = await self.chat_panel.ticket_client.confirm_registration_claim(claim_id)
        registration = result.get("registration") if isinstance(result, dict) else {}
        if isinstance(registration, dict):
            profile["registration_status"] = registration.get("status") or profile.get("registration_status")
            saved = manager.save(profile)
            await self._save_registration_pending_account_session(saved, registration)
            self.registration_status_label.setText(str(saved.get("registration_status") or "unknown"))
        self._set_registration_entry_status("Данные регистрации подтверждены.", error=False)
        self._select_sidebar_view("account_gate", expand=True)

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
            requires_restart = bool(result.get("requires_restart"))
            changed_keys = result.get("changed_keys", [])

            settings_payload = payload.get("settings", {})
            api_url = settings_payload.get("server", {}).get("api_url")
            if api_url:
                self._apply_runtime_api_url(str(api_url))
            ui_payload = settings_payload.get("ui", {})
            self._preview_theme_mode(str(ui_payload.get("theme_mode") or "light"))

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
            if config_changed and requires_restart and not request_restart:
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
            text = "Офлайн"
            meta = "Локальный мост недоступен"
            bg = theme.current_palette().status_offline_bg
            fg = theme.current_palette().status_offline_fg
            dot_name = "StatusDot"
        elif self._server_connection_state == "connected":
            text = "Онлайн"
            meta = "Сервер доступен"
            bg = theme.current_palette().status_online_bg
            fg = theme.current_palette().status_online_fg
            dot_name = "StatusDotOnline"
        elif self._server_connection_state in {"connecting", "authorizing", "starting"}:
            text = "Подключение..."
            meta = "Идёт подключение"
            bg = theme.current_palette().status_busy_bg
            fg = theme.current_palette().status_busy_fg
            dot_name = "StatusDotBusy"
        elif self._server_connection_state == "auth_required":
            text = "Офлайн"
            meta = "Нужен токен"
            bg = theme.current_palette().status_offline_bg
            fg = theme.current_palette().status_offline_fg
            dot_name = "StatusDot"
        elif self._server_connection_state in {"rejected", "error"}:
            text = "Ошибка подключения"
            meta = "Доступ отклонён"
            bg = theme.current_palette().status_offline_bg
            fg = theme.current_palette().danger_fg
            dot_name = "StatusDot"
        else:
            text = "Офлайн"
            meta = "Нет соединения с сервером"
            bg = theme.current_palette().status_offline_bg
            fg = theme.current_palette().status_offline_fg
            dot_name = "StatusDot"

        if self._server_connection_detail:
            meta = f"{meta}: {self._server_connection_detail}"

        normalized_state = normalize_connection_state(self._bridge_connected, self._server_connection_state)
        accessible_detail = connection_description(
            bridge_connected=self._bridge_connected,
            server_state=self._server_connection_state,
            detail=self._server_connection_detail or meta,
        )
        self.connection_status_btn.setText(self._repair_text(text))
        set_uia_metadata(
            self.connection_status_btn,
            name=f"agent.connection.state {normalized_state}",
            description=accessible_detail,
        )
        self.connection_status_btn.setStyleSheet(
            f"padding: 6px 14px; border-radius: 999px; background: {bg}; color: {fg}; "
            f"font-weight: 800; border: 1px solid {bg};"
        )
        self.connection_status_btn.setToolTip(self._repair_text("Открыть настройки подключения"))
        if hasattr(self, "connection_status_dot"):
            self.connection_status_dot.setObjectName(dot_name)
            self.connection_status_dot.setStyleSheet(
                f"min-width: 12px; max-width: 12px; min-height: 12px; max-height: 12px; "
                f"border-radius: 6px; background: {fg};"
            )
        if not self.update_agent_btn.isVisible():
            self.agent_footer_meta.setText(self._repair_text(meta))
        set_uia_metadata(
            self.agent_footer_meta,
            name="agent.connection.detail",
            description=f"id=agent.connection.detail; {accessible_detail}",
        )
        self._refresh_dashboard()

    def set_bridge_connected(self, connected: bool) -> None:
        self._bridge_connected = connected
        if not connected:
            self._server_connection_detail = ""
        self._render_connection_status()

    def set_connection_state(self, state: str, detail: str = "") -> None:
        self._server_connection_state = (state or "disconnected").strip().lower()
        self._server_connection_detail = detail.strip()
        self._render_connection_status()
        if self._bridge_connected and self._server_connection_state == "connected":
            QTimer.singleShot(400, lambda: self._queue_runtime_status_refresh(update_panel=False))

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
            detail = str(data.get("message") or data.get("detail") or "подключение отклонено")
            self.set_connection_state("rejected", detail)
            return
        if event_type == "remote_assist_request":
            self._handle_remote_assist_request(data)
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

    def _handle_remote_assist_request(self, data: dict) -> None:
        session_id = str(data.get("session_id") or "").strip()
        if not session_id:
            logger.warning("Remote Assist request received without session_id")
            return
        if str(data.get("consent_status") or "").strip().lower() == "approved":
            existing = self._remote_assist_threads.get(session_id)
            if existing and existing.isRunning():
                return
            self._add_log(f"remote_assist | approved consent received | {session_id[:8]}", "info")
            self._spawn_gui_task(
                self._post_remote_assist_decision(session_id, approve=True),
                name="remote_assist.start_after_consent",
            )
            return
        dialog_key = f"remote_assist:{session_id}"
        if dialog_key in self.open_dialogs:
            logger.debug(f"Remote Assist dialog already open for session_id={session_id}")
            return
        self.open_dialogs.add(dialog_key)
        dialog = RemoteAssistConsentDialog(data, self)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self._remote_assist_dialogs[session_id] = dialog
        logger.info(f"Remote Assist consent dialog opened for session_id={session_id}")

        def cleanup() -> None:
            self.open_dialogs.discard(dialog_key)
            self._remote_assist_dialogs.pop(session_id, None)

        def approve() -> None:
            self._spawn_gui_task(
                self._post_remote_assist_decision(session_id, approve=True),
                name="remote_assist.approve",
            )

        def deny() -> None:
            self._spawn_gui_task(
                self._post_remote_assist_decision(session_id, approve=False),
                name="remote_assist.deny",
            )

        dialog.approved.connect(approve)
        dialog.denied.connect(deny)
        dialog.finished.connect(lambda _result: cleanup())
        dialog.open()
        dialog.raise_()
        dialog.activateWindow()

    async def _post_remote_assist_decision(self, session_id: str, *, approve: bool) -> None:
        if not self.auth_token:
            self._add_log("remote_assist | auth token missing", "error")
            return
        api_url = get_config().server.api_url.rstrip("/")
        action = "approve" if approve else "deny"
        url = f"{api_url}/remote-assist/{session_id}/{action}"
        payload = {} if approve else {"reason": "user_denied"}
        response_data: dict = {}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers={"Authorization": f"Bearer {self.auth_token}"}) as response:
                    data = await response.json(content_type=None)
                    if response.status < 200 or response.status >= 300:
                        self._add_log(
                            f"remote_assist | {action} failed | {response.status} | {data.get('error_code') or data.get('error')}",
                            "error",
                        )
                        return
                    response_data = data.get("data") if isinstance(data.get("data"), dict) else {}
            self._add_log(
                "Удалённая помощь разрешена" if approve else "Удалённая помощь отклонена",
                "success" if approve else "warning",
            )
            if approve:
                self._start_remote_assist_session(session_id, response_data)
        except Exception as exc:
            logger.exception(f"Remote Assist {action} failed: {exc}")
            self._add_log(f"remote_assist | {action} failed | {exc}", "error")

    def _start_remote_assist_session(self, session_id: str, data: dict) -> None:
        signaling_url = str(data.get("agent_signaling_url") or "").strip()
        token = str(data.get("agent_token") or "").strip()
        if not signaling_url or not token:
            self._add_log("remote_assist | signaling info missing", "error")
            return
        existing = self._remote_assist_threads.get(session_id)
        if existing and existing.isRunning():
            return
        thread = create_remote_assist_thread(
            signaling_url=signaling_url,
            token=token,
            ice_servers=data.get("ice_servers") if isinstance(data.get("ice_servers"), list) else [],
            mode=str(data.get("mode") or "view_only"),
            media=data.get("media") if isinstance(data.get("media"), dict) else {},
            features=data.get("features") if isinstance(data.get("features"), dict) else {},
            parent=self,
        )
        thread.failed.connect(lambda message, sid=session_id: self._handle_remote_assist_thread_failed(sid, message))
        thread.state_changed.connect(lambda state, sid=session_id: self._handle_remote_assist_state_changed(sid, state))
        thread.ended.connect(lambda sid=session_id: self._remote_assist_threads.pop(sid, None))
        thread.ended.connect(lambda sid=session_id: self._hide_remote_assist_banner(sid))
        self._remote_assist_threads[session_id] = thread
        self._show_remote_assist_banner(session_id, mode=str(data.get("mode") or "view_only"), state="connecting")
        thread.start()

    def _handle_remote_assist_state_changed(self, session_id: str, state: str) -> None:
        normalized = (state or "").strip().lower()
        label = self._remote_assist_banner_labels.get(session_id)
        if label is None:
            return
        mode = self._remote_assist_modes.get(session_id, "view_only")
        if normalized in {"connected", "completed"}:
            if mode == "elevated_admin":
                label.setText("Административная удалённая помощь активна. Специалист видит экран и может управлять админскими окнами после UAC.")
            elif mode == "interactive_control":
                label.setText("Удалённая помощь активна. Специалист видит экран и может управлять мышью/клавиатурой.")
            else:
                label.setText("Удалённая помощь активна. Специалист видит ваш экран.")
        elif normalized in {"failed", "closed", "disconnected"}:
            label.setText("Удалённая помощь прервана. Подключение не установлено.")
        else:
            label.setText("Подключение удалённой помощи. Специалист пока не видит экран.")

    def _handle_remote_assist_thread_failed(self, session_id: str, message: str) -> None:
        self._add_log(f"remote_assist | failed | {session_id[:8]} | {message}", "error")
        self._spawn_gui_task(
            self._fail_remote_assist_from_agent(session_id, message),
            name="remote_assist.fail",
        )

    def _show_remote_assist_banner(self, session_id: str, *, mode: str = "view_only", state: str = "active") -> None:
        self._hide_remote_assist_banner(session_id)
        banner = QWidget()
        banner.setObjectName("RemoteAssistActiveBanner")
        banner.setWindowTitle("Maria Agent remote assist")
        banner.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        banner.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        banner.setStyleSheet("background-color: #111827; color: white; border: 1px solid #2563eb; border-radius: 10px;")
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(12, 10, 12, 10)
        if state != "active":
            label = QLabel("Подключение удалённой помощи. Специалист пока не видит экран.")
        elif mode == "elevated_admin":
            label = QLabel("Административная удалённая помощь активна. Специалист видит экран и может управлять админскими окнами после UAC.")
        elif mode == "interactive_control":
            label = QLabel("Удалённая помощь активна. Специалист видит экран и может управлять мышью/клавиатурой.")
        else:
            label = QLabel("Удалённая помощь активна. Специалист видит ваш экран.")
        stop_button = QPushButton("Завершить доступ")
        stop_button.setStyleSheet("background-color: #b91c1c; color: white; font-weight: 600; padding: 6px 10px; border-radius: 6px;")
        stop_button.clicked.connect(lambda: self._spawn_gui_task(self._end_remote_assist_from_user(session_id), name="remote_assist.user_end"))
        layout.addWidget(label)
        layout.addWidget(stop_button)
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            banner.adjustSize()
            banner.move(geom.x() + 24, geom.y() + 24)
        banner.show()
        self._remote_assist_banners[session_id] = banner
        self._remote_assist_banner_labels[session_id] = label
        self._remote_assist_modes[session_id] = mode

    def _hide_remote_assist_banner(self, session_id: str) -> None:
        banner = self._remote_assist_banners.pop(session_id, None)
        self._remote_assist_banner_labels.pop(session_id, None)
        self._remote_assist_modes.pop(session_id, None)
        if banner:
            banner.close()
            banner.deleteLater()

    async def _end_remote_assist_from_user(self, session_id: str) -> None:
        thread = self._remote_assist_threads.get(session_id)
        if thread:
            thread.stop(reason="user_finished", notify_peer=True)
        if not self.auth_token:
            return
        api_url = get_config().server.api_url.rstrip("/")
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{api_url}/remote-assist/{session_id}/end",
                    json={"reason": "user_finished"},
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                )
        except Exception as exc:
            logger.debug(f"Remote Assist user end API call failed: {exc}")

    async def _fail_remote_assist_from_agent(self, session_id: str, message: str) -> None:
        if not self.auth_token:
            return
        api_url = get_config().server.api_url.rstrip("/")
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{api_url}/remote-assist/{session_id}/fail",
                    json={"error_code": "WEBRTC_FAILED", "error_message": message[:500]},
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                )
        except Exception as exc:
            logger.debug(f"Remote Assist fail API call failed: {exc}")
    
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
        widget.setObjectName("RecordingStopOverlay")
        widget.setWindowTitle("Maria Agent recording control")
        widget.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
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
        try:
            if hasattr(self, "_user_consent_timer") and self._user_consent_timer:
                self._user_consent_timer.stop()
            self._close_user_consent_dialogs()
        except Exception as e:
            logger.debug(f"closeEvent: stop consent polling failed: {e}")
        self._hide_stop_button()
        for session_id, thread in list(self._remote_assist_threads.items()):
            try:
                thread.stop()
            except Exception:
                pass
            self._hide_remote_assist_banner(session_id)
        super().closeEvent(event)
    
    def _load_device_uuid(self):
        """Загружает device UUID из identity manager."""
        try:
            from pc_agent.core.identity import IdentityManager
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
