from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from pc_agent.version import AGENT_VERSION

from .input_controller import InputControllerError, ScreenSizeProvider, WindowsSendInputBackend


_LOCALHOST = "127.0.0.1"
_MAX_MESSAGE_BYTES = 64 * 1024


class ElevatedInputProxyBackend:
    """Session-scoped proxy to a UAC-elevated helper process.

    The main agent stays unelevated. For `elevated_admin` sessions it opens a
    localhost listener, launches the same `pc_agent.exe` with a helper CLI flag
    through UAC, and sends validated input actions to that helper.
    """

    def __init__(
        self,
        *,
        screen_size_provider: ScreenSizeProvider | None = None,
        launcher: Callable[[int, str], None] | None = None,
        connect_timeout_sec: float = 30.0,
        request_timeout_sec: float = 10.0,
    ):
        if not sys.platform.startswith("win"):
            raise InputControllerError("ELEVATION_UNSUPPORTED", "Elevated Remote Assist is only supported on Windows")
        self._screen_backend = WindowsSendInputBackend(screen_size_provider=screen_size_provider)
        self._launcher = launcher or launch_elevated_helper
        self._connect_timeout_sec = max(5.0, float(connect_timeout_sec))
        self._request_timeout_sec = max(2.0, float(request_timeout_sec))
        self._server: socket.socket | None = None
        self._conn: socket.socket | None = None
        self._reader: _SocketLineReader | None = None
        self._writer = None

    def screen_size(self) -> tuple[int, int]:
        return self._screen_backend.screen_size()

    def send(self, action: dict[str, Any]) -> None:
        self._ensure_connected()
        response = self._request({"type": "input", "action": action})
        if response.get("status") != "ok":
            error_code = str(response.get("error_code") or "ELEVATED_INPUT_FAILED")
            error = str(response.get("error") or "Elevated input helper rejected input")
            raise InputControllerError(error_code, error)

    def close(self) -> None:
        try:
            if self._conn is not None:
                self._request({"type": "stop"})
        except Exception:
            pass
        for item in (self._reader, self._writer, self._conn, self._server):
            try:
                if item is not None:
                    item.close()
            except Exception:
                pass
        self._reader = None
        self._writer = None
        self._conn = None
        self._server = None

    def _ensure_connected(self) -> None:
        if self._conn is not None:
            return
        token = secrets.token_urlsafe(32)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((_LOCALHOST, 0))
        server.listen(1)
        server.settimeout(self._connect_timeout_sec)
        self._server = server
        port = int(server.getsockname()[1])
        self._launcher(port, token)
        try:
            conn, address = server.accept()
        except socket.timeout as exc:
            raise InputControllerError("ELEVATION_TIMEOUT", "Elevated helper did not connect after UAC prompt") from exc
        if address[0] != _LOCALHOST:
            conn.close()
            raise InputControllerError("ELEVATION_PEER_INVALID", "Elevated helper connected from an unexpected address")
        conn.settimeout(self._request_timeout_sec)
        self._conn = conn
        self._reader = _SocketLineReader(conn)
        self._writer = conn.makefile("w", encoding="utf-8", newline="\n")
        hello = self._read_json()
        if hello.get("type") != "hello" or not secrets.compare_digest(str(hello.get("token") or ""), token):
            self.close()
            raise InputControllerError("ELEVATION_TOKEN_INVALID", "Elevated helper token validation failed")

    def _request(self, message: dict[str, Any]) -> dict[str, Any]:
        try:
            self._write_json(message)
            return self._read_json()
        except InputControllerError:
            self._drop_connection()
            raise

    def _write_json(self, message: dict[str, Any]) -> None:
        if self._writer is None:
            raise InputControllerError("ELEVATION_NOT_CONNECTED", "Elevated helper is not connected")
        text = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        if len(text.encode("utf-8")) > _MAX_MESSAGE_BYTES:
            raise InputControllerError("ELEVATION_MESSAGE_TOO_LARGE", "Elevated helper message is too large")
        try:
            self._writer.write(text + "\n")
            self._writer.flush()
        except OSError as exc:
            raise InputControllerError("ELEVATION_DISCONNECTED", "Elevated helper disconnected") from exc

    def _read_json(self) -> dict[str, Any]:
        if self._reader is None:
            raise InputControllerError("ELEVATION_NOT_CONNECTED", "Elevated helper is not connected")
        line = self._reader.readline(_MAX_MESSAGE_BYTES + 1)
        if line is None:
            raise InputControllerError("ELEVATION_RESPONSE_TIMEOUT", "Elevated helper did not respond in time")
        if not line:
            raise InputControllerError("ELEVATION_DISCONNECTED", "Elevated helper disconnected")
        if len(line.encode("utf-8")) > _MAX_MESSAGE_BYTES:
            raise InputControllerError("ELEVATION_MESSAGE_TOO_LARGE", "Elevated helper response is too large")
        try:
            message = json.loads(line)
        except ValueError as exc:
            raise InputControllerError("ELEVATION_MESSAGE_INVALID", "Elevated helper response is invalid") from exc
        if not isinstance(message, dict):
            raise InputControllerError("ELEVATION_MESSAGE_INVALID", "Elevated helper response must be an object")
        return message

    def _drop_connection(self) -> None:
        for item in (self._writer, self._conn):
            try:
                if item is not None:
                    item.close()
            except Exception:
                pass
        self._reader = None
        self._writer = None
        self._conn = None


