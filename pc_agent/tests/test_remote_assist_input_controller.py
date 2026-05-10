import pytest

from pc_agent.remote_assist.input_controller import (
    InputController,
    InputControllerError,
    LinuxPynputInputBackend,
    WindowsSendInputBackend,
)


def test_remote_assist_input_controller_is_disabled_by_default() -> None:
    controller = InputController(platform="win32")

    assert controller.enabled is False
    with pytest.raises(InputControllerError) as exc:
        controller.handle_message({"type": "mouse_move", "x_ratio": 0.5, "y_ratio": 0.5})
    assert exc.value.code == "CONTROL_DISABLED"


def test_control_requires_explicit_enable_message() -> None:
    sent: list[dict] = []
    controller = InputController(
        mode_enabled=True,
        platform="win32",
        sender=sent.append,
        screen_size_provider=lambda: (1000, 500),
    )

    with pytest.raises(InputControllerError) as exc:
        controller.handle_message({"type": "mouse_move", "x_ratio": 0.5, "y_ratio": 0.5})
    assert exc.value.code == "CONTROL_NOT_ACTIVE"

    result = controller.handle_message({"type": "control_enable"})
    assert result["type"] == "control.enabled"
    assert controller.enabled is True

    result = controller.handle_message({"type": "mouse_move", "x_ratio": 0.5, "y_ratio": 0.25})
    assert result == {"type": "control.accepted", "action": "mouse_move"}
    assert sent == [{"kind": "mouse_move", "x": 500, "y": 125}]


def test_mouse_click_and_keyboard_messages_are_validated() -> None:
    sent: list[dict] = []
    controller = InputController(
        mode_enabled=True,
        platform="win32",
        sender=sent.append,
        screen_size_provider=lambda: (1920, 1080),
    )
    controller.handle_message({"type": "control_enable"})

    controller.handle_message({"type": "mouse_click", "x_ratio": 1, "y_ratio": 0, "button": "right", "click_count": 2})
    controller.handle_message({"type": "key_down", "key": "Enter"})
    controller.handle_message({"type": "key_up", "key": "Enter"})

    assert sent == [
        {"kind": "mouse_click", "x": 1919, "y": 0, "button": "right", "click_count": 2},
        {"kind": "key_down", "key": "Enter"},
        {"kind": "key_up", "key": "Enter"},
    ]


def test_drag_wheel_and_shortcuts_are_validated() -> None:
    sent: list[dict] = []
    controller = InputController(
        mode_enabled=True,
        platform="win32",
        sender=sent.append,
        screen_size_provider=lambda: (1000, 500),
    )
    controller.handle_message({"type": "control_enable"})

    controller.handle_message({"type": "mouse_down", "x_ratio": 0.1, "y_ratio": 0.2, "button": "left"})
    controller.handle_message({"type": "mouse_up", "x_ratio": 0.3, "y_ratio": 0.4, "button": "left"})
    controller.handle_message({"type": "mouse_wheel", "x_ratio": 0.5, "y_ratio": 0.5, "delta_y": -240})
    controller.handle_message({"type": "key_press", "key": "c", "modifiers": ["Control"]})

    assert sent == [
        {"kind": "mouse_down", "x": 100, "y": 100, "button": "left"},
        {"kind": "mouse_up", "x": 300, "y": 200, "button": "left"},
        {"kind": "mouse_wheel", "x": 500, "y": 250, "delta_x": 0, "delta_y": -240},
        {"kind": "key_press", "key": "c", "modifiers": ["Control"]},
    ]


