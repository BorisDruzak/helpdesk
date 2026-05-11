import json
import socket
import threading

import pytest

from pc_agent.remote_assist.elevated_helper import ElevatedInputProxyBackend, _SocketLineReader, run_elevated_helper_client


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


def test_elevated_helper_client_survives_idle_socket_timeout() -> None:
    token = "idle-token"
    ready = threading.Event()
    result: dict[str, object] = {}

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = int(server.getsockname()[1])

    def run_server() -> None:
        try:
            ready.set()
            conn, _ = server.accept()
            with conn:
                reader = conn.makefile("r", encoding="utf-8", newline="\n")
                writer = conn.makefile("w", encoding="utf-8", newline="\n")
                hello = json.loads(reader.readline())
                result["hello"] = hello
                threading.Event().wait(2.4)
                writer.write(json.dumps({"type": "stop"}) + "\n")
                writer.flush()
                result["stop_response"] = json.loads(reader.readline())
        finally:
            server.close()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    assert ready.wait(2)

    assert run_elevated_helper_client(host="127.0.0.1", port=port, token=token, idle_timeout_sec=30) == 0
    thread.join(timeout=2)

    assert result["hello"] == {"type": "hello", "token": token}
    assert result["stop_response"] == {"status": "ok"}


def test_socket_line_reader_treats_timed_out_oserror_as_idle_timeout() -> None:
    class TimedOutSocket:
        def recv(self, size: int) -> bytes:
            raise OSError("cannot read from timed out object")

    reader = _SocketLineReader(TimedOutSocket())  # type: ignore[arg-type]

    assert reader.readline(1024) is None
