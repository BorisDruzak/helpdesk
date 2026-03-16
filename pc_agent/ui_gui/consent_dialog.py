"""
Диалог для запроса согласия пользователя на выполнение действия.
"""

import json
import aiohttp
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QMessageBox
)
from PySide6.QtCore import Qt
from loguru import logger


class ConsentDialog(QDialog):
    """
    Диалог для запроса согласия.
    
    Отображает информацию о запросе и позволяет пользователю
    одобрить или отклонить действие.
    """
    
    def __init__(self, event_data: dict, host: str, port: int, parent=None, session_key: Optional[str] = None):
        """
        Инициализация диалога.
        
        Args:
            event_data: Данные события consent_required
            host: Хост UI API сервера
            port: Порт UI API сервера
            parent: Родительское окно
            session_key: Ключ сессии для привязки consent к чату (если не указан, берется из события или job_id)
        """
        super().__init__(parent)
        self.event_data = event_data
        self.host = host
        self.port = port
        self.setWindowTitle("Запрос согласия")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        # Извлекаем данные из события
        data = event_data.get("data", {})
        self.consent_token = data.get("consent_token", "")
        self.job_id = data.get("job_id", "")
        # session_key: приоритет - переданный параметр, затем из события, затем job_id
        # session_key == текущий chat job_id, полученный из /api/chat_start
        self.session_key = session_key or data.get("session_key") or self.job_id or ""
        self.tool_name = data.get("tool_name", "Unknown")
        self.reason = data.get("reason", "")
        self.params = data.get("params", {})
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Настройка UI диалога."""
        layout = QVBoxLayout(self)
        
        # Информация о инструменте
        tool_label = QLabel(f"<b>Инструмент:</b> {self.tool_name}")
        tool_label.setWordWrap(True)
        layout.addWidget(tool_label)
        
        # Причина запроса
        if self.reason:
            reason_label = QLabel(f"<b>Причина:</b> {self.reason}")
            reason_label.setWordWrap(True)
            layout.addWidget(reason_label)
        
        # Параметры (pretty JSON)
        params_label = QLabel("<b>Параметры:</b>")
        layout.addWidget(params_label)
        
        params_text = QTextEdit()
        params_text.setReadOnly(True)
        params_text.setMaximumHeight(150)
        try:
            params_json = json.dumps(self.params, indent=2, ensure_ascii=False)
            params_text.setPlainText(params_json)
        except Exception as e:
            params_text.setPlainText(f"Ошибка форматирования: {e}")
        layout.addWidget(params_text)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        approve_btn = QPushButton("Approve")
        approve_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        approve_btn.clicked.connect(self._on_approve)
        buttons_layout.addWidget(approve_btn)
        
        deny_btn = QPushButton("Deny")
        deny_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        deny_btn.clicked.connect(self._on_deny)
        buttons_layout.addWidget(deny_btn)
        
        layout.addLayout(buttons_layout)
    
    def _on_approve(self):
        """Обработчик нажатия кнопки Approve."""
        self._send_decision(approved=True)
    
    def _on_deny(self):
        """Обработчик нажатия кнопки Deny."""
        self._send_decision(approved=False)
    
    def _send_decision(self, approved: bool):
        """
        Отправляет решение о согласии на сервер.
        
        Args:
            approved: Одобрено ли действие
        """
        import asyncio
        
        # Получаем event loop (должен быть qasync loop)
        try:
            loop = asyncio.get_event_loop()
            # Создаем задачу в текущем loop
            asyncio.create_task(self._async_send_decision(approved))
        except RuntimeError:
            logger.error("Event loop не найден, не могу отправить решение")
            QMessageBox.warning(
                self,
                "Ошибка",
                "Event loop не найден, не могу отправить решение"
            )
    
    async def _async_send_decision(self, approved: bool):
        """
        Асинхронная отправка решения.
        
        Args:
            approved: Одобрено ли действие
        """
        url = f"http://{self.host}:{self.port}/ui/consent_decision"
        
        payload = {
            "consent_token": self.consent_token,
            "approved": approved,
            "session_key": self.session_key,
            "reason": "",
            "job_id": self.job_id
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.success(f"Решение о согласии отправлено: approved={approved}")
                        self.accept()  # Закрываем диалог
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка отправки решения: HTTP {response.status}, {error_text}")
                        QMessageBox.warning(
                            self,
                            "Ошибка",
                            f"Не удалось отправить решение:\nHTTP {response.status}\n{error_text}"
                        )
        except Exception as e:
            logger.error(f"Ошибка отправки решения: {e}")
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось отправить решение:\n{str(e)}"
            )

