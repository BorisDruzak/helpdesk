import sys
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
