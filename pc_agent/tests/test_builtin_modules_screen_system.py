import sys
import io
from types import SimpleNamespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.modules.pop("modules", None)

from pc_agent.modules.impl import screen as screen_module
from pc_agent.modules.impl import system as system_module
from pc_agent.modules.impl.screen import ScreenCollector
from pc_agent.modules.impl.system import SystemCollector


class _FakeGrab:
    def __init__(self, width: int, height: int):
        self.rgb = b"\x00" * (width * height * 3)
        self.size = (width, height)


class _FakeMss:
    def __init__(self):
        self.monitors = [
            {"left": 0, "top": 0, "width": 3200, "height": 1080},
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
            {"left": 1920, "top": 0, "width": 1280, "height": 1024},
        ]

    def grab(self, region):
        return _FakeGrab(region["width"], region["height"])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeShot:
    def __init__(self, width: int = 64, height: int = 48):
        self.width = width
        self.height = height
        self.raw = b"\x00" * (width * height * 4)
        self.rgb = b"\x00" * (width * height * 3)
        self.size = (width, height)


class _FakeRecordingMss(_FakeMss):
    def grab(self, region):
        return _FakeShot(region["width"], region["height"])


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_screen_collect_supports_region_capture(monkeypatch, tmp_path):
    monkeypatch.setattr(screen_module.mss, "mss", lambda: _FakeMss())
    monkeypatch.setattr(screen_module, "get_config", lambda: SimpleNamespace(paths=SimpleNamespace(data_dir=str(tmp_path))))

    def _write(image, output_path):
        output_path.write_bytes(b"png")

    monkeypatch.setattr(ScreenCollector, "_write_screenshot", staticmethod(_write))

    collector = ScreenCollector()
    collector.temp_dir = tmp_path

    result = await collector.collect(monitor=2, left=10, top=20, width=300, height=200)

    assert result["capture_mode"] == "region"
    assert result["resolution"] == "300x200"
    assert result["region"] == {"left": 1930, "top": 20, "width": 300, "height": 200}
    assert result["_artifacts"][0]["mime"] == "image/png"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_system_collect_uses_presets_and_overrides(monkeypatch):
    collector = SystemCollector()

    monkeypatch.setattr(system_module.psutil, "cpu_percent", lambda interval=1: 12.5)
    monkeypatch.setattr(system_module.psutil, "cpu_count", lambda logical=True: 8 if logical else 4)
    monkeypatch.setattr(
        system_module.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(percent=45.0, total=1000, available=550, used=450),
    )
    monkeypatch.setattr(
        system_module.psutil,
        "disk_usage",
        lambda path: SimpleNamespace(percent=77.0, total=2000, used=1540, free=460),
    )
    monkeypatch.setattr(system_module.psutil, "net_if_addrs", lambda: {})
    monkeypatch.setattr(
        system_module.psutil,
        "net_io_counters",
        lambda: SimpleNamespace(bytes_sent=100, bytes_recv=200),
    )
    monkeypatch.setattr(system_module.psutil, "boot_time", lambda: 1234567890.0)
    monkeypatch.setattr(system_module.socket, "gethostname", lambda: "agent-host")
    monkeypatch.setattr(SystemCollector, "_guess_primary_ip", staticmethod(lambda hostname: "10.0.0.5"))

    result = await collector.collect(preset="identity", include_boot_time=True, include_cpu=True)

    assert result["preset"] == "identity"
    assert "cpu" in result["selected_sections"]
    assert "network" in result["selected_sections"]
    assert "platform" in result["selected_sections"]
    assert "boot_time" in result["selected_sections"]
    assert result["hostname"] == "agent-host"
    assert result["ip"] == "10.0.0.5"
    assert result["sections"]["cpu"]["percent"] == 12.5
    assert result["sections"]["boot_time"]["epoch"] == 1234567890.0


@pytest.mark.no_db
def test_screen_record_falls_back_to_frame_sequence_when_raw_pipe_crashes(monkeypatch, tmp_path):
    class _FailingStdin:
        def write(self, data):
            raise OSError(22, "Invalid argument")

        def close(self):
            pass

    class _FailingPopen:
        def __init__(self, *args, **kwargs):
            self.stdin = _FailingStdin()
            self.stderr = io.BytesIO(b"raw pipe crashed")
            self.returncode = 3221225794

        def wait(self, timeout=None):
            return self.returncode

    run_calls = []

    def _fake_run(cmd, stdout=None, stderr=None, timeout=None):
        run_calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"mp4")
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(screen_module.mss, "mss", lambda: _FakeRecordingMss())
    monkeypatch.setattr(screen_module.mss.tools, "to_png", lambda rgb, size, output: Path(output).write_bytes(b"png"))
    monkeypatch.setattr(screen_module.subprocess, "Popen", _FailingPopen)
    monkeypatch.setattr(screen_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(screen_module.time, "sleep", lambda seconds: None)

    output_path = tmp_path / "recording.mp4"
    result = screen_module._record_sync(
        "ffmpeg",
        monitor=1,
        fps=5,
        duration_sec=1,
        max_width=640,
        quality_crf=28,
        size_limit_bytes=screen_module.SIZE_LIMIT_BYTES,
        output_path=str(output_path),
        stop_event=None,
    )

    assert result["error"] is None
    assert result["frames_captured"] == 5
    assert result["encoder_mode"] == "image_sequence_fallback"
    assert result["raw_error"]
    assert output_path.read_bytes() == b"mp4"
    assert run_calls
    assert "-framerate" in run_calls[0]
    assert not any(path.name.endswith("_frames") for path in tmp_path.iterdir())


@pytest.mark.no_db
def test_screen_record_reports_ffmpeg_stderr_when_raw_and_fallback_fail(monkeypatch, tmp_path):
    class _FailingStdin:
        def write(self, data):
            raise OSError(22, "Invalid argument")

        def close(self):
            pass

    class _FailingPopen:
        def __init__(self, *args, **kwargs):
            self.stdin = _FailingStdin()
            self.stderr = io.BytesIO(b"raw pipe crashed")
            self.returncode = 3221225794

        def wait(self, timeout=None):
            return self.returncode

    def _fake_run(cmd, stdout=None, stderr=None, timeout=None):
        return SimpleNamespace(returncode=1, stderr=b"fallback encoder failed")

    monkeypatch.setattr(screen_module.mss, "mss", lambda: _FakeRecordingMss())
    monkeypatch.setattr(screen_module.mss.tools, "to_png", lambda rgb, size, output: Path(output).write_bytes(b"png"))
    monkeypatch.setattr(screen_module.subprocess, "Popen", _FailingPopen)
    monkeypatch.setattr(screen_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(screen_module.time, "sleep", lambda seconds: None)

    result = screen_module._record_sync(
        "ffmpeg",
        monitor=1,
        fps=5,
        duration_sec=1,
        max_width=640,
        quality_crf=28,
        size_limit_bytes=screen_module.SIZE_LIMIT_BYTES,
        output_path=str(tmp_path / "recording.mp4"),
        stop_event=None,
    )

    assert result["error"]
    assert "raw ffmpeg failed" in result["error"]
    assert "raw pipe crashed" in result["error"]
    assert "fallback encoder failed" in result["error"]
