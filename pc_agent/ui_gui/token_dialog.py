"""
Token input dialog for agent authentication.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class TokenDialog(QDialog):
    def __init__(self, device_uuid: str, parent=None):
        super().__init__(parent)
        self.device_uuid = device_uuid
        self.token = None

        self.setWindowTitle("Agent Authentication")
        self.setMinimumWidth(520)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        info_label = QLabel(
            f"<b>Device UUID:</b> {self.device_uuid}<br><br>"
            "Enter authentication token generated from server admin panel."
        )
        info_label.setWordWrap(True)
        info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(info_label)

        uuid_row = QHBoxLayout()
        copy_uuid_btn = QPushButton("Copy Device UUID")
        copy_uuid_btn.clicked.connect(self._copy_device_uuid)
        uuid_row.addWidget(copy_uuid_btn)
        uuid_row.addStretch()
        layout.addLayout(uuid_row)

        token_label = QLabel("Token:")
        layout.addWidget(token_label)

        self.token_input = QTextEdit()
        self.token_input.setPlaceholderText("Paste token here...")
        self.token_input.setMaximumHeight(100)
        self.token_input.setAcceptRichText(False)
        layout.addWidget(self.token_input)

        paste_row = QHBoxLayout()
        paste_btn = QPushButton("Paste from clipboard")
        paste_btn.clicked.connect(self._paste_from_clipboard)
        paste_row.addWidget(paste_btn)
        paste_row.addStretch()
        layout.addLayout(paste_row)

        buttons_layout = QVBoxLayout()

        self.ok_button = QPushButton("OK")
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self._on_ok)
        buttons_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)

        layout.addLayout(buttons_layout)

        instruction = QLabel(
            "<small><i>"
            "To generate token:<br>"
            "1. Open server admin panel (http://server:8666/admin)<br>"
            "2. Go to 'Generate Agent Token' section<br>"
            "3. Enter device UUID and click 'Generate Token'<br>"
            "4. Copy token and paste it here"
            "</i></small>"
        )
        instruction.setWordWrap(True)
        instruction.setStyleSheet("color: #6e6e73;")
        layout.addWidget(instruction)

    def _on_ok(self) -> None:
        token = self.token_input.toPlainText().strip()

        if not token:
            QMessageBox.warning(self, "Invalid Token", "Please enter a token.")
            return

        if len(token) < 10:
            QMessageBox.warning(
                self,
                "Invalid Token",
                "Token seems too short. Please check and try again.",
            )
            return

        self.token = token
        self.accept()

    def _copy_device_uuid(self) -> None:
        QApplication.clipboard().setText(self.device_uuid)
        QMessageBox.information(self, "Copied", "Device UUID copied to clipboard.")

    def _paste_from_clipboard(self) -> None:
        text = QApplication.clipboard().text().strip()
        if text:
            self.token_input.setPlainText(text)

    def get_token(self) -> str:
        return self.token