def launch_elevated_helper(port: int, token: str) -> None:
    if not sys.platform.startswith("win"):
        raise InputControllerError("ELEVATION_UNSUPPORTED", "Elevated Remote Assist is only supported on Windows")
    import ctypes

    executable = str(Path(sys.executable).resolve())
    logger.info(
        "Remote Assist elevated helper launch requested: agent_version={} executable={} cwd={} port={}",
        AGENT_VERSION,
        executable,
        os.getcwd(),
        int(port),
    )
    args = subprocess.list2cmdline(
        [
            "--remote-assist-elevated-helper",
            "--host",
            _LOCALHOST,
            "--port",
            str(int(port)),
            "--token",
            token,
        ]
    )
    rc = int(ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, args, os.getcwd(), 1))
    logger.info("Remote Assist elevated helper ShellExecuteW returned: shell_code={} executable={}", rc, executable)
    if rc <= 32:
        raise InputControllerError("ELEVATION_DENIED", f"Windows elevation prompt failed or was denied; shell_code={rc}")


def run_elevated_helper_client(*, host: str, port: int, token: str, idle_timeout_sec: int = 900) -> int:
    if not sys.platform.startswith("win"):
        return 2
    executable = str(Path(sys.executable).resolve())
    logger.info(
        "Remote Assist elevated helper client starting: agent_version={} pid={} executable={} host={} port={}",
        AGENT_VERSION,
        os.getpid(),
        executable,
        host,
        int(port),
    )
    try:
        backend = WindowsSendInputBackend()
        deadline = time.monotonic() + max(30, int(idle_timeout_sec))
        with socket.create_connection((host, int(port)), timeout=30) as conn:
            conn.settimeout(2.0)
            reader = _SocketLineReader(conn)
            writer = conn.makefile("w", encoding="utf-8", newline="\n")
            _helper_write(writer, {"type": "hello", "token": token})
            while time.monotonic() < deadline:
                line = reader.readline(_MAX_MESSAGE_BYTES + 1)
                if line is None:
                    continue
                if not line:
                    logger.info("Remote Assist elevated helper client disconnected by parent")
                    return 0
                if len(line.encode("utf-8")) > _MAX_MESSAGE_BYTES:
                    _helper_write(writer, {"status": "error", "error_code": "ELEVATED_MESSAGE_TOO_LARGE", "error": "Message is too large"})
                    continue
                try:
                    message = json.loads(line)
                except ValueError:
                    _helper_write(writer, {"status": "error", "error_code": "ELEVATED_MESSAGE_INVALID", "error": "Message is invalid"})
                    continue
                if not isinstance(message, dict):
                    _helper_write(writer, {"status": "error", "error_code": "ELEVATED_MESSAGE_INVALID", "error": "Message must be an object"})
                    continue
                if message.get("type") == "stop":
                    _helper_write(writer, {"status": "ok"})
                    logger.info("Remote Assist elevated helper client stopped by parent")
                    return 0
                if message.get("type") != "input" or not isinstance(message.get("action"), dict):
                    _helper_write(writer, {"status": "error", "error_code": "ELEVATED_TYPE_NOT_ALLOWED", "error": "Message type is not allowed"})
                    continue
                try:
                    backend.send(message["action"])
                except InputControllerError as exc:
                    _helper_write(writer, {"status": "error", "error_code": exc.code, "error": exc.message})
                except Exception as exc:
                    _helper_write(writer, {"status": "error", "error_code": "ELEVATED_INPUT_FAILED", "error": str(exc)})
                else:
                    deadline = time.monotonic() + max(30, int(idle_timeout_sec))
                    _helper_write(writer, {"status": "ok"})
        logger.info("Remote Assist elevated helper client connection closed")
        return 0
    except (OSError, TimeoutError) as exc:
        logger.warning(
            "Remote Assist elevated helper client socket failure: agent_version={} pid={} executable={} error={}",
            AGENT_VERSION,
            os.getpid(),
            executable,
            exc,
        )
        return 1


def _helper_write(writer: Any, message: dict[str, Any]) -> None:
    writer.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
    writer.flush()


class _SocketLineReader:
    """Timeout-safe newline reader for sockets.

    `socket.makefile().readline()` becomes unusable after a socket timeout on
    some Python versions and then raises `OSError: cannot read from timed out
    object`. Remote Assist elevated helper uses short idle timeouts, so read
    directly from the socket and keep the partial line buffer ourselves.
    """

    def __init__(self, conn: socket.socket):
        self._conn = conn
        self._buffer = bytearray()

    def readline(self, limit: int) -> str | None:
        while b"\n" not in self._buffer:
            if len(self._buffer) > limit:
                break
            try:
                chunk = self._conn.recv(min(4096, max(1, limit + 1 - len(self._buffer))))
            except (socket.timeout, TimeoutError):
                return None
            except OSError as exc:
                if "timed out" in str(exc).lower():
                    return None
                raise
            if not chunk:
                if not self._buffer:
                    return ""
                line = bytes(self._buffer)
                self._buffer.clear()
                return line.decode("utf-8", errors="replace")
            self._buffer.extend(chunk)

        if b"\n" in self._buffer:
            index = self._buffer.index(b"\n") + 1
            line = bytes(self._buffer[:index])
            del self._buffer[:index]
        else:
            line = bytes(self._buffer)
            self._buffer.clear()
        return line.decode("utf-8", errors="replace")
