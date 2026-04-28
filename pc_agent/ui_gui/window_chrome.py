"""Custom cross-platform window chrome for the Qt agent GUI."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QWidget

from pc_agent.version import AGENT_VERSION

from . import theme


class CustomTitleBar(QFrame):
    """A small frameless-window title bar that works on Windows and Linux."""

    minimizeRequested = Signal()
    maximizeRestoreRequested = Signal()
    closeRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CustomTitleBar")
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._dragging = False
        self._drag_start_global = QPoint()
        self._drag_start_window_pos = QPoint()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(8)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("TitleBarIcon")
        self.icon_label.setFixedSize(18, 18)
        self.icon_label.setScaledContents(True)
        if theme.LOGO_PATH.exists():
            self.icon_label.setPixmap(
                QPixmap(str(theme.LOGO_PATH)).scaled(
                    18,
                    18,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(self.icon_label)

        self.title_label = QLabel(f"Maria Agent v{AGENT_VERSION}")
        self.title_label.setObjectName("TitleBarText")
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        self.minimize_btn = self._chrome_button("–", "Свернуть")
        self.maximize_btn = self._chrome_button("□", "Развернуть")
        self.close_btn = self._chrome_button("×", "Скрыть окно / tray")
        self.close_btn.setObjectName("TitleBarCloseButton")

        self.minimize_btn.clicked.connect(self.minimizeRequested)
        self.maximize_btn.clicked.connect(self.maximizeRestoreRequested)
        self.close_btn.clicked.connect(self.closeRequested)

        layout.addWidget(self.minimize_btn)
        layout.addWidget(self.maximize_btn)
        layout.addWidget(self.close_btn)

        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.setStyleSheet(theme.window_chrome_stylesheet())

    def set_maximized(self, maximized: bool) -> None:
        self.maximize_btn.setText("❐" if maximized else "□")
        self.maximize_btn.setToolTip("Восстановить" if maximized else "Развернуть")

    @staticmethod
    def _chrome_button(text: str, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName("TitleBarButton")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(QSize(46, 30))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximizeRestoreRequested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            handle = window.windowHandle() if window else None
            if handle is not None and hasattr(handle, "startSystemMove"):
                try:
                    handle.startSystemMove()
                    event.accept()
                    return
                except Exception:
                    pass
            if window is not None and not window.isMaximized() and not window.isFullScreen():
                self._dragging = True
                self._drag_start_global = event.globalPosition().toPoint()
                self._drag_start_window_pos = window.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            window = self.window()
            if window is not None:
                delta = event.globalPosition().toPoint() - self._drag_start_global
                window.move(self._drag_start_window_pos + delta)
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)


class FramelessResizeHandler(QWidget):
    """Event filter that restores native edge resizing for frameless windows."""

    MARGIN = 7

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._press_pos = QPoint()
        self._press_geometry = window.geometry()
        self._pressed_edges = Qt.Edge(0)
        window.installEventFilter(self)
        window.setMouseTracking(True)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is not self._window:
            return False
        if self._window.isMaximized() or self._window.isFullScreen():
            return False
        if event.type() == QEvent.Type.MouseMove:
            self._update_cursor(event.position().toPoint())
            if self._pressed_edges:
                self._resize_manually(event.globalPosition().toPoint())
                return True
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            edges = self._edges_at(event.position().toPoint())
            if edges:
                self._pressed_edges = edges
                self._press_pos = event.globalPosition().toPoint()
                self._press_geometry = self._window.geometry()
                handle = self._window.windowHandle()
                if handle is not None and hasattr(handle, "startSystemResize"):
                    try:
                        if handle.startSystemResize(edges):
                            self._pressed_edges = Qt.Edge(0)
                            return True
                    except Exception:
                        pass
                return True
        if event.type() == QEvent.Type.MouseButtonRelease:
            self._pressed_edges = Qt.Edge(0)
            self._update_cursor(event.position().toPoint())
        if event.type() == QEvent.Type.Leave and not self._pressed_edges:
            self._window.unsetCursor()
        return False

    def _edges_at(self, pos: QPoint) -> Qt.Edge:
        rect = self._window.rect()
        edges = Qt.Edge(0)
        if pos.x() <= self.MARGIN:
            edges |= Qt.Edge.LeftEdge
        elif pos.x() >= rect.width() - self.MARGIN:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= self.MARGIN:
            edges |= Qt.Edge.TopEdge
        elif pos.y() >= rect.height() - self.MARGIN:
            edges |= Qt.Edge.BottomEdge
        return edges

    def _update_cursor(self, pos: QPoint) -> None:
        edges = self._edges_at(pos)
        if edges in (Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.Edge.RightEdge | Qt.Edge.BottomEdge):
            self._window.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges in (Qt.Edge.RightEdge | Qt.Edge.TopEdge, Qt.Edge.LeftEdge | Qt.Edge.BottomEdge):
            self._window.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            self._window.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
            self._window.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self._window.unsetCursor()

    def _resize_manually(self, global_pos: QPoint) -> None:
        delta = global_pos - self._press_pos
        geom = self._press_geometry
        min_size = self._window.minimumSize()
        x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()

        if self._pressed_edges & Qt.Edge.LeftEdge:
            new_x = x + delta.x()
            new_w = w - delta.x()
            if new_w >= min_size.width():
                x, w = new_x, new_w
        if self._pressed_edges & Qt.Edge.RightEdge:
            w = max(min_size.width(), w + delta.x())
        if self._pressed_edges & Qt.Edge.TopEdge:
            new_y = y + delta.y()
            new_h = h - delta.y()
            if new_h >= min_size.height():
                y, h = new_y, new_h
        if self._pressed_edges & Qt.Edge.BottomEdge:
            h = max(min_size.height(), h + delta.y())

        self._window.setGeometry(x, y, w, h)
