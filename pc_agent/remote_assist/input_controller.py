from __future__ import annotations

import sys
from contextlib import contextmanager
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


class InputControllerError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


InputSender = Callable[[dict[str, Any]], None]
ScreenSizeProvider = Callable[[], tuple[int, int]]


class InputBackend(Protocol):
    def send(self, action: dict[str, Any]) -> None: ...

    def screen_size(self) -> tuple[int, int]: ...


@dataclass(frozen=True, slots=True)
class ControlLimits:
    max_text_chars: int = 256


@dataclass(slots=True)
class CallbackInputBackend:
    sender: InputSender
    screen_size_provider: ScreenSizeProvider

    def send(self, action: dict[str, Any]) -> None:
        self.sender(action)

    def screen_size(self) -> tuple[int, int]:
        return self.screen_size_provider()


class WindowsSendInputBackend:
    def __init__(
        self,
        *,
        user32: Any | None = None,
        kernel32: Any | None = None,
        screen_size_provider: ScreenSizeProvider | None = None,
        attach_to_foreground: bool = True,
    ):
        if user32 is None:
            import ctypes

            user32 = ctypes.windll.user32
        if kernel32 is None:
            import ctypes

            kernel32 = ctypes.windll.kernel32
        self._user32 = user32
        self._kernel32 = kernel32
        self._screen_size_provider = screen_size_provider
        self._attach_to_foreground = attach_to_foreground

    def screen_size(self) -> tuple[int, int]:
        if self._screen_size_provider is not None:
            return self._screen_size_provider()
        _left, _top, width, height = self._virtual_bounds()
        return width, height

    def send(self, action: dict[str, Any]) -> None:
        kind = action["kind"]
        if kind == "mouse_move":
            self._set_cursor_position(int(action["x"]), int(action["y"]))
        elif kind in {"mouse_down", "mouse_up"}:
            flag = _mouse_button_down_flag(action["button"]) if kind == "mouse_down" else _mouse_button_up_flag(action["button"])
            self._set_cursor_position(int(action["x"]), int(action["y"]))
            self._send_inputs([self._mouse_input(0, 0, flag, absolute=False)])
        elif kind == "mouse_click":
            down, up = _mouse_button_flags(action["button"])
            self._set_cursor_position(int(action["x"]), int(action["y"]))
            self._send_inputs([self._mouse_input(0, 0, down, absolute=False), self._mouse_input(0, 0, up, absolute=False)])
        elif kind == "mouse_wheel":
            self._set_cursor_position(int(action["x"]), int(action["y"]))
            self._send_inputs([_mouse_input(dx=0, dy=0, mouse_data=int(action["delta_y"]), flags=_MOUSEEVENTF_WHEEL)])
        elif kind in {"key_down", "key_up"}:
            vk = _virtual_key(action["key"], self._user32)
            flags = 0 if kind == "key_down" else _KEYEVENTF_KEYUP
            self._send_inputs([_keyboard_input(vk=vk, flags=flags)])
        elif kind == "key_press":
            self._send_inputs(_keyboard_shortcut_inputs(action["key"], action.get("modifiers", []), self._user32))
        elif kind == "text_input":
            inputs: list[_INPUT] = []
            for unit in _utf16_code_units(str(action["text"])):
                inputs.append(_keyboard_input(scan=unit, flags=_KEYEVENTF_UNICODE))
                inputs.append(_keyboard_input(scan=unit, flags=_KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP))
            self._send_inputs(inputs)

    def _mouse_input(self, x: int, y: int, flags: int, *, absolute: bool = True) -> "_INPUT":
        if absolute:
            dx, dy = self._absolute_coordinates(x, y)
            flags |= _MOUSEEVENTF_ABSOLUTE | _MOUSEEVENTF_VIRTUALDESK
        else:
            dx, dy = x, y
        return _mouse_input(dx=dx, dy=dy, flags=flags)

    def _absolute_coordinates(self, x: int, y: int) -> tuple[int, int]:
        left, top, width, height = self._virtual_bounds()
        actual_x = left + max(0, min(width - 1, x))
        actual_y = top + max(0, min(height - 1, y))
        dx = int(round((actual_x - left) * 65535 / max(1, width - 1)))
        dy = int(round((actual_y - top) * 65535 / max(1, height - 1)))
        return dx, dy

    def _screen_coordinates(self, x: int, y: int) -> tuple[int, int]:
        left, top, width, height = self._virtual_bounds()
        actual_x = left + max(0, min(width - 1, x))
        actual_y = top + max(0, min(height - 1, y))
        return actual_x, actual_y

    def _set_cursor_position(self, x: int, y: int) -> None:
        actual_x, actual_y = self._screen_coordinates(x, y)
        with self._foreground_input_queue():
            ok = bool(getattr(self._user32, "SetCursorPos")(actual_x, actual_y))
        if not ok:
            error_code = self._last_error()
            raise InputControllerError("CONTROL_INJECTION_FAILED", f"Windows SetCursorPos failed; last_error={error_code}")

    def _virtual_bounds(self) -> tuple[int, int, int, int]:
        left = int(self._user32.GetSystemMetrics(76))
        top = int(self._user32.GetSystemMetrics(77))
        width = int(self._user32.GetSystemMetrics(78))
        height = int(self._user32.GetSystemMetrics(79))
        if width <= 0 or height <= 0:
            left, top = 0, 0
            width = int(self._user32.GetSystemMetrics(0))
            height = int(self._user32.GetSystemMetrics(1))
        return left, top, max(1, width), max(1, height)

    def _send_inputs(self, inputs: list["_INPUT"]) -> None:
        if not inputs:
            return
        import ctypes

        array_type = _INPUT * len(inputs)
        array = array_type(*inputs)
        with self._foreground_input_queue():
            sent = int(self._user32.SendInput(len(inputs), array, ctypes.sizeof(_INPUT)))
        if sent != len(inputs):
            error_code = self._last_error()
            raise InputControllerError(
                "CONTROL_INJECTION_FAILED",
                f"Windows SendInput did not accept all input events; sent={sent}/{len(inputs)} last_error={error_code}",
            )

    @contextmanager
    def _foreground_input_queue(self):
        attached = False
        current_thread_id = 0
        foreground_thread_id = 0
        try:
            if self._attach_to_foreground:
                foreground_window = int(getattr(self._user32, "GetForegroundWindow", lambda: 0)() or 0)
                if foreground_window:
                    import ctypes

                    process_id = ctypes.c_ulong(0)
                    foreground_thread_id = int(self._user32.GetWindowThreadProcessId(foreground_window, ctypes.byref(process_id)) or 0)
                    current_thread_id = int(getattr(self._kernel32, "GetCurrentThreadId", lambda: 0)() or 0)
                    if foreground_thread_id and current_thread_id and foreground_thread_id != current_thread_id:
                        attached = bool(self._user32.AttachThreadInput(current_thread_id, foreground_thread_id, True))
            yield
        finally:
            if attached:
                try:
                    self._user32.AttachThreadInput(current_thread_id, foreground_thread_id, False)
                except Exception:
                    pass

    def _last_error(self) -> int:
        try:
            return int(self._kernel32.GetLastError())
        except Exception:
            return 0


