"""
Диалог «Дождитесь авторизации от Администратора» при отсутствии токена.

Агент отправляет запрос на подключение; при одобрении токен сохраняется в БД.
Диалог опрашивает БД и закрывается при появлении токена или при нажатии «Отмена».
"""
from __future__ import annotations

import asyncio
from typing import Optional, Callable, Awaitable

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
)
from PySide6.QtCore import QTimer, Qt
from loguru import logger


class WaitForAuthDialog(QDialog):
    """
    Показывает «Дождитесь авторизации от Администратора».
    При появлении токена в БД закрывается с результатом token.
    """
    def __init__(
        self,
        device_uuid: str,
        on_auth_complete: Optional[Callable[[], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.device_uuid = device_uuid
        self.on_auth_complete = on_auth_complete
        self._token: Optional[str] = None
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._check_token)
        self.setWindowTitle("Авторизация")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        self._label = QLabel(
            "Дождитесь авторизации от Администратора.\n\n"
            "Запрос на подключение отправлен. После одобрения в админ-панели окно закроется автоматически."
        )
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)
        btn_layout = QHBoxLayout()
        self._manual_btn = QPushButton("Ввести токен вручную")
        self._manual_btn.clicked.connect(self._on_manual)
        self._cancel_btn = QPushButton("Отмена")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self._manual_btn)
        btn_layout.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout)
        self._manual_token: Optional[str] = None

    def start_polling(self) -> None:
        """Запускает опрос БД каждые 2 секунды."""
        self._poll_timer.start(2000)

    def _check_token(self) -> None:
        """Проверяет наличие токена в БД."""
        try:
            from core.database import db_manager
            if not db_manager or not self.device_uuid:
                return
            import sqlite3
            conn = sqlite3.connect(db_manager._db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT token FROM auth_tokens
                WHERE device_id = ? AND is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            """, (self.device_uuid,))
            row = cursor.fetchone()
            conn.close()
            if row:
                self._token = row[0]
                self._poll_timer.stop()
                logger.info("Токен получен из БД после одобрения администратором")
                if self.on_auth_complete:
                    self.on_auth_complete()
                self.accept()
        except Exception as e:
            logger.debug(f"Ошибка проверки токена в БД: {e}")

    def _on_manual(self) -> None:
        """Переключение на ввод токена вручную — закрываем с результатом None, вызывающий покажет TokenDialog."""
        self._poll_timer.stop()
        self._manual_token = "manual"
        self.reject()

    def get_token(self) -> Optional[str]:
        """Возвращает токен после accept() (из БД)."""
        return self._token

    def was_manual_requested(self) -> bool:
        """True если нажали «Ввести токен вручную»."""
        return self._manual_token == "manual"
