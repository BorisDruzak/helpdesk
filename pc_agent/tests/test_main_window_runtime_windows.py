import sys
import inspect
from pathlib import Path
from types import SimpleNamespace

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


def test_custom_title_bar_does_not_render_duplicate_requester_connection_status():
    app = QApplication.instance() or QApplication([])
    bar = CustomTitleBar()

    assert app is not None
    assert not hasattr(bar, "status_pill")
    assert "TitleBarStatusPill" not in bar.styleSheet()


def test_main_window_keeps_sidebar_agent_status_card_for_version_and_update_state():
    setup_source = inspect.getsource(MainWindow._setup_ui)
    render_source = inspect.getsource(MainWindow._render_connection_status)

    assert "self.title_bar = CustomTitleBar" in setup_source
    assert "self.footer_status_block.hide()" not in setup_source
    assert "set_connection_status" not in render_source


def test_main_window_collapses_sidebar_for_focused_ticket_and_create_workspaces():
    setup_source = inspect.getsource(MainWindow._setup_ui)
    resize_source = inspect.getsource(MainWindow._set_sidebar_expanded)
    select_source = inspect.getsource(MainWindow._select_sidebar_view)
    list_visibility_source = inspect.getsource(MainWindow._on_list_navigation_visibility_changed)
    create_source = inspect.getsource(MainWindow._on_create_ticket_from_menu)
    created_source = inspect.getsource(MainWindow._on_ticket_created_from_wizard)

    assert "self._sidebar_collapsed_width" in setup_source
    assert "self.sidebar_toggle_btn.show()" in setup_source
    assert "self._sidebar_expanded = expanded" in resize_source
    assert "self._sidebar_collapsed_width" in resize_source
    assert "self.sidebar_profile_card.setVisible(expanded)" in resize_source
    assert "self.footer_status_block.setVisible(expanded)" in resize_source
    assert 'view_name in {"create", "ticket"}' in select_source
    assert 'self._select_sidebar_view("create", expand=False)' in create_source
    assert 'self._select_sidebar_view("ticket", expand=False)' in created_source
    assert "self._set_sidebar_expanded(False)" in list_visibility_source


def test_main_window_sidebar_resize_tolerates_early_setup_before_footer_card():
    resize_source = inspect.getsource(MainWindow._set_sidebar_expanded)

    assert 'hasattr(self, "footer_status_block")' in resize_source
    assert "self.footer_status_block.setVisible(expanded)" in resize_source


def test_main_window_create_ticket_menu_switches_before_async_prepare():
    window = MainWindow.__new__(MainWindow)
    selected: list[tuple[str, bool]] = []
    scheduled: list[object] = []
    statuses: list[tuple[str, bool]] = []
    reset_calls: list[bool] = []

    async def _prepare():
        return None

    class _FakeCreatePage:
        def reset_wizard(self):
            reset_calls.append(True)

        def _set_status(self, text, *, error):
            statuses.append((text, error))

        def async_prepare(self):
            return _prepare()

    window.ticket_create_page = _FakeCreatePage()
    window._select_sidebar_view = lambda view_name, *, expand: selected.append((view_name, expand))

    def _fake_spawn(coro, *, name):
        scheduled.append(SimpleNamespace(coro=coro, name=name))
        coro.close()
        return None

    window._spawn_gui_task = _fake_spawn

    MainWindow._on_create_ticket_from_menu(window)

    assert selected == [("create", False)]
    assert reset_calls == [True]
    assert statuses == [("Открываю форму обращения...", False)]
    assert scheduled and scheduled[0].name == "gui.create_ticket.prepare"


def test_main_window_create_ticket_prepare_uses_gui_task_scheduler():
    create_source = inspect.getsource(MainWindow._on_create_ticket_from_menu)
    scheduler_source = inspect.getsource(MainWindow._spawn_gui_task)

    assert "asyncio.create_task" not in create_source
    assert "self._spawn_gui_task(self.ticket_create_page.async_prepare()" in create_source
    assert "loop.create_task(coro, name=name)" in scheduler_source


def test_main_window_syncs_sidebar_connection_status_with_requester_labels():
    class _FakeButton:
        def __init__(self):
            self.text_value = ""

        def setText(self, value):
            self.text_value = value

        def setStyleSheet(self, _value):
            pass

        def setToolTip(self, _value):
            pass

    class _FakeDot:
        def __init__(self):
            self.object_name = ""

        def setObjectName(self, value):
            self.object_name = value

        def setStyleSheet(self, _value):
            pass

    class _FakeLabel:
        def __init__(self):
            self.value = ""

        def setText(self, value):
            self.value = value

    class _FakeUpdateButton:
        def isVisible(self):
            return False

    window = MainWindow.__new__(MainWindow)
    window._repair_text = lambda value: value
    window._refresh_dashboard = lambda: None
    window.connection_status_btn = _FakeButton()
    window.connection_status_dot = _FakeDot()
    window.agent_footer_meta = _FakeLabel()
    window.update_agent_btn = _FakeUpdateButton()
    window._server_connection_detail = ""
    window._bridge_connected = True

    window._server_connection_state = "connecting"
    window._render_connection_status()
    assert window.connection_status_btn.text_value == "Подключение..."
    assert window.agent_footer_meta.value == "Идёт подключение"

    window._server_connection_state = "connected"
    window._render_connection_status()
    assert window.connection_status_btn.text_value == "Онлайн"
    assert window.agent_footer_meta.value == "Сервер доступен"

    window._server_connection_state = "error"
    window._render_connection_status()
    assert window.connection_status_btn.text_value == "Ошибка подключения"
    assert window.agent_footer_meta.value == "Доступ отклонён"
