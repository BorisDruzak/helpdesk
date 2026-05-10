from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class InputControllerError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


InputSender = Callable[[dict[str, Any]], None]
ScreenSizeProvider = Callable[[], tuple[int, int]]


@dataclass(frozen=True, slots=True)
class ControlLimits:
    max_text_chars: int = 256


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
        limits: ControlLimits | None = None,
    ):
        self.mode_enabled = bool(mode_enabled)
        self.control_active = False
        self.platform = platform or sys.platform
        self._sender = sender or self._send_windows_input
        self._screen_size_provider = screen_size_provider or self._get_primary_screen_size
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
        elif message_type == "mouse_click":
            action = self._mouse_action(message, action="click")
            action["button"] = self._button(message.get("button"))
        elif message_type in {"key_down", "key_up"}:
            action = {"kind": message_type, "key": self._key(message.get("key"))}
        elif message_type == "text_input":
            text = str(message.get("text") or "")
            if not text or len(text) > self._limits.max_text_chars:
                raise InputControllerError("CONTROL_TEXT_INVALID", "Text input is empty or too large")
            action = {"kind": "text_input", "text": text}
        elif message_type.startswith("clipboard.") or message_type.startswith("file."):
            raise InputControllerError("FEATURE_NOT_ENABLED", "This Remote Assist channel is not enabled")
        else:
            raise InputControllerError("CONTROL_TYPE_NOT_ALLOWED", "Control message type is not allowed")

        self._assert_supported()
        self._sender(action)
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
        if not self.platform.startswith("win"):
            raise InputControllerError("CONTROL_UNSUPPORTED", "Remote Assist control is supported only on Windows")

    def _mouse_action(self, message: dict[str, Any], *, action: str) -> dict[str, Any]:
        x_ratio = self._ratio(message.get("x_ratio"))
        y_ratio = self._ratio(message.get("y_ratio"))
        width, height = self._screen_size_provider()
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
    def _key(value: Any) -> str:
        key = str(value or "").strip()
        if not key or len(key) > 32:
            raise InputControllerError("CONTROL_KEY_INVALID", "Keyboard key is invalid")
        return key

    @staticmethod
    def _get_primary_screen_size() -> tuple[int, int]:
        import ctypes

        user32 = ctypes.windll.user32
        return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))

    @staticmethod
    def _send_windows_input(action: dict[str, Any]) -> None:
        import ctypes

        user32 = ctypes.windll.user32
        kind = action["kind"]
        if kind in {"mouse_move", "mouse_click"}:
            user32.SetCursorPos(int(action["x"]), int(action["y"]))
        if kind == "mouse_click":
            flags = {
                "left": (0x0002, 0x0004),
                "right": (0x0008, 0x0010),
                "middle": (0x0020, 0x0040),
            }[action["button"]]
            user32.mouse_event(flags[0], 0, 0, 0, 0)
            user32.mouse_event(flags[1], 0, 0, 0, 0)
        elif kind in {"key_down", "key_up"}:
            vk = _virtual_key(action["key"], user32)
            flags = 0 if kind == "key_down" else 0x0002
            user32.keybd_event(vk, 0, flags, 0)
        elif kind == "text_input":
            for char in action["text"]:
                vk = _virtual_key(char, user32)
                user32.keybd_event(vk, 0, 0, 0)
                user32.keybd_event(vk, 0, 0x0002, 0)


def _virtual_key(key: str, user32: Any) -> int:
    special = {
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