class LinuxPynputInputBackend:
    def __init__(
        self,
        *,
        mouse: Any | None = None,
        keyboard: Any | None = None,
        button_module: Any | None = None,
        key_module: Any | None = None,
        screen_size_provider: ScreenSizeProvider | None = None,
    ):
        if mouse is None or keyboard is None:
            try:
                from pynput import keyboard as pynput_keyboard
                from pynput import mouse as pynput_mouse
            except Exception as exc:
                raise InputControllerError("CONTROL_UNSUPPORTED", "Linux Remote Assist control requires pynput") from exc
            mouse = mouse or pynput_mouse.Controller()
            keyboard = keyboard or pynput_keyboard.Controller()
            button_module = button_module or pynput_mouse.Button
            key_module = key_module or pynput_keyboard.Key
        self._mouse = mouse
        self._keyboard = keyboard
        self._button_module = button_module
        self._key_module = key_module
        self._screen_size_provider = screen_size_provider or _get_linux_primary_screen_size

    def screen_size(self) -> tuple[int, int]:
        return self._screen_size_provider()

    def send(self, action: dict[str, Any]) -> None:
        kind = action["kind"]
        if kind in {"mouse_move", "mouse_click"}:
            self._mouse.position = (int(action["x"]), int(action["y"]))
        if kind == "mouse_down":
            self._mouse.position = (int(action["x"]), int(action["y"]))
            self._mouse.press(self._button(action["button"]))
        elif kind == "mouse_up":
            self._mouse.position = (int(action["x"]), int(action["y"]))
            self._mouse.release(self._button(action["button"]))
        if kind == "mouse_click":
            self._mouse.click(self._button(action["button"]), 1)
        elif kind == "mouse_wheel":
            self._mouse.scroll(int(action.get("delta_x", 0)), int(action.get("delta_y", 0)))
        elif kind == "key_down":
            self._keyboard.press(self._key(action["key"]))
        elif kind == "key_up":
            self._keyboard.release(self._key(action["key"]))
        elif kind == "key_press":
            modifiers = [self._key(item) for item in action.get("modifiers", [])]
            key = self._key(action["key"])
            for modifier in modifiers:
                self._keyboard.press(modifier)
            try:
                self._keyboard.press(key)
                self._keyboard.release(key)
            finally:
                for modifier in reversed(modifiers):
                    self._keyboard.release(modifier)
        elif kind == "text_input":
            self._keyboard.type(str(action["text"]))

    def _button(self, button: str) -> Any:
        if self._button_module is None:
            return button
        return getattr(self._button_module, button)

    def _key(self, key: str) -> Any:
        special = {
            "Control": "ctrl",
            "Alt": "alt",
            "Shift": "shift",
            "Meta": "cmd",
            "Enter": "enter",
            "Tab": "tab",
            "Escape": "esc",
            "Backspace": "backspace",
            "Delete": "delete",
            "ArrowLeft": "left",
            "ArrowUp": "up",
            "ArrowRight": "right",
            "ArrowDown": "down",
            "Home": "home",
            "End": "end",
            "PageUp": "page_up",
            "PageDown": "page_down",
            "Space": "space",
        }
        mapped = special.get(key)
        if mapped is None:
            return key
        if self._key_module is None:
            return mapped
        return getattr(self._key_module, mapped)


