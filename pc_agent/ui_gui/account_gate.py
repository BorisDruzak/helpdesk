from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

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


def account_gate_view_state(
    account_state: dict[str, Any] | None,
    *,
    local_session: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    if error:
        return {
            "mode": "error",
            "title": "Не удалось проверить аккаунт",
            "message": error,
            "show_register": False,
            "show_login_confirmed": False,
            "show_login_other": False,
            "show_confirm": False,
            "warning": None,
            "primary_account": None,
            "pending_account": None,
            "approved_other_account": None,
        }
    account_state = account_state or {}
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
    if has_known_account_state and confirmed is None and mode in {"unregistered", "pending"}:
        can_register = True
    can_login_other = (
        confirmed is not None
        and bool(account_state.get("can_request_other_account_login") or account_state.get("can_login_other_account"))
    )
    if approved_other is not None:
        can_login_other = True
    return {
        "mode": mode,
        "title": {
            "registered": "Этот ПК зарегистрирован за:",
            "pending": "Регистрация ожидает подтверждения",
            "unregistered": "Для работы с обращениями нужно зарегистрироваться",
        }.get(mode, "Проверяем регистрацию устройства..."),
        "message": str(account_state.get("message") or ""),
        "show_register": can_register and confirmed is None,
        "show_login_confirmed": confirmed is not None,
        "show_login_other": can_login_other,
        "show_confirm": mode == "pending",
        "warning": warning,
        "primary_account": confirmed,
        "pending_account": pending,
        "approved_other_account": approved_other,
    }


class AccountGateWidget(QFrame):
    loginConfirmedRequested = Signal(dict)
    loginOtherRequested = Signal(dict)
    registerRequested = Signal()
    confirmRegistrationRequested = Signal()
    refreshRequested = Signal()
    settingsRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MainPanel")
        self._account_state: dict[str, Any] = {}
        self._local_session: dict[str, Any] = {}
        self._primary_account: dict[str, Any] | None = None
        self._approved_other_account: dict[str, Any] | None = None
        self._showing_other_form = False

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

        self.other_form = DynamicFormWidget()
        self.other_form.set_form(OTHER_ACCOUNT_FORM)
        layout.addWidget(self.other_form)

        actions = QHBoxLayout()
        self.login_button = QPushButton("Войти")
        self.login_button.setObjectName("PrimaryButton")
        self.login_button.clicked.connect(self._on_login_confirmed)
        self.other_button = QPushButton("Войти в другой аккаунт")
        self.other_button.setObjectName("SecondaryButton")
        self.other_button.clicked.connect(self._on_other_clicked)
        self.register_button = QPushButton("Регистрация")
        self.register_button.setObjectName("PrimaryButton")
        self.register_button.clicked.connect(self.registerRequested.emit)
        self.confirm_button = QPushButton("Подтвердить данные")
        self.confirm_button.setObjectName("SecondaryButton")
        self.confirm_button.clicked.connect(self.confirmRegistrationRequested.emit)
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setObjectName("SecondaryButton")
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.settings_button = QPushButton("Настройки")
        self.settings_button.setObjectName("SecondaryButton")
        self.settings_button.clicked.connect(self.settingsRequested.emit)
        for button in (
            self.login_button,
            self.other_button,
            self.register_button,
            self.confirm_button,
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
        self.other_form.hide()

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
        self.title_label.setText(state["title"])
        self.message_label.setText(state.get("message") or "")
        self.message_label.setVisible(bool(self.message_label.text()))
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
        self.login_button.setVisible(bool(state["show_login_confirmed"]))
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
        self.register_button.setVisible(bool(state["show_register"]))
        self.register_button.setText("Продолжить регистрацию" if state.get("mode") == "pending" else "Регистрация")
        self.confirm_button.setVisible(bool(state["show_confirm"]))
        self.other_form.setVisible(self._showing_other_form)
        self.setStyleSheet(theme.main_window_stylesheet())

    def _on_login_confirmed(self) -> None:
        if self._primary_account:
            self.loginConfirmedRequested.emit(dict(self._primary_account))

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

    def reset_other_form(self) -> None:
        self._showing_other_form = False
        self.other_button.setText("Войти в другой аккаунт")
        self.other_form.set_form(OTHER_ACCOUNT_FORM)
        self.other_form.hide()
