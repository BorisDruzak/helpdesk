from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from . import theme
from .dynamic_form_widget import DynamicFormWidget


OTHER_ACCOUNT_FORM = {
    "key": "agent_other_account_login",
    "title": "Вход в другой аккаунт",
    "fields": [
        {"key": "full_name", "label": "ФИО", "type": "text", "required": True},
        {"key": "display_name", "label": "Отображаемое имя", "type": "text", "required": False},
        {"key": "login", "label": "Логин", "type": "text", "required": True},
        {"key": "email", "label": "Email", "type": "text", "required": False},
        {"key": "phone", "label": "Телефон", "type": "text", "required": False},
        {
            "key": "reason",
            "label": "Почему входите не под зарегистрированным пользователем?",
            "type": "textarea",
            "required": True,
        },
    ],
}

TERMINAL_OTHER_ACCOUNT_REQUEST_STATUSES = {"approved", "rejected", "expired", "canceled"}


def account_gate_view_state(
    account_state: dict[str, Any] | None,
    *,
    local_session: dict[str, Any] | None = None,
    error: str | None = None,
    legacy_registration_enabled: bool | None = None,
) -> dict[str, Any]:
    if error:
        return {
            "mode": "error",
            "title": "Не удалось проверить аккаунт",
            "message": error,
            "show_register": False,
            "show_browser_register": False,
            "show_login_confirmed": False,
            "show_gui_password_login": False,
            "show_browser_login": False,
            "show_login_other": False,
            "show_confirm": False,
            "warning": None,
            "primary_account": None,
            "pending_account": None,
            "approved_other_account": None,
        }
    account_state = account_state or {}
    pending_request_status = str((local_session or {}).get("pending_login_request_status") or "").strip().lower()
    if (
        isinstance(local_session, dict)
        and local_session.get("account_mode") == "pending_other_account_request"
        and pending_request_status not in TERMINAL_OTHER_ACCOUNT_REQUEST_STATUSES
    ):
        return {
            "mode": "pending_other_account_request",
            "title": "Заявка на вход в другой аккаунт ожидает подтверждения",
            "message": "Администратор должен подтвердить вход. Можно проверить статус вручную или дождаться автоматического обновления.",
            "show_register": False,
            "show_browser_register": False,
            "show_login_confirmed": False,
            "show_gui_password_login": False,
            "show_browser_login": False,
            "show_login_other": False,
            "show_confirm": False,
            "show_check_pending_request": True,
            "warning": "pending_other_account_request",
            "primary_account": None,
            "pending_account": {
                "display_name": local_session.get("display_name") or local_session.get("full_name") or local_session.get("login"),
                "registration_status": local_session.get("pending_login_request_status") or "pending_verification",
                "login": local_session.get("login"),
                "reason": local_session.get("reason"),
            },
            "approved_other_account": None,
            "pending_request_id": local_session.get("pending_login_request_id"),
        }
    accounts = [item for item in account_state.get("accounts") or [] if isinstance(item, dict)]
    confirmed = next(
        (item for item in accounts if item.get("account_mode") == "confirmed_binding" and item.get("can_login", True)),
        None,
    )
    pending = next((item for item in accounts if item.get("account_mode") == "registration_pending"), None)
    approved_other = next(
        (
            item
            for item in accounts
            if item.get("account_mode") == "verified_other_account" and item.get("can_login", True)
        ),
        None,
    )
    registration = account_state.get("registration") if isinstance(account_state.get("registration"), dict) else {}
    mode = "unregistered"
    if confirmed:
        mode = "registered"
    elif pending or str(registration.get("status") or "") in {
        "self_reported",
        "pending_user_confirmation",
        "user_confirmed",
        "pending_admin_review",
    }:
        mode = "pending"
    warning = None
    if isinstance(local_session, dict) and local_session.get("account_mode") in {"verified_other_account", "other_account"}:
        warning = "other_account"
    has_known_account_state = bool(account_state) and isinstance(account_state.get("registration"), dict)
    can_register = bool(account_state.get("can_register"))
    if has_known_account_state and confirmed is None and mode == "unregistered":
        can_register = True
    if mode == "pending":
        can_register = False
    can_login_other = (
        confirmed is not None
        and bool(account_state.get("can_request_other_account_login") or account_state.get("can_login_other_account"))
    )
    if approved_other is not None:
        can_login_other = True
    browser_pairing_code = str(account_state.get("browser_pairing_code") or "").strip()
    return {
        "mode": mode,
        "title": {
            "registered": "Этот ПК зарегистрирован за:",
            "pending": "Регистрация ожидает подтверждения",
            "unregistered": "Привяжите это устройство через браузер",
        }.get(mode, "Проверяем регистрацию устройства..."),
        "message": str(account_state.get("message") or ""),
        "show_register": False,
        "show_browser_register": can_register and confirmed is None,
        "browser_pairing_code": browser_pairing_code,
        "show_copy_pairing_code": bool(browser_pairing_code),
        "show_login_confirmed": confirmed is not None,
        "show_gui_password_login": confirmed is not None,
        "show_browser_login": confirmed is not None,
        "show_login_other": can_login_other,
        "show_confirm": False,
        "show_check_pending_request": False,
        "warning": warning,
        "primary_account": confirmed,
        "pending_account": pending,
        "approved_other_account": approved_other,
    }


