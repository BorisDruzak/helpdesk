from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon


class TrayManager(QObject):
    """Thin system tray wrapper for always-on agent mode."""

    def __init__(
        self,
        *,
        tooltip: str,
        logs_dir: Path,
        notifications_enabled: bool,
        on_show_window: Callable[[], None],
        on_restart_agent: Callable[[], None],
        on_exit_agent: Callable[[], None],
    ) -> None:
        super().__init__()
        self._logs_dir = Path(logs_dir)
        self._notifications_enabled = bool(notifications_enabled)
        self._on_show_window = on_show_window
        self._on_restart_agent = on_restart_agent
        self._on_exit_agent = on_exit_agent
        self._tray: Optional[QSystemTrayIcon] = None
        self._menu: Optional[QMenu] = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        app = QApplication.instance()
        icon = QIcon()
        if app is not None:
            style = app.style()
            if style is not None:
                icon = style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self._tray = QSystemTrayIcon(icon, app)
        self._tray.setToolTip(tooltip)

        menu = QMenu()
        action_show = QAction("Открыть окно", menu)
        action_show.triggered.connect(self._handle_show_window)
        menu.addAction(action_show)

        action_logs = QAction("Открыть логи", menu)
        action_logs.triggered.connect(self._handle_open_logs)
        menu.addAction(action_logs)

        action_restart = QAction("Перезапустить агент", menu)
        action_restart.triggered.connect(self._handle_restart_agent)
        menu.addAction(action_restart)

        menu.addSeparator()

        action_exit = QAction("Выход", menu)
        action_exit.triggered.connect(self._handle_exit_agent)
        menu.addAction(action_exit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._menu = menu

    @property
    def available(self) -> bool:
        return self._tray is not None

    def show(self) -> None:
        if self._tray is not None:
            self._tray.show()

    def cleanup(self) -> None:
        if self._tray is not None:
            self._tray.hide()
            self._tray.deleteLater()
            self._tray = None
        if self._menu is not None:
            self._menu.deleteLater()
            self._menu = None

    def set_tooltip(self, text: str) -> None:
        if self._tray is not None:
            self._tray.setToolTip(text)

    def notify(self, title: str, message: str) -> None:
        if self._tray is not None and self._notifications_enabled:
            self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 4000)

    def _handle_show_window(self) -> None:
        self._on_show_window()

    def _handle_open_logs(self) -> None:
        if self._logs_dir.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._logs_dir)))

    def _handle_restart_agent(self) -> None:
        self._on_restart_agent()

    def _handle_exit_agent(self) -> None:
        self._on_exit_agent()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.MiddleClick,
        }:
            self._on_show_window()
