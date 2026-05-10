from __future__ import annotations

import asyncio
import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable


class ClipboardError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ClipboardConfig:
    enabled: bool = False
    max_bytes: int = 256 * 1024
    poll_interval_sec: float = 1.0


def clipboard_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ClipboardSyncBridge:
    def __init__(self, *, config: ClipboardConfig, send: Callable[[dict[str, Any]], None], backend: Any | None = None):
        self.config = config
        self.send = send
        self.backend = backend or create_clipboard_backend()
        self.active = False
        self._closed = False
        self._poll_task: asyncio.Task | None = None
        self._last_hash: str | None = None
        self._last_remote_hash: str | None = None

    async def start(self) -> None:
        if not self.config.enabled:
            raise ClipboardError("CLIPBOARD_DISABLED", "Clipboard sync is disabled for this session")
        if self.active:
            return
        self.active = True
        try:
            text = await asyncio.to_thread(self.backend.read_text)
            self._last_hash = clipboard_hash(text)
        except Exception:
            self._last_hash = None
        self._poll_task = asyncio.create_task(self._poll())
        self.send({"type": "clipboard.ready", "payload": {"max_bytes": self.config.max_bytes}})

    async def stop(self) -> None:
        self.active = False
        self._closed = True
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._poll_task = None

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        message_type = str(message.get("type") or "")
        if message_type == "clipboard_enable":
            await self.start()
            return {"type": "clipboard.enabled"}
        if message_type == "clipboard_disable":
            await self.stop()
            return {"type": "clipboard.disabled"}
        if message_type == "clipboard.update":
            await self._apply_remote_text(message.get("payload") if isinstance(message.get("payload"), dict) else {})
            return {"type": "clipboard.applied"}
        raise ClipboardError("CLIPBOARD_MESSAGE_UNSUPPORTED", "Clipboard message is unsupported")

    async def _poll(self) -> None:
        while not self._closed and self.active:
            await asyncio.sleep(self.config.poll_interval_sec)
            try:
                text = await asyncio.to_thread(self.backend.read_text)
                digest = clipboard_hash(text)
                if digest == self._last_hash or digest == self._last_remote_hash:
                    self._last_hash = digest
                    continue
                self._assert_size(text)
                self._last_hash = digest
                self.send({"type": "clipboard.update", "payload": {"text": text, "hash": digest, "origin": "agent"}})
            except ClipboardError as exc:
                self.send({"type": "clipboard.error", "payload": {"error_code": exc.code, "error": exc.message}})
            except Exception as exc:
                self.send({"type": "clipboard.error", "payload": {"error_code": "CLIPBOARD_READ_FAILED", "error": str(exc)}})

    async def _apply_remote_text(self, payload: dict[str, Any]) -> None:
        text = str(payload.get("text") or "")
        self._assert_size(text)
        digest = str(payload.get("hash") or clipboard_hash(text))
        if digest == self._last_hash:
            return
        await asyncio.to_thread(self.backend.write_text, text)
        self._last_remote_hash = digest
        self._last_hash = digest

    def _assert_size(self, text: str) -> None:
        if len(text.encode("utf-8")) > self.config.max_bytes:
            raise ClipboardError("CLIPBOARD_TOO_LARGE", "Clipboard text is too large for Remote Assist sync")


class WindowsClipboardBackend:
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        self.user32.GetClipboardData.restype = ctypes.c_void_p
        self.user32.SetClipboardData.restype = ctypes.c_void_p
        self.user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        self.kernel32.GlobalAlloc.restype = ctypes.c_void_p
        self.kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        self.kernel32.GlobalLock.restype = ctypes.c_void_p
        self.kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        self.kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        self.kernel32.GlobalFree.argtypes = [ctypes.c_void_p]

    def read_text(self) -> str:
        if not self.user32.OpenClipboard(None):
            raise ClipboardError("CLIPBOARD_BUSY", "Clipboard is busy")
        try:
            handle = self.user32.GetClipboardData(self.CF_UNICODETEXT)
            if not handle:
                return ""
            pointer = self.kernel32.GlobalLock(handle)
            if not pointer:
                return ""
            try:
                return ctypes.wstring_at(pointer)
            finally:
                self.kernel32.GlobalUnlock(handle)
        finally:
            self.user32.CloseClipboard()

    def write_text(self, text: str) -> None:
        data = (text + "\0").encode("utf-16-le")
        if not self.user32.OpenClipboard(None):
            raise ClipboardError("CLIPBOARD_BUSY", "Clipboard is busy")
        try:
            if not self.user32.EmptyClipboard():
                raise ClipboardError("CLIPBOARD_WRITE_FAILED", "Failed to clear clipboard")
            handle = self.kernel32.GlobalAlloc(self.GMEM_MOVEABLE, len(data))
            if not handle:
                raise ClipboardError("CLIPBOARD_WRITE_FAILED", "Failed to allocate clipboard memory")
            pointer = self.kernel32.GlobalLock(handle)
            if not pointer:
                self.kernel32.GlobalFree(handle)
                raise ClipboardError("CLIPBOARD_WRITE_FAILED", "Failed to lock clipboard memory")
            try:
                ctypes.memmove(pointer, data, len(data))
            finally:
                self.kernel32.GlobalUnlock(handle)
            if not self.user32.SetClipboardData(self.CF_UNICODETEXT, handle):
                self.kernel32.GlobalFree(handle)
                raise ClipboardError("CLIPBOARD_WRITE_FAILED", "Failed to set clipboard data")
        finally:
            self.user32.CloseClipboard()


class LinuxCommandClipboardBackend:
    def __init__(self):
        self.backend = self._detect_backend()
        if self.backend is None:
            raise ClipboardError("CLIPBOARD_UNSUPPORTED", "Linux clipboard sync requires wl-clipboard, xclip, or xsel")

    def read_text(self) -> str:
        command = self.backend["read"]
        completed = subprocess.run(command, capture_output=True, check=False, timeout=2)
        if completed.returncode != 0:
            return ""
        return completed.stdout.decode("utf-8", errors="replace")

    def write_text(self, text: str) -> None:
        command = self.backend["write"]
        subprocess.run(command, input=text.encode("utf-8"), capture_output=True, check=False, timeout=2)

    @staticmethod
    def _detect_backend() -> dict[str, list[str]] | None:
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy") and shutil.which("wl-paste"):
            return {"read": ["wl-paste", "--no-newline"], "write": ["wl-copy"]}
        if shutil.which("xclip"):
            return {"read": ["xclip", "-selection", "clipboard", "-out"], "write": ["xclip", "-selection", "clipboard", "-in"]}
        if shutil.which("xsel"):
            return {"read": ["xsel", "--clipboard", "--output"], "write": ["xsel", "--clipboard", "--input"]}
        return None


class MemoryClipboardBackend:
    def __init__(self, text: str = ""):
        self.text = text
        self.writes: list[str] = []

    def read_text(self) -> str:
        return self.text

    def write_text(self, text: str) -> None:
        self.text = text
        self.writes.append(text)


def create_clipboard_backend() -> Any:
    if sys.platform == "win32":
        return WindowsClipboardBackend()
    if sys.platform.startswith("linux"):
        return LinuxCommandClipboardBackend()
    raise ClipboardError("CLIPBOARD_UNSUPPORTED", "Clipboard sync is unsupported on this platform")
