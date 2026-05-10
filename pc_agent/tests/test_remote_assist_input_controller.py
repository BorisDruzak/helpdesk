import pytest

from pc_agent.remote_assist.input_controller import InputController, InputControllerError


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

    controller.handle_message({"type": "mouse_click", "x_ratio": 1, "y_ratio": 0, "button": "right"})
    controller.handle_message({"type": "key_down", "key": "Enter"})
    controller.handle_message({"type": "key_up", "key": "Enter"})

    assert sent == [
        {"kind": "mouse_click", "x": 1919, "y": 0, "button": "right"},
        {"kind": "key_down", "key": "Enter"},
        {"kind": "key_up", "key": "Enter"},
    ]


def test_control_rejects_unsupported_platform_and_unenabled_features() -> None:
    controller = InputController(mode_enabled=True, platform="linux")

    with pytest.raises(InputControllerError) as exc:
        controller.handle_message({"type": "control_enable"})
    assert exc.value.code == "CONTROL_UNSUPPORTED"

    controller = InputController(mode_enabled=True, platform="win32", sender=lambda _action: None)
    controller.handle_message({"type": "control_enable"})
    with pytest.raises(InputControllerError) as exc:
        controller.handle_message({"type": "clipboard.read"})
    assert exc.value.code == "FEATURE_NOT_ENABLED"
