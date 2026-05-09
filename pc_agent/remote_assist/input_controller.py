from __future__ import annotations


class InputController:
    """Disabled control-mode placeholder for future Remote Assist releases."""

    enabled = False

    def handle_message(self, message: dict) -> None:
        raise RuntimeError("Remote Assist control mode is disabled in MVP")
