import asyncio
import time

from PIL import Image

from pc_agent.remote_assist.screen_track import MssCaptureWorker


class FastCaptureWorker(MssCaptureWorker):
    def _capture_sync(self, capture_local):
        return Image.new("RGB", (640, 360), (1, 2, 3))


class StalledCaptureWorker(MssCaptureWorker):
    def _capture_sync(self, capture_local):
        time.sleep(0.7)
        return Image.new("RGB", (640, 360), (1, 2, 3))


def test_capture_worker_returns_captured_frame() -> None:
    worker = FastCaptureWorker(max_width=800, max_height=600)
    try:
        image = asyncio.run(worker.capture())
    finally:
        worker.close()

    assert image.size == (640, 360)


def test_capture_worker_returns_fallback_frame_after_timeout() -> None:
    worker = StalledCaptureWorker(max_width=800, max_height=600, capture_timeout_sec=0.01)
    try:
        image = asyncio.run(worker.capture())
    finally:
        worker.close()

    assert image.size == (800, 540)
    assert worker._consecutive_failures == 1