class InputController:
    """Validated Remote Assist input bridge.

    The controller is inert unless the session mode enabled control and the
    operator explicitly sends control_enable over the WebRTC data channel.
    """

    def __init__(
        self,
        *,
        mode_enabled: bool = False,
        platform: str | None = None,
        sender: InputSender | None = None,
        screen_size_provider: ScreenSizeProvider | None = None,
        backend: InputBackend | None = None,
        limits: ControlLimits | None = None,
    ):
        self.mode_enabled = bool(mode_enabled)
        self.control_active = False
        self.platform = platform or sys.platform
        self._screen_size_provider = screen_size_provider
        if backend is not None:
            self._backend: InputBackend | None = backend
        elif sender is not None:
            self._backend = CallbackInputBackend(sender=sender, screen_size_provider=screen_size_provider or self._default_screen_size)
        else:
            self._backend = None
        self._limits = limits or ControlLimits()

    @property
    def enabled(self) -> bool:
        return self.mode_enabled and self.control_active

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(message, dict):
            raise InputControllerError("CONTROL_MESSAGE_INVALID", "Control message must be an object")
        message_type = str(message.get("type") or "").strip()
        if message_type == "control_enable":
            self._assert_mode_enabled()
            self.control_active = True
            return {"type": "control.enabled"}
        if message_type == "control_disable":
            self.control_active = False
            return {"type": "control.disabled"}
        self._assert_active()

        if message_type == "mouse_move":
            action = self._mouse_action(message, action="move")
        elif message_type in {"mouse_click", "mouse_down", "mouse_up"}:
            action_name = message_type.removeprefix("mouse_")
            action = self._mouse_action(message, action=action_name)
            action["button"] = self._button(message.get("button"))
        elif message_type == "mouse_wheel":
            action = self._mouse_action(message, action="wheel")
            action["delta_x"] = self._wheel_delta(message.get("delta_x"))
            action["delta_y"] = self._wheel_delta(message.get("delta_y"))
        elif message_type in {"key_down", "key_up"}:
            action = {"kind": message_type, "key": self._key(message.get("key"))}
        elif message_type == "key_press":
            action = {
                "kind": "key_press",
                "key": self._key(message.get("key")),
                "modifiers": self._modifiers(message.get("modifiers")),
            }
        elif message_type == "text_input":
            text = str(message.get("text") or "")
            if not text or len(text) > self._limits.max_text_chars:
                raise InputControllerError("CONTROL_TEXT_INVALID", "Text input is empty or too large")
            action = {"kind": "text_input", "text": text}
        elif message_type in {"clipboard_enable", "clipboard_disable"} or message_type.startswith("clipboard.") or message_type.startswith("file."):
            raise InputControllerError("FEATURE_NOT_ENABLED", "This Remote Assist channel is not enabled")
        else:
            raise InputControllerError("CONTROL_TYPE_NOT_ALLOWED", "Control message type is not allowed")

        self._assert_supported()
        self._get_backend().send(action)
        return {"type": "control.accepted", "action": action["kind"]}

    def _assert_mode_enabled(self) -> None:
        if not self.mode_enabled:
            raise InputControllerError("CONTROL_DISABLED", "Remote Assist control mode is disabled")
        self._assert_supported()

    def _assert_active(self) -> None:
        self._assert_mode_enabled()
        if not self.control_active:
            raise InputControllerError("CONTROL_NOT_ACTIVE", "Remote Assist control is not active")

    def _assert_supported(self) -> None:
        self._get_backend()

    def _get_backend(self) -> InputBackend:
        if self._backend is not None:
            return self._backend
        platform = self.platform.lower()
        try:
            if platform.startswith("win"):
                self._backend = WindowsSendInputBackend(screen_size_provider=self._screen_size_provider)
            elif platform.startswith("linux"):
                self._backend = LinuxPynputInputBackend(screen_size_provider=self._screen_size_provider)
            else:
                raise InputControllerError("CONTROL_UNSUPPORTED", "Remote Assist control is not supported on this platform")
        except InputControllerError:
            raise
        except Exception as exc:
            raise InputControllerError("CONTROL_UNSUPPORTED", "Remote Assist control backend is unavailable") from exc
        return self._backend

    def _mouse_action(self, message: dict[str, Any], *, action: str) -> dict[str, Any]:
        x_ratio = self._ratio(message.get("x_ratio"))
        y_ratio = self._ratio(message.get("y_ratio"))
        width, height = self._get_backend().screen_size()
        x = max(0, min(width - 1, int(round(x_ratio * max(1, width - 1)))))
        y = max(0, min(height - 1, int(round(y_ratio * max(1, height - 1)))))
        return {"kind": f"mouse_{action}", "x": x, "y": y}

    @staticmethod
    def _ratio(value: Any) -> float:
        try:
            ratio = float(value)
        except (TypeError, ValueError) as exc:
            raise InputControllerError("CONTROL_COORDINATE_INVALID", "Coordinate ratio is invalid") from exc
        if ratio < 0.0 or ratio > 1.0:
            raise InputControllerError("CONTROL_COORDINATE_INVALID", "Coordinate ratio must be between 0 and 1")
        return ratio

    @staticmethod
    def _button(value: Any) -> str:
        button = str(value or "left").strip().lower()
        if button not in {"left", "right", "middle"}:
            raise InputControllerError("CONTROL_BUTTON_INVALID", "Mouse button is invalid")
        return button

    @staticmethod
    def _wheel_delta(value: Any) -> int:
        try:
            delta = int(value)
        except (TypeError, ValueError):
            return 0
        return max(-1200, min(1200, delta))

    @staticmethod
    def _modifiers(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        allowed = {"Control", "Alt", "Shift", "Meta"}
        result: list[str] = []
        for item in value:
            modifier = str(item or "").strip()
            if modifier in allowed and modifier not in result:
                result.append(modifier)
        return result

    @staticmethod
    def _key(value: Any) -> str:
        key = str(value or "").strip()
        if not key or len(key) > 32:
            raise InputControllerError("CONTROL_KEY_INVALID", "Keyboard key is invalid")
        return key

    def _default_screen_size(self) -> tuple[int, int]:
        return self._get_backend().screen_size()


import ctypes
from ctypes import wintypes


_INPUT_MOUSE = 0
_INPUT_KEYBOARD = 1
_MOUSEEVENTF_MOVE = 0x0001
_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004
_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP = 0x0010
_MOUSEEVENTF_MIDDLEDOWN = 0x0020
_MOUSEEVENTF_MIDDLEUP = 0x0040
_MOUSEEVENTF_WHEEL = 0x0800
_MOUSEEVENTF_ABSOLUTE = 0x8000
_MOUSEEVENTF_VIRTUALDESK = 0x4000
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004
_ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_UNION),
    ]


