from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class RemoteAssistConsentDialog(QDialog):
    approved = Signal()
    denied = Signal()

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload
        self.setWindowTitle("Запрос удалённой помощи")
        self.setModal(False)
        self.setMinimumWidth(460)

        operator = str(payload.get("operator_id") or "Специалист поддержки")
        ticket_code = str(payload.get("ticket_code") or payload.get("ticket_id") or "")
        reason = str(payload.get("reason") or "Не указана")
        duration = str(payload.get("duration_minutes") or "15")

        layout = QVBoxLayout(self)
        title = QLabel("Запрос удалённой помощи")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        text = QLabel(
            f"Специалист {operator} хочет подключиться к вашему компьютеру.\n\n"
            f"Обращение: {ticket_code}\n"
            f"Цель: {reason}\n"
            f"Режим: Только просмотр\n"
            f"Длительность: до {duration} минут\n\n"
            "В этом режиме специалист будет видеть ваш экран, но не сможет управлять мышью или клавиатурой."
        )
        text.setWordWrap(True)
        layout.addWidget(text)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        deny_button = QPushButton("Отклонить")
        allow_button = QPushButton("Разрешить")
        allow_button.setDefault(True)
        buttons.addWidget(deny_button)
        buttons.addWidget(allow_button)
        layout.addLayout(buttons)

        deny_button.clicked.connect(self._deny)
        allow_button.clicked.connect(self._approve)

    def _approve(self) -> None:
        self.approved.emit()
        self.accept()

    def _deny(self) -> None:
        self.denied.emit()
        self.reject()
