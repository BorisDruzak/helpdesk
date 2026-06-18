from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from pc_agent.core.database import DatabaseManager
from pc_agent.ui_gui.wait_for_auth_dialog import WaitForAuthDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _dialog_with_error(tmp_path, payload: dict) -> WaitForAuthDialog:
    DatabaseManager._instance = None
    DatabaseManager(str(tmp_path / "storage.db"))
    (tmp_path / "connection_request_error.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    dialog = WaitForAuthDialog("device-1")
    assert dialog._show_connection_error_if_any() is True
    return dialog


def test_wait_for_auth_dialog_shows_archived_device_error(tmp_path):
    _app()

    dialog = _dialog_with_error(
        tmp_path,
        {
            "error_code": "DEVICE_ARCHIVED",
            "message": "Устройство архивировано администратором",
        },
    )

    assert "Устройство архивировано администратором" in dialog._label.text()
    assert "Новый запрос на подключение не появится" in dialog._label.text()


def test_wait_for_auth_dialog_keeps_token_limit_guidance(tmp_path):
    _app()

    dialog = _dialog_with_error(
        tmp_path,
        {
            "error_code": "TOKEN_LIMIT_EXCEEDED",
            "message": "На сервере уже есть 2 активных токена",
        },
    )

    assert "На сервере уже есть 2 активных токена" in dialog._label.text()
    assert "старый активный токен" in dialog._label.text()