def _mouse_input(*, dx: int, dy: int, flags: int, mouse_data: int = 0) -> _INPUT:
    return _INPUT(type=_INPUT_MOUSE, u=_INPUT_UNION(mi=_MOUSEINPUT(dx, dy, mouse_data, flags, 0, 0)))


def _keyboard_input(*, vk: int = 0, scan: int = 0, flags: int = 0) -> _INPUT:
    return _INPUT(type=_INPUT_KEYBOARD, u=_INPUT_UNION(ki=_KEYBDINPUT(vk, scan, flags, 0, 0)))


def _mouse_button_flags(button: str) -> tuple[int, int]:
    return {
        "left": (_MOUSEEVENTF_LEFTDOWN, _MOUSEEVENTF_LEFTUP),
        "right": (_MOUSEEVENTF_RIGHTDOWN, _MOUSEEVENTF_RIGHTUP),
        "middle": (_MOUSEEVENTF_MIDDLEDOWN, _MOUSEEVENTF_MIDDLEUP),
    }[button]


def _mouse_button_down_flag(button: str) -> int:
    return _mouse_button_flags(button)[0]


def _mouse_button_up_flag(button: str) -> int:
    return _mouse_button_flags(button)[1]


def _utf16_code_units(text: str) -> list[int]:
    encoded = text.encode("utf-16-le")
    return [int.from_bytes(encoded[index : index + 2], "little") for index in range(0, len(encoded), 2)]