class AccountGateWidget(QFrame):
    browserLoginRequested = Signal()
    browserRegisterRequested = Signal()
    loginConfirmedRequested = Signal(dict)
    guiPasswordLoginRequested = Signal(str, str)
    loginOtherRequested = Signal(dict)
    refreshRequested = Signal()
    settingsRequested = Signal()
    checkOtherLoginRequestRequested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MainPanel")
        self._account_state: dict[str, Any] = {}
        self._local_session: dict[str, Any] = {}
        self._primary_account: dict[str, Any] | None = None
        self._approved_other_account: dict[str, Any] | None = None
        self._pending_request_id: str | None = None
        self._browser_pairing_code: str = ""
        self._showing_other_form = False
        self._pending_poll_timer = QTimer(self)
        self._pending_poll_timer.setInterval(20000)
        self._pending_poll_timer.timeout.connect(self._on_check_pending_request)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        self.title_label = QLabel("Проверяем регистрацию устройства...")
        self.title_label.setObjectName("MainTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.message_label = QLabel("")
        self.message_label.setObjectName("MainSubtitle")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        self.account_card = QFrame()
        self.account_card.setObjectName("ProfileCard")
        card_layout = QVBoxLayout(self.account_card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(4)
        self.account_name_label = QLabel("")
        self.account_name_label.setObjectName("CardTitle")
        self.account_meta_label = QLabel("")
        self.account_meta_label.setObjectName("CardMeta")
        card_layout.addWidget(self.account_name_label)
        card_layout.addWidget(self.account_meta_label)
        layout.addWidget(self.account_card)

        self.warning_label = QLabel("")
        self.warning_label.setObjectName("ProfileHint")
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)

        self.pairing_code_label = QLabel("")
        self.pairing_code_label.setObjectName("CardMeta")
        self.pairing_code_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.pairing_code_label.setWordWrap(True)
        layout.addWidget(self.pairing_code_label)

        self.gui_login_frame = QFrame()
        self.gui_login_frame.setObjectName("ProfileCard")
        gui_login_layout = QVBoxLayout(self.gui_login_frame)
        gui_login_layout.setContentsMargins(16, 14, 16, 14)
        gui_login_layout.setSpacing(8)
        self.gui_login_title_label = QLabel("Вход по логину и паролю")
        self.gui_login_title_label.setObjectName("CardTitle")
        self.gui_login_input = QLineEdit()
        self.gui_login_input.setObjectName("agent.account.gui_login")
        self.gui_login_input.setPlaceholderText("Логин")
        self.gui_password_input = QLineEdit()
        self.gui_password_input.setObjectName("agent.account.gui_password")
        self.gui_password_input.setPlaceholderText("Пароль")
        self.gui_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.gui_password_login_button = QPushButton("Войти")
        self.gui_password_login_button.setObjectName("PrimaryButton")
        self.gui_password_login_button.clicked.connect(self._on_gui_password_login)
        gui_login_layout.addWidget(self.gui_login_title_label)
        gui_login_layout.addWidget(self.gui_login_input)
        gui_login_layout.addWidget(self.gui_password_input)
        gui_login_layout.addWidget(self.gui_password_login_button)
        layout.addWidget(self.gui_login_frame)

        self.other_form = DynamicFormWidget()
        self.other_form.set_form(OTHER_ACCOUNT_FORM)
        layout.addWidget(self.other_form)

        actions = QHBoxLayout()
        self.browser_login_button = QPushButton("Войти через браузер")
        self.browser_login_button.setObjectName("PrimaryButton")
        self.browser_login_button.clicked.connect(self.browserLoginRequested.emit)
        self.login_button = QPushButton("Войти")
        self.login_button.setObjectName("SecondaryButton")
        self.login_button.clicked.connect(self._on_login_confirmed)
        self.other_button = QPushButton("Войти в другой аккаунт")
        self.other_button.setObjectName("SecondaryButton")
        self.other_button.clicked.connect(self._on_other_clicked)
        self.browser_register_button = QPushButton("Привязать через браузер")
        self.browser_register_button.setObjectName("PrimaryButton")
        self.browser_register_button.clicked.connect(self.browserRegisterRequested.emit)
        self.copy_pairing_code_button = QPushButton("Скопировать код")
        self.copy_pairing_code_button.setObjectName("SecondaryButton")
        self.copy_pairing_code_button.clicked.connect(self._on_copy_pairing_code)
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setObjectName("SecondaryButton")
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.settings_button = QPushButton("Настройки")
        self.settings_button.setObjectName("SecondaryButton")
        self.settings_button.clicked.connect(self.settingsRequested.emit)
        self.check_request_button = QPushButton("Проверить статус заявки")
        self.check_request_button.setObjectName("SecondaryButton")
        self.check_request_button.clicked.connect(self._on_check_pending_request)
        for button in (
            self.browser_login_button,
            self.login_button,
            self.other_button,
            self.browser_register_button,
            self.copy_pairing_code_button,
            self.check_request_button,
            self.refresh_button,
            self.settings_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)
        self.render_loading()

    def render_loading(self) -> None:
        self.render({}, error=None)
        self.title_label.setText("Проверяем регистрацию устройства...")
        self.account_card.hide()
        self.gui_login_frame.hide()
        self.other_form.hide()

    def _on_check_pending_request(self) -> None:
        if self._pending_request_id:
            self.checkOtherLoginRequestRequested.emit(self._pending_request_id)
        else:
            self.refreshRequested.emit()

    def render(
        self,
        account_state: dict[str, Any] | None,
        *,
        local_session: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self._account_state = account_state or {}
        self._local_session = local_session or {}
        state = account_gate_view_state(self._account_state, local_session=self._local_session, error=error)
        self._primary_account = state.get("primary_account") if isinstance(state.get("primary_account"), dict) else None
        self._approved_other_account = (
            state.get("approved_other_account") if isinstance(state.get("approved_other_account"), dict) else None
        )
        self._pending_request_id = str(state.get("pending_request_id") or "").strip() or None
        self.title_label.setText(state["title"])
        self.message_label.setText(state.get("message") or "")
        self.message_label.setVisible(bool(self.message_label.text()))
        self._browser_pairing_code = str(state.get("browser_pairing_code") or "").strip()
        self.pairing_code_label.setVisible(bool(self._browser_pairing_code))
        self.gui_login_frame.setVisible(bool(state.get("show_gui_password_login")))
        self.pairing_code_label.setText(f"Код привязки: {self._browser_pairing_code}" if self._browser_pairing_code else "")
        account = state.get("primary_account") or state.get("pending_account")
        self.account_card.setVisible(isinstance(account, dict))
        if isinstance(account, dict):
            name = account.get("display_name") or account.get("full_name") or account.get("login") or "Аккаунт"
            self.account_name_label.setText(str(name))
            self.account_meta_label.setText(
                str(account.get("registration_status") or account.get("relationship_type") or "")
            )
        self.warning_label.setVisible(state.get("warning") == "other_account")
        self.warning_label.setText(
            "Вы вошли не под зарегистрированным пользователем этого ПК. Все обращения будут помечены."
            if state.get("warning") == "other_account"
            else ""
        )
        self.browser_login_button.setVisible(bool(state["show_browser_login"]))
        self.login_button.setVisible(bool(state["show_login_confirmed"]))
        if state.get("warning") == "pending_other_account_request":
            self.warning_label.setText("Заявка отправлена. До подтверждения вход в другой аккаунт недоступен.")
            self.warning_label.setVisible(True)
        elif state.get("warning") not in {"other_account"}:
            self.warning_label.setText("")
            self.warning_label.setVisible(False)
        if self._primary_account:
            name = self._primary_account.get("display_name") or self._primary_account.get("full_name") or "аккаунт"
            self.login_button.setText(f"Войти как {name}")
        self.other_button.setVisible(bool(state["show_login_other"]))
        if self._approved_other_account:
            name = (
                self._approved_other_account.get("display_name")
                or self._approved_other_account.get("full_name")
                or self._approved_other_account.get("login")
                or "другой аккаунт"
            )
            self.other_button.setText(f"Войти как {name}")
        elif not self._showing_other_form:
            self.other_button.setText("Войти в другой аккаунт")
        self.browser_register_button.setVisible(bool(state["show_browser_register"]))
        self.copy_pairing_code_button.setVisible(bool(state.get("show_copy_pairing_code")))
        self.check_request_button.setVisible(bool(state.get("show_check_pending_request") and self._pending_request_id))
        self.other_form.setVisible(self._showing_other_form)
        if self._pending_request_id or state.get("mode") == "pending":
            if not self._pending_poll_timer.isActive():
                self._pending_poll_timer.start()
        else:
            self._pending_poll_timer.stop()
        self.setStyleSheet(theme.main_window_stylesheet())

    def _on_login_confirmed(self) -> None:
        if self._primary_account:
            self.loginConfirmedRequested.emit(dict(self._primary_account))

    def _on_gui_password_login(self) -> None:
        login = str(self.gui_login_input.text() or "").strip()
        password = str(self.gui_password_input.text() or "")
        if not login or not password:
            self.warning_label.setText("Введите логин и пароль.")
            self.warning_label.setVisible(True)
            return
        self.gui_password_input.clear()
        self.guiPasswordLoginRequested.emit(login, password)

    def _on_other_clicked(self) -> None:
        if self._approved_other_account:
            self.loginOtherRequested.emit(dict(self._approved_other_account))
            return
        if not self._showing_other_form:
            self._showing_other_form = True
            self.other_button.setText("Продолжить")
            self.other_form.show()
            return
        missing = self.other_form.validate_required_fields(show_feedback=True)
        if missing:
            return
        self.loginOtherRequested.emit(self.other_form.values(visible_only=True))

    def _on_copy_pairing_code(self) -> None:
        if self._browser_pairing_code:
            QApplication.clipboard().setText(self._browser_pairing_code)

    def reset_other_form(self) -> None:
        self._showing_other_form = False
        self.other_button.setText("Войти в другой аккаунт")
        self.other_form.set_form(OTHER_ACCOUNT_FORM)
        self.other_form.hide()
