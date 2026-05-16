"""
Screen capture and recording module.

Supports full-monitor screenshots, all-monitor capture, and selected regions
relative to the chosen monitor.
"""

import asyncio
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

import mss
import mss.tools
from loguru import logger
from pydantic import BaseModel, Field

from pc_agent.modules.base_module import BaseCollector
from pc_agent.config.config_loader import get_config
from pc_agent.core.registry import exposed_tool
from pc_agent.core.recording_controller import get_recording_controller

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
    left: Optional[int] = Field(default=None, ge=0)
    top: Optional[int] = Field(default=None, ge=0)
    width: Optional[int] = Field(default=None, gt=0)
    height: Optional[int] = Field(default=None, gt=0)


class ScreenRecordParams(BaseModel):
    duration_sec: int = Field(ge=1, le=300, description="Recording duration in seconds")
    fps: int = Field(default=15, ge=5, le=30)
    max_width: int = Field(default=1920, ge=640, le=3840)
    quality_crf: int = Field(default=28, ge=18, le=40)
    monitor: int = Field(default=1)


class ScreenCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        self.sct = mss.mss()
        self.temp_dir = Path(get_config().paths.data_dir) / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"[{self.name}] temp dir: {self.temp_dir}")

    @property
    def name(self) -> str:
        return "screen"

    def _resolve_capture_region(
        self,
        *,
        monitor: int,
        left: Optional[int],
        top: Optional[int],
        width: Optional[int],
        height: Optional[int],
    ) -> tuple[dict, str]:
        monitors = self.sct.monitors
        if not monitors:
            raise RuntimeError("No monitors available for screenshot capture")

        monitor_index = 0 if monitor <= 0 else monitor
        if monitor_index >= len(monitors):
            logger.warning(f"[{self.name}] Requested monitor {monitor} not found, falling back to primary")
            monitor_index = 1 if len(monitors) > 1 else 0

        base_monitor = monitors[monitor_index]
        region_requested = any(value is not None for value in (left, top, width, height))
        if not region_requested:
            return dict(base_monitor), "monitor"

        if None in (left, top, width, height):
            raise ValueError("left, top, width and height must be provided together for region capture")

        return {
            "left": int(base_monitor["left"]) + int(left),
            "top": int(base_monitor["top"]) + int(top),
            "width": int(width),
            "height": int(height),
        }, "region"

    @staticmethod
    def _write_screenshot(image: Any, output_path: Path) -> None:
        mss.tools.to_png(image.rgb, image.size, output=str(output_path))

    @exposed_tool(
        name="collect",
        description="Capture screenshot of the screen or a selected region",
        risk_level="sensitive_read",
        params_model=ScreenCollectParams,
        presets=[
            {
                "id": "primary_monitor",
                "name": "Primary monitor",
                "description": "Capture the primary monitor",
                "params": {"monitor": 1, "include_cursor": False},
            },
            {
                "id": "all_monitors",
                "name": "All monitors",
                "description": "Capture all connected monitors in one image",
                "params": {"monitor": -1, "include_cursor": False},
            },
            {
                "id": "secondary_monitor",
                "name": "Secondary monitor",
                "description": "Capture the secondary monitor if it exists",
                "params": {"monitor": 2, "include_cursor": False},
            },
            {
                "id": "region_template",
                "name": "Selected area",
                "description": "Template for region capture relative to the chosen monitor",
                "params": {
                    "monitor": 1,
                    "left": 100,
                    "top": 100,
                    "width": 800,
                    "height": 600,
                    "include_cursor": False,
                },
            },
        ],
        output_schema={
            "type": "object",
            "properties": {
                "resolution": {"type": "string"},
                "capture_mode": {"type": "string"},
                "monitor": {"type": "integer"},
                "region": {"type": "object"},
            },
        },
        metadata_risk_level="sensitive_read",
        metadata_scopes=["screen"],
        metadata_requires_consent=False,
        metadata_allow_roles=["user", "agent", "llm", "support", "admin"],
        contract_version="1.0.0",
        lifecycle="stable",
        error_codes=["VALIDATION_ERROR", "TIMEOUT", "ACCESS_DENIED"],
        artifact_types=[{"kind": "screenshot", "mime": "image/png", "sensitivity": "sensitive"}],
        redaction={"enabled": True, "allow_raw_sensitive_data": False, "redact_headers": True, "redact_env": True, "redact_fields": []},
        resources={"max_runtime_sec": 30, "max_artifact_count": 1, "max_artifact_bytes": 52428800},
        execution={
            "target": "agent_builtin",
            "requires_device": True,
            "requires_agent_online": True,
            "supports_auto_install": False,
            "requires_integration": False,
        },
        deployment={"provider_id": "screen", "install_required_on_agent": False, "package_type": "builtin"},
        safety={"side_effects": False, "requires_consent": False, "idempotent": False},
        evidence={
            "produces_evidence": True,
            "kind": "endpoint.screenshot",
            "domain": "endpoint",
            "perspective": "endpoint",
            "passport_eligible": True,
        },
        artifacts={"may_produce_artifacts": True, "artifact_kinds": ["screenshot"]},
    )
    async def collect(
        self,
        monitor: int = 1,
        include_cursor: bool = False,
        left: Optional[int] = None,
        top: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Dict[str, Any]:
        with self.trace_span("tool.entry", details={"tool_name": "screen.collect"}):
            return await self._collect_impl(
                monitor=monitor,
                include_cursor=include_cursor,
                left=left,
                top=top,
                width=width,
                height=height,
            )

    async def _collect_impl(
        self,
        monitor: int = 1,
        include_cursor: bool = False,
        left: Optional[int] = None,
        top: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Dict[str, Any]:
        logger.debug(
            f"[{self.name}] capture requested "
            f"(monitor={monitor}, include_cursor={include_cursor}, left={left}, top={top}, width={width}, height={height})"
        )
        timestamp = int(time.time())
        temp_path = self.temp_dir / f"screenshot_{timestamp}.png"
        try:
            with self.trace_span(
                "collect.resolve_region",
                details={"monitor": monitor, "region_requested": any(v is not None for v in (left, top, width, height))},
            ):
                capture_region, capture_mode = self._resolve_capture_region(
                    monitor=monitor,
                    left=left,
                    top=top,
                    width=width,
                    height=height,
                )
            with self.trace_span("collect.capture_png", details={"capture_mode": capture_mode}):
                image = self.sct.grab(capture_region)
                self._write_screenshot(image, temp_path)
            absolute_path = temp_path.resolve()
            resolution = f"{capture_region['width']}x{capture_region['height']}"
            self.trace_event(
                "collect.summary",
                summary="screen capture complete",
                details={"capture_mode": capture_mode, "resolution": resolution},
            )
            logger.success(f"[{self.name}] screenshot saved: {absolute_path}")
            return {
                "resolution": resolution,
                "captured_at_epoch": timestamp,
                "capture_mode": capture_mode,
                "monitor": monitor,
                "include_cursor": include_cursor,
                "region": {
                    "left": int(capture_region["left"]),
                    "top": int(capture_region["top"]),
                    "width": int(capture_region["width"]),
                    "height": int(capture_region["height"]),
                },
                "_artifacts": [
                    {
                        "kind": "screenshot",
                        "local_path": str(absolute_path),
                        "name": f"screenshot_{timestamp}.png",
                        "mime": "image/png",
                    }
                ],
                "_cleanup_paths": [str(absolute_path)],
            }
        except mss.ScreenShotError as exc:
            logger.error(f"[{self.name}] screen capture error: {exc}")
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise
        except Exception:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise

    @exposed_tool(
        name="record",
        description="Record screen to MP4 video (1-300 sec, up to 200MB)",
        risk_level="sensitive_read",
        params_model=ScreenRecordParams,
        presets=[
            {"id": "short", "name": "30 sec", "description": "Short recording", "params": {"duration_sec": 30}},
            {"id": "long", "name": "5 min", "description": "Long recording", "params": {"duration_sec": 300}},
        ],
        output_schema={
            "type": "object",
            "properties": {
                "frames_captured": {"type": "integer"},
                "duration_sec": {"type": "number"},
                "file_size_bytes": {"type": "integer"},
            },
        },
        metadata_risk_level="sensitive_read",
        metadata_scopes=["screen"],
        metadata_requires_consent=False,
        metadata_allow_roles=["user", "agent", "llm", "support", "admin"],
        contract_version="1.0.0",
        lifecycle="stable",
        error_codes=["VALIDATION_ERROR", "TIMEOUT", "DEPENDENCY_MISSING", "ACCESS_DENIED"],
        artifact_types=[{"kind": "screen_recording", "mime": "video/mp4", "sensitivity": "sensitive"}],
        redaction={"enabled": True, "allow_raw_sensitive_data": False, "redact_headers": True, "redact_env": True, "redact_fields": []},
        resources={"max_runtime_sec": 360, "max_artifact_count": 1, "max_artifact_bytes": 209715200},
        execution={
            "target": "agent_builtin",
            "requires_device": True,
            "requires_agent_online": True,
            "supports_auto_install": False,
            "requires_integration": False,
        },
        deployment={"provider_id": "screen", "install_required_on_agent": False, "package_type": "builtin"},
        safety={"side_effects": False, "requires_consent": False, "idempotent": False},
        evidence={
            "produces_evidence": True,
            "kind": "endpoint.screen_recording",
            "domain": "endpoint",
            "perspective": "endpoint",
            "passport_eligible": True,
        },
        artifacts={"may_produce_artifacts": True, "artifact_kinds": ["screen_recording"]},
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
        with self.trace_span("record.resolve_ffmpeg"):
            ffmpeg_path = _get_ffmpeg_path()
        if not ffmpeg_path:
            raise RuntimeError(
                "ffmpeg not found. Install a system ffmpeg binary or imageio-ffmpeg."
            )
        stop_event = get_recording_controller().get(operation_id) if operation_id else None
        timestamp = int(time.time())
        temp_path = self.temp_dir / f"recording_{timestamp}.mp4"
        try:
            with self.trace_span(
                "record.capture",
                details={"monitor": monitor, "fps": fps, "duration_sec": duration_sec, "max_width": max_width},
            ):
                result = await asyncio.to_thread(
                    _record_sync,
                    ffmpeg_path,
                    monitor,
                    fps,
                    duration_sec,
                    max_width,
                    quality_crf,
                    SIZE_LIMIT_BYTES,
                    str(temp_path),
                    stop_event,
                )
            if result.get("error"):
                raise RuntimeError(result["error"])
            absolute_path = temp_path.resolve()
            self.trace_event(
                "record.summary",
                summary="screen recording complete",
                details={"frames_captured": result.get("frames_captured", 0), "output_path": str(absolute_path)},
            )
            return {
                "frames_captured": result.get("frames_captured", 0),
                "duration_sec": result.get("duration_actual_sec", 0),
                "file_size_bytes": absolute_path.stat().st_size,
                "_artifacts": [
                    {
                        "kind": "screen_recording",
                        "local_path": str(absolute_path),
                        "name": f"recording_{timestamp}.mp4",
                        "mime": "video/mp4",
                    }
                ],
                "_cleanup_paths": [str(absolute_path)],
            }
        except Exception:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise


def _record_sync(
    ffmpeg_path: str,
    monitor: int,
    fps: int,
    duration_sec: int,
    max_width: int,
    quality_crf: int,
    size_limit_bytes: int,
    output_path: str,
    stop_event: Optional[object],
) -> Dict[str, Any]:
    import time as time_mod

    max_frames = fps * duration_sec
    with mss.mss() as sct:
        mon_idx = 0 if monitor <= 0 else monitor
        if mon_idx >= len(sct.monitors):
            mon_idx = 1 if len(sct.monitors) > 1 else 0
        img = sct.grab(sct.monitors[mon_idx])
        w, h = img.width, img.height
        scale = f"scale={max_width}:-2" if w > max_width else "copy"
        cmd = [
            ffmpeg_path,
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgra",
            "-s",
            f"{w}x{h}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            "-vf",
            scale,
            "-c:v",
            "libx264",
            "-crf",
            str(quality_crf),
            "-movflags",
            "+faststart",
            "-pix_fmt",
            "yuv420p",
            output_path,
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        frames_captured = 0
        start = time_mod.time()
        try:
            for _ in range(max_frames):
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
        logger.warning(f"[screen] recording exceeded size limit {size_limit_bytes // (1024 * 1024)} MB")
    return {
        "frames_captured": frames_captured,
        "duration_actual_sec": round(duration_actual, 1),
        "error": None,
    }
