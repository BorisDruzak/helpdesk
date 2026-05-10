from __future__ import annotations

import asyncio
from typing import Any

from PySide6.QtCore import QThread, Signal
from loguru import logger

from .webrtc_client import RemoteAssistWebRTCClient


class RemoteAssistThread(QThread):
    failed = Signal(str)
    ended = Signal()
    state_changed = Signal(str)

    def __init__(
        self,
        *,
        signaling_url: str,
        token: str,
        ice_servers: list[dict[str, Any]] | None = None,
        mode: str = "view_only",
        media: dict[str, Any] | None = None,
        features: dict[str, Any] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.client = RemoteAssistWebRTCClient(
            signaling_url=signaling_url,
            token=token,
            ice_servers=ice_servers,
            mode=mode,
            media=media,
            features=features,
            on_state_change=self.state_changed.emit,
        )
        self._loop: asyncio.AbstractEventLoop | None = None

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self.client.run())
        except Exception as exc:
            logger.exception(f"Remote Assist WebRTC failed: {exc}")
            self.failed.emit(str(exc))
        finally:
            try:
                self._loop.run_until_complete(self.client.stop())
            finally:
                self._loop.close()
                self.ended.emit()

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(lambda: asyncio.create_task(self.client.stop()))
