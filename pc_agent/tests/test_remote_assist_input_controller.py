import pytest

from pc_agent.remote_assist.input_controller import InputController


def test_remote_assist_input_controller_is_disabled_in_mvp() -> None:
    controller = InputController()

    assert controller.enabled is False
    with pytest.raises(RuntimeError):
        controller.handle_message({"type": "mouse_move"})
