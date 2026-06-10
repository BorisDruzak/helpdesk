from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class UserConsentPromptDialog(QDialog):
    approved = Signal()
    denied = Signal()

    def __init__(self, consent: dict, parent=None):
        super().__init__(parent)
        self.consent = dict(consent or {})
        self.setWindowTitle("Запрос согласия")
        self.setModal(False)
        self.setMinimumWidth(460)

        title_text = str(self.consent.get("title") or "Требуется ваше согласие")
        description = str(self.consent.get("description") or "").strip()
        subject_type = str(self.consent.get("subject_type") or "consent")
        risk_level = str(self.consent.get("risk_level") or "unknown")
        ticket_id = str(self.consent.get("ticket_id") or "").strip()
        device_id = str(self.consent.get("device_id") or "").strip()
        expires_at = str(self.consent.get("expires_at") or "").strip()

        layout = QVBoxLayout(self)
        title = QLabel(title_text)
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        title.setWordWrap(True)
        layout.addWidget(title)

        meta_parts = [f"Тип: {subject_type}", f"Риск: {risk_level}"]
        if ticket_id:
            meta_parts.append(f"Обращение: {ticket_id}")
        if device_id:
            meta_parts.append(f"Устройство: {device_id}")
        if expires_at:
            meta_parts.append(f"Истекает: {expires_at}")

        text = QLabel("\n".join(meta_parts) + (f"\n\n{description}" if description else ""))
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
