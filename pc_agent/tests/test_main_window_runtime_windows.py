import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent.ui_gui.main_window import MainWindow


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
