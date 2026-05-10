from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import threading
import time
from typing import Any

import mss
from loguru import logger


class MssCaptureWorker:
    def __init__(
        self,
        *,
        max_width: int,
        max_height: int,
        capture_timeout_sec: float = 2.0,
        max_consecutive_failures: int = 3,
    ) -> None:
        self.max_width = max_width
        self.max_height = max_height
        self.capture_timeout_sec = max(0.5, float(capture_timeout_sec))
        self.max_consecutive_failures = max(1, int(max_consecutive_failures))
        self._executor = self._new_executor()
        self._capture_local = threading.local()
        self._consecutive_failures = 0
        self._last_warning_at = 0.0

    async def capture(self):
        loop = asyncio.get_running_loop()
        capture_local = self._capture_local
        try:
            image = await asyncio.wait_for(
                loop.run_in_executor(self._executor, self._capture_sync, capture_local),
                timeout=self.capture_timeout_sec,
            )
            self._consecutive_failures = 0
            return image
        except asyncio.TimeoutError:
            self._replace_executor()
            return self._fallback_frame("Screen capture stalled")
        except Exception as exc:
            self._replace_executor()
            return self._fallback_frame(f"Screen capture error: {type(exc).__name__}")

    def close(self) -> None:
        self._close_capture_context(self._capture_local)
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _replace_executor(self) -> None:
        self._consecutive_failures += 1
        self._log_capture_warning()
        old_executor = self._executor
        self._capture_local = threading.local()
        self._executor = self._new_executor()
        old_executor.shutdown(wait=False, cancel_futures=True)

    def _capture_sync(self, capture_local: threading.local):
        from PIL import Image

        sct = getattr(capture_local, "sct", None)
        monitor = getattr(capture_local, "monitor", None)
        if sct is None or monitor is None:
            sct = mss.mss()
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            capture_local.sct = sct
            capture_local.monitor = monitor
        raw = sct.grab(monitor)
        image = Image.frombytes("RGB", raw.size, raw.rgb)
        resampling = getattr(getattr(Image, "Resampling", Image), "BILINEAR")
        image.thumbnail((self.max_width, self.max_height), resampling)
        return image

    def _fallback_frame(self, message: str):
        from PIL import Image, ImageDraw

        width = max(320, min(self.max_width, 960))
        height = max(180, min(self.max_height, 540))
        image = Image.new("RGB", (width, height), (15, 23, 42))
        draw = ImageDraw.Draw(image)
        text = f"{message}\nRetrying capture...\n{time.strftime('%H:%M:%S')}"
        draw.multiline_text((24, 24), text, fill=(226, 232, 240), spacing=8)
        return image

    def _log_capture_warning(self) -> None:
        now = time.monotonic()
        if now - self._last_warning_at < 5:
            return
        self._last_warning_at = now
        logger.warning(
            "Remote Assist screen capture interrupted; retrying with a fresh capture worker (consecutive_failures={})",
            self._consecutive_failures,
        )

    @staticmethod
    def _new_executor() -> ThreadPoolExecutor:
        return ThreadPoolExecutor(max_workers=1, thread_name_prefix="remote-assist-capture")

    @staticmethod
    def _close_capture_context(capture_local: threading.local) -> None:
        sct = getattr(capture_local, "sct", None)
        if sct is not None:
            try:
                sct.close()
            except Exception:
                pass


class ScreenCaptureTrack:
    """Factory wrapper that creates an aiortc VideoStreamTrack for the primary monitor."""

    @staticmethod
    def create(max_width: int = 1280, max_height: int = 720, fps: int = 5):
        from aiortc import VideoStreamTrack
        from av import VideoFrame

        class _MssScreenTrack(VideoStreamTrack):
            kind = "video"

            def __init__(self) -> None:
                super().__init__()
                self._fps = max(1, fps)
                self._frame_index = 0
                self._capture_worker = MssCaptureWorker(max_width=max_width, max_height=max_height)

            async def recv(self) -> Any:
                await asyncio.sleep(1 / self._fps)
                image = await self._capture_worker.capture()
                frame = VideoFrame.from_image(image)
                frame.pts = self._frame_index
                frame.time_base = Fraction(1, self._fps)
                self._frame_index += 1
                return frame

            def stop(self) -> None:
                self._capture_worker.close()
                super().stop()

        return _MssScreenTrack()
