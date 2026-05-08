import sys
import inspect
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent.ui_gui.main_window import MainWindow
from pc_agent.ui_gui.window_chrome import CustomTitleBar, FramelessResizeHandler


def test_stop_recording_overlay_is_tool_window_not_taskbar_window():
    app = QApplication.instance() or QApplication([])
    window = MainWindow.__new__(MainWindow)
    window._stop_button_widget = None
    window._recording_operation_id = "op-test"

    try:
        window._show_stop_button()

        overlay = window._stop_button_widget
        assert overlay is not None
        assert overlay.windowType() == Qt.WindowType.Tool
        assert overlay.windowTitle() == "Maria Agent recording control"
    finally:
        if window._stop_button_widget is not None:
            window._hide_stop_button()
        app.processEvents()


def test_frameless_chrome_avoids_qt_native_helper_windows():
    source = "\n".join(
        (
            inspect.getsource(CustomTitleBar.mousePressEvent),
            inspect.getsource(FramelessResizeHandler.eventFilter),
        )
    )

    assert "startSystemMove" not in source
    assert "startSystemResize" not in source


def test_sidebar_header_does_not_create_unparented_blank_top_level_labels():
    source = "\n".join(
        (
            inspect.getsource(MainWindow._setup_ui),
            inspect.getsource(MainWindow._set_sidebar_expanded),
        )
    )

    assert "sidebar_title_label = QLabel" not in source
    assert "sidebar_subtitle_label = QLabel" not in source
    assert "sidebar_title_label.setVisible" not in source
    assert "sidebar_subtitle_label.setVisible" not in source