def _get_linux_primary_screen_size() -> tuple[int, int]:
    try:
        import mss

        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            return int(monitor["width"]), int(monitor["height"])
    except Exception as exc:
        raise InputControllerError("CONTROL_UNSUPPORTED", "Linux screen size detection requires an available display") from exc


def _virtual_key(key: str, user32: Any) -> int:
    special = {
        "Control": 0x11,
        "Alt": 0x12,
        "Shift": 0x10,
        "Meta": 0x5B,
        "Enter": 0x0D,
        "Tab": 0x09,
        "Escape": 0x1B,
        "Backspace": 0x08,
        "Delete": 0x2E,
        "ArrowLeft": 0x25,
        "ArrowUp": 0x26,
        "ArrowRight": 0x27,
        "ArrowDown": 0x28,
        "Home": 0x24,
        "End": 0x23,
        "PageUp": 0x21,
        "PageDown": 0x22,
        "Space": 0x20,
    }
    if key in special:
        return special[key]
    if len(key) == 1:
        vk = user32.VkKeyScanW(ord(key)) & 0xFF
        if vk != 0xFF:
            return int(vk)
    raise InputControllerError("CONTROL_KEY_UNSUPPORTED", "Keyboard key is unsupported")


def _keyboard_shortcut_inputs(key: str, modifiers: list[str], user32: Any) -> list[_INPUT]:
    inputs: list[_INPUT] = []
    modifier_vks = [_virtual_key(modifier, user32) for modifier in modifiers]
    for vk in modifier_vks:
        inputs.append(_keyboard_input(vk=vk, flags=0))
    key_vk = _virtual_key(key, user32)
    inputs.append(_keyboard_input(vk=key_vk, flags=0))
    inputs.append(_keyboard_input(vk=key_vk, flags=_KEYEVENTF_KEYUP))
    for vk in reversed(modifier_vks):
        inputs.append(_keyboard_input(vk=vk, flags=_KEYEVENTF_KEYUP))
    return inputs
