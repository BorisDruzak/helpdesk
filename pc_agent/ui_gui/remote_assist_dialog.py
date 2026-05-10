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
        mode = str(payload.get("mode") or "view_only")
        session_features = payload.get("session_features") if isinstance(payload.get("session_features"), dict) else {}
        if mode == "interactive_control":
            mode_label = "Просмотр и управление"
            mode_note = "В этом режиме специалист будет видеть ваш экран и сможет управлять мышью и клавиатурой после вашего разрешения."
        elif mode == "file_transfer":
            mode_label = "Передача файлов"
            mode_note = "Специалист сможет передавать файлы на этот компьютер в рамках этой сессии; файлы будут сохраняться в папку загрузок Maria Remote Assist."
        elif mode == "elevated_admin":
            mode_label = "Административная помощь"
            mode_note = (
                "Специалист будет видеть экран и сможет управлять мышью и клавиатурой в админских окнах. "
                "После вашего разрешения Windows покажет отдельное UAC-подтверждение; без него админ-доступ не включится."
            )
        else:
            mode_label = "Только просмотр"
            mode_note = "В этом режиме специалист будет видеть ваш экран, но не сможет управлять мышью или клавиатурой."
        feature_notes: list[str] = []
        if session_features.get("clipboard_auto_sync"):
            feature_notes.append("Буфер обмена будет синхронизироваться автоматически между вами и специалистом.")
        if session_features.get("file_transfer"):
            feature_notes.append("Специалист сможет передавать файлы на этот компьютер; файлы будут сохранены в папку загрузок Maria Remote Assist.")
        feature_text = "\n".join(feature_notes)

        layout = QVBoxLayout(self)
        title = QLabel("Запрос удалённой помощи")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        text = QLabel(
            f"Специалист {operator} хочет подключиться к вашему компьютеру.\n\n"
            f"Обращение: {ticket_code}\n"
            f"Цель: {reason}\n"
            f"Режим: {mode_label}\n"
            f"Длительность: до {duration} минут\n\n"
            f"{mode_note}"
            + (f"\n{feature_text}" if feature_text else "")
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
