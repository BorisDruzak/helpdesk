"""
Модуль для снятия скриншотов и записи экрана (пакет для загрузки на сервер и установки на агенты).

Использует mss для захвата экрана, ffmpeg для записи видео. При загрузке из modules_store
импорты идут через agent_dir в sys.path (modules.*, core.*).
"""

import asyncio
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional

import mss
import mss.tools
from loguru import logger
from pydantic import BaseModel, Field

from modules.base_module import BaseCollector
from pc_agent.config.config_loader import get_config
from core.registry import exposed_tool
from core.recording_controller import get_recording_controller

SIZE_LIMIT_BYTES = 200 * 1024 * 1024


def _get_ffmpeg_path() -> Optional[str]:
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    return None


class ScreenCollectParams(BaseModel):
    monitor: int = 1
    include_cursor: bool = False


class ScreenRecordParams(BaseModel):
    duration_sec: int = Field(ge=1, le=300, description="Длительность записи 1–300 сек")
    fps: int = Field(default=15, ge=5, le=30)
    max_width: int = Field(default=1920, ge=640, le=3840)
    quality_crf: int = Field(default=28, ge=18, le=40)
    monitor: int = Field(default=1)


class ScreenCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "screen"

    def __init__(self):
        super().__init__()
        self.sct = mss.mss()
        self.temp_dir = Path(get_config().paths.data_dir) / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"[{self.name}] ScreenCollector инициализирован (packaged)")

    @exposed_tool(
        name="collect",
        description="Capture screenshot of the screen",
        risk_level="sensitive_read",
        params_model=ScreenCollectParams,
        presets=[
            {"id": "primary_monitor", "name": "Основной монитор", "description": "Снимок основного монитора", "params": {"monitor": 1, "include_cursor": False}},
            {"id": "all_monitors", "name": "Все мониторы", "description": "Снимок всех мониторов в один файл", "params": {"monitor": -1, "include_cursor": False}},
            {"id": "secondary_monitor", "name": "Второй монитор", "description": "Снимок второго монитора", "params": {"monitor": 2, "include_cursor": False}},
        ],
        metadata_risk_level="sensitive_read",
        metadata_scopes=["screen"],
        metadata_requires_consent=False,
        metadata_allow_roles=["user", "agent", "llm", "support", "admin"],
    )
    async def collect(self, monitor: int = 1, include_cursor: bool = False) -> Dict[str, Any]:
        with self.trace_span("tool.entry", details={"tool_name": "screen.collect"}):
            return await self._collect_impl(monitor=monitor, include_cursor=include_cursor)

    async def _collect_impl(self, monitor: int = 1, include_cursor: bool = False) -> Dict[str, Any]:
        logger.debug(f"[{self.name}] Снятие скриншота (monitor={monitor})")
        timestamp = int(time.time())
        temp_path = self.temp_dir / f"screenshot_{timestamp}.png"
        try:
            screenshot_path = self.sct.shot(mon=monitor, output=str(temp_path))
            logger.success(f"[{self.name}] Скриншот сохранен: {screenshot_path}")
            if monitor == -1:
                monitor_info = self.sct.monitors[-1]
            else:
                mon_idx = 0 if monitor == 0 else monitor
                if mon_idx < len(self.sct.monitors):
                    monitor_info = self.sct.monitors[mon_idx]
                else:
                    monitor_info = self.sct.monitors[1] if len(self.sct.monitors) > 1 else self.sct.monitors[0]
            resolution = f"{monitor_info['width']}x{monitor_info['height']}"
            absolute_path = temp_path.resolve()
            return {
                "resolution": resolution,
                "captured_at_epoch": timestamp,
                "_artifacts": [{"kind": "screenshot", "local_path": str(absolute_path), "name": f"screenshot_{timestamp}.png", "mime": "image/png"}],
                "_cleanup_paths": [str(absolute_path)],
            }
        except Exception as e:
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise

    @exposed_tool(
        name="record",
        description="Record screen to MP4 video (1–300 sec, up to 200MB)",
        risk_level="sensitive_read",
        params_model=ScreenRecordParams,
        presets=[
            {"id": "short", "name": "30 сек", "description": "Короткая запись 30 сек", "params": {"duration_sec": 30}},
            {"id": "long", "name": "5 мин", "description": "Длинная запись 5 мин", "params": {"duration_sec": 300}},
        ],
        metadata_risk_level="sensitive_read",
        metadata_scopes=["screen"],
        metadata_requires_consent=False,
        metadata_allow_roles=["user", "agent", "llm", "support", "admin"],
    )
    async def record(
        self,
        duration_sec: int = 300,
        fps: int = 15,
        max_width: int = 1920,
        quality_crf: int = 28,
        monitor: int = 1,
        operation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.trace_span("tool.entry", details={"tool_name": "screen.record"}):
            return await self._record_impl(
                duration_sec=duration_sec,
                fps=fps,
                max_width=max_width,
                quality_crf=quality_crf,
                monitor=monitor,
                operation_id=operation_id,
            )

    async def _record_impl(
        self,
        duration_sec: int = 300,
        fps: int = 15,
        max_width: int = 1920,
        quality_crf: int = 28,
        monitor: int = 1,
        operation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ffmpeg_path = _get_ffmpeg_path()
        if not ffmpeg_path:
            raise RuntimeError(
                "ffmpeg не найден. Установите: системный ffmpeg или pip install imageio-ffmpeg"
            )
        stop_event = get_recording_controller().get(operation_id) if operation_id else None
        timestamp = int(time.time())
        temp_path = self.temp_dir / f"recording_{timestamp}.mp4"
        try:
            result = await asyncio.to_thread(
                _record_sync,
                ffmpeg_path, monitor, fps, duration_sec, max_width, quality_crf,
                SIZE_LIMIT_BYTES, str(temp_path), stop_event,
            )
            if result.get("error"):
                raise RuntimeError(result["error"])
            frames_captured = result.get("frames_captured", 0)
            logger.success(f"[{self.name}] Запись завершена: {frames_captured} кадров")
            absolute_path = temp_path.resolve()
            return {
                "frames_captured": frames_captured,
                "duration_sec": result.get("duration_actual_sec", 0),
                "file_size_bytes": absolute_path.stat().st_size,
                "_artifacts": [{"kind": "screen_recording", "local_path": str(absolute_path), "name": f"recording_{timestamp}.mp4", "mime": "video/mp4"}],
                "_cleanup_paths": [str(absolute_path)],
            }
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise


def _record_sync(
    ffmpeg_path: str, monitor: int, fps: int, duration_sec: int, max_width: int,
    quality_crf: int, size_limit_bytes: int, output_path: str, stop_event: Optional[object],
) -> Dict[str, Any]:
    import time as time_mod
    max_frames = fps * duration_sec
    with mss.mss() as sct:
        mon_idx = 0 if monitor <= 0 else monitor
        if mon_idx >= len(sct.monitors):
            mon_idx = 1
        img = sct.grab(sct.monitors[mon_idx])
        w, h = img.width, img.height
        scale = f"scale={max_width}:-2" if w > max_width else "copy"
        cmd = [
            ffmpeg_path, "-y",
            "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{w}x{h}", "-r", str(fps),
            "-i", "pipe:0", "-vf", scale,
            "-c:v", "libx264", "-crf", str(quality_crf),
            "-movflags", "+faststart", "-pix_fmt", "yuv420p",
            output_path,
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        frames_captured = 0
        start = time_mod.time()
        try:
            for i in range(max_frames):
                if stop_event is not None and getattr(stop_event, "is_set", lambda: False) and stop_event.is_set():
                    break
                try:
                    img = sct.grab(sct.monitors[mon_idx])
                    proc.stdin.write(img.raw)
                    frames_captured += 1
                except BrokenPipeError:
                    break
                if frames_captured % (fps * 5) == 0 and frames_captured > 0:
                    if os.path.exists(output_path) and os.path.getsize(output_path) >= size_limit_bytes:
                        break
                time_mod.sleep(1.0 / fps)
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.wait(timeout=30)
    duration_actual = time_mod.time() - start
    if os.path.exists(output_path) and os.path.getsize(output_path) > size_limit_bytes:
        logger.warning(f"[screen] Размер записи превысил лимит {size_limit_bytes // (1024*1024)} MB")
    return {"frames_captured": frames_captured, "duration_actual_sec": round(duration_actual, 1), "error": None}


def register():
    """Entrypoint для загрузки из modules_store (manifest entrypoint: module:register)."""
    return ScreenCollector()