def test_linux_control_uses_pynput_backend() -> None:
    class FakeMouse:
        def __init__(self) -> None:
            self.position = (0, 0)
            self.clicks: list[tuple[str, int]] = []
            self.pressed: list[tuple[str, str]] = []
            self.scrolled: list[tuple[int, int]] = []

        def click(self, button: str, count: int = 1) -> None:
            self.clicks.append((button, count))

        def press(self, button: str) -> None:
            self.pressed.append(("down", button))

        def release(self, button: str) -> None:
            self.pressed.append(("up", button))

        def scroll(self, delta_x: int, delta_y: int) -> None:
            self.scrolled.append((delta_x, delta_y))

    class FakeKeyboard:
        def __init__(self) -> None:
            self.pressed: list[tuple[str, str]] = []
            self.typed: list[str] = []

        def press(self, key: str) -> None:
            self.pressed.append(("down", key))

        def release(self, key: str) -> None:
            self.pressed.append(("up", key))

        def type(self, text: str) -> None:
            self.typed.append(text)

    mouse = FakeMouse()
    keyboard = FakeKeyboard()
    backend = LinuxPynputInputBackend(mouse=mouse, keyboard=keyboard, screen_size_provider=lambda: (800, 600))
    controller = InputController(mode_enabled=True, platform="linux", backend=backend)

    controller.handle_message({"type": "control_enable"})
    controller.handle_message({"type": "mouse_move", "x_ratio": 0.25, "y_ratio": 0.5})
    controller.handle_message({"type": "mouse_click", "x_ratio": 0.25, "y_ratio": 0.5, "button": "left", "click_count": 2})
    controller.handle_message({"type": "mouse_wheel", "x_ratio": 0.25, "y_ratio": 0.5, "delta_y": -120})
    controller.handle_message({"type": "key_down", "key": "Enter"})
    controller.handle_message({"type": "key_up", "key": "Enter"})
    controller.handle_message({"type": "key_press", "key": "v", "modifiers": ["Control"]})
    controller.handle_message({"type": "text_input", "text": "test"})

    assert mouse.position == (200, 300)
    assert mouse.clicks == [("left", 2)]
    assert mouse.scrolled == [(0, -120)]
    assert keyboard.pressed == [("down", "enter"), ("up", "enter"), ("down", "ctrl"), ("down", "v"), ("up", "v"), ("up", "ctrl")]
    assert keyboard.typed == ["test"]


def test_windows_backend_uses_sendinput() -> None:
    class FakeUser32:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int]] = []
            self.attached: list[tuple[int, int, bool]] = []
            self.cursor_positions: list[tuple[int, int]] = []

        def SendInput(self, count: int, inputs: object, size: int) -> int:
            self.calls.append((count, size))
            return count

        def SetCursorPos(self, x: int, y: int) -> bool:
            self.cursor_positions.append((x, y))
            return True

        def GetSystemMetrics(self, index: int) -> int:
            values = {76: 0, 77: 0, 78: 1920, 79: 1080, 0: 1920, 1: 1080}
            return values[index]

        def VkKeyScanW(self, codepoint: int) -> int:
            return codepoint

        def GetForegroundWindow(self) -> int:
            return 100

        def GetWindowThreadProcessId(self, window: int, process_id: object) -> int:
            assert window == 100
            return 20

        def AttachThreadInput(self, current_thread_id: int, foreground_thread_id: int, attach: bool) -> bool:
            self.attached.append((current_thread_id, foreground_thread_id, attach))
            return True

    class FakeKernel32:
        def GetCurrentThreadId(self) -> int:
            return 10

        def GetLastError(self) -> int:
            return 0

    user32 = FakeUser32()
    backend = WindowsSendInputBackend(user32=user32, kernel32=FakeKernel32())

    backend.send({"kind": "mouse_click", "x": 100, "y": 200, "button": "left"})
    backend.send({"kind": "mouse_click", "x": 100, "y": 200, "button": "left", "click_count": 2})
    backend.send({"kind": "key_down", "key": "Enter"})
    backend.send({"kind": "key_up", "key": "Enter"})
    backend.send({"kind": "text_input", "text": "я"})

    assert len(user32.calls) == 5
    assert all(count >= 1 for count, _size in user32.calls)
    assert user32.calls[1][0] == 4
    assert user32.cursor_positions == [(100, 200), (100, 200)]
    assert user32.attached[0] == (10, 20, True)
    assert user32.attached[1] == (10, 20, False)


def test_control_rejects_unenabled_features() -> None:
    controller = InputController(mode_enabled=True, platform="win32", sender=lambda _action: None)

    controller.handle_message({"type": "control_enable"})
    with pytest.raises(InputControllerError) as exc:
        controller.handle_message({"type": "clipboard_enable"})
    assert exc.value.code == "FEATURE_NOT_ENABLED"
