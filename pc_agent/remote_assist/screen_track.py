from __future__ import annotations

import asyncio
from fractions import Fraction
import threading
from typing import Any

import mss


class ScreenCaptureTrack:
    """Factory wrapper that creates an aiortc VideoStreamTrack for the primary monitor."""

    @staticmethod
    def create(max_width: int = 1280, max_height: int = 720, fps: int = 5):
        from aiortc import VideoStreamTrack
        from av import VideoFrame
        from PIL import Image

        class _MssScreenTrack(VideoStreamTrack):
            kind = "video"

            def __init__(self) -> None:
                super().__init__()
                self._fps = max(1, fps)
                self._frame_index = 0
                self._capture_local = threading.local()

            async def recv(self) -> Any:
                await asyncio.sleep(1 / self._fps)
                image = await asyncio.to_thread(self._capture)
                frame = VideoFrame.from_image(image)
                frame.pts = self._frame_index
                frame.time_base = Fraction(1, self._fps)
                self._frame_index += 1
                return frame

            def _capture(self):
                sct = getattr(self._capture_local, "sct", None)
                monitor = getattr(self._capture_local, "monitor", None)
                if sct is None or monitor is None:
                    sct = mss.mss()
                    monitor = sct.monitors[1]
                    self._capture_local.sct = sct
                    self._capture_local.monitor = monitor
                raw = sct.grab(monitor)
                image = Image.frombytes("RGB", raw.size, raw.rgb)
                resampling = getattr(getattr(Image, "Resampling", Image), "BILINEAR")
                image.thumbnail((max_width, max_height), resampling)
                return image

        return _MssScreenTrack()
