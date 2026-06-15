import sys
import inspect
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent.ui_gui.main_window import MainWindow, gui_soft_shadows_enabled
from pc_agent.ui_gui.performance_probe import (
    GuiPerformanceProbe,
    gui_performance_probe_enabled,
    gui_performance_probe_interval_ms,
)
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


def test_frameless_resize_handler_deduplicates_cursor_updates():
    class _FakeWindow:
        def __init__(self):
            self.calls = []

        def setCursor(self, shape):
            self.calls.append(("set", shape))

        def unsetCursor(self):
            self.calls.append(("unset", None))

    fake = _FakeWindow()
    handler = FramelessResizeHandler.__new__(FramelessResizeHandler)
    handler._window = fake
    handler._last_cursor_shape = None

    handler._set_cursor_shape(Qt.CursorShape.SizeHorCursor)
    handler._set_cursor_shape(Qt.CursorShape.SizeHorCursor)
    handler._set_cursor_shape(None)
    handler._set_cursor_shape(None)
    handler._set_cursor_shape(Qt.CursorShape.SizeVerCursor)

    assert fake.calls == [
        ("set", Qt.CursorShape.SizeHorCursor),
        ("unset", None),
        ("set", Qt.CursorShape.SizeVerCursor),
    ]


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


def test_main_window_soft_shadows_are_opt_in_for_low_cpu_default(monkeypatch):
    monkeypatch.delenv("PC_AGENT_ENABLE_GUI_SHADOWS", raising=False)
    assert gui_soft_shadows_enabled() is False

    monkeypatch.setenv("PC_AGENT_ENABLE_GUI_SHADOWS", "1")
    assert gui_soft_shadows_enabled() is True


def test_gui_performance_probe_is_enabled_with_bounded_default_interval(monkeypatch):
    monkeypatch.delenv("PC_AGENT_GUI_PROFILER", raising=False)
    monkeypatch.delenv("PC_AGENT_GUI_PROFILER_INTERVAL_MS", raising=False)
    assert gui_performance_probe_enabled() is True
    assert gui_performance_probe_interval_ms() == 5000

    monkeypatch.setenv("PC_AGENT_GUI_PROFILER", "0")
    assert gui_performance_probe_enabled() is False

    monkeypatch.setenv("PC_AGENT_GUI_PROFILER_INTERVAL_MS", "50")
    assert gui_performance_probe_interval_ms() == 1000

    monkeypatch.setenv("PC_AGENT_GUI_PROFILER_INTERVAL_MS", "90000")
    assert gui_performance_probe_interval_ms() == 60000


def test_gui_performance_probe_counts_qt_events_without_consuming_them():
    app = QApplication.instance() or QApplication([])
    window = MainWindow.__new__(MainWindow)
    window.isActiveWindow = lambda: True
    window.isVisible = lambda: True

    probe = GuiPerformanceProbe(app, window, interval_ms=1000)
    event = QEvent(QEvent.Type.MouseMove)

    assert probe.eventFilter(window, event) is False
    assert probe._event_counts[int(QEvent.Type.MouseMove)] == 1
    assert any(key.startswith("MouseMove@") for key in probe._receiver_counts)


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


def test_main_window_legacy_registration_entry_is_gated_by_default():
    setup_source = inspect.getsource(MainWindow._setup_ui)
    show_registration_source = inspect.getsource(MainWindow._show_registration_entry)
    select_source = inspect.getsource(MainWindow._select_sidebar_view)

    assert "legacy_agent_registration_enabled()" in setup_source
    assert "self.registration_entry_page = self._build_legacy_registration_disabled_page()" in setup_source
    assert "self.registration_entry_page = self._build_registration_entry_page()" in setup_source
    assert "self.main_content_stack.addWidget(self.registration_entry_page)" in setup_source
    assert "legacy_agent_registration_enabled()" in show_registration_source
    assert "self._on_browser_register_requested()" in show_registration_source
    assert 'view_name == "registration" and not legacy_agent_registration_enabled()' in select_source
    assert 'elif view_name == "registration"' in select_source
    assert "identity_section_layout.addWidget(registration_group)" not in setup_source


def test_main_window_entry_settings_has_back_to_account_gate():
    setup_source = inspect.getsource(MainWindow._setup_ui)
    account_entry_source = inspect.getsource(MainWindow._set_account_entry_mode)

    assert "self.settings_back_btn = QPushButton" in setup_source
    assert "self.settings_back_btn.clicked.connect(self._show_account_gate_entry)" in setup_source
    assert 'self._active_sidebar_view == "settings"' in account_entry_source


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
    window._active_account_session_for_tickets = lambda: {"account_mode": "confirmed_binding"}
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
