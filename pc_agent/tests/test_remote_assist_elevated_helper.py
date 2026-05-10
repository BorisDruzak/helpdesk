import json
import socket
import threading

import pytest

from pc_agent.remote_assist.elevated_helper import ElevatedInputProxyBackend


pytestmark = pytest.mark.skipif(not __import__("sys").platform.startswith("win"), reason="Windows-only elevated helper proxy")


def test_elevated_input_proxy_uses_one_time_token_and_sends_actions() -> None:
    received_actions: list[dict] = []

    def launcher(port: int, token: str) -> None:
        def run_fake_helper() -> None:
            with socket.create_connection(("127.0.0.1", port), timeout=5) as conn:
                reader = conn.makefile("r", encoding="utf-8", newline="\n")
                writer = conn.makefile("w", encoding="utf-8", newline="\n")
                writer.write(json.dumps({"type": "hello", "token": token}) + "\n")
                writer.flush()
                request = json.loads(reader.readline())
                received_actions.append(request["action"])
                writer.write(json.dumps({"status": "ok"}) + "\n")
                writer.flush()
                stop_request = json.loads(reader.readline())
                assert stop_request == {"type": "stop"}
                writer.write(json.dumps({"status": "ok"}) + "\n")
                writer.flush()

        threading.Thread(target=run_fake_helper, daemon=True).start()

    backend = ElevatedInputProxyBackend(
        screen_size_provider=lambda: (800, 600),
        launcher=launcher,
        connect_timeout_sec=5,
        request_timeout_sec=5,
    )

    assert backend.screen_size() == (800, 600)
    backend.send({"kind": "mouse_click", "x": 10, "y": 20, "button": "left", "click_count": 2})
    backend.close()

    assert received_actions == [{"kind": "mouse_click", "x": 10, "y": 20, "button": "left", "click_count": 2}]
