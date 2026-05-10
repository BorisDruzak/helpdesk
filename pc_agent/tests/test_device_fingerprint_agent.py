import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent.core import device_fingerprint


def test_windows_fingerprint_avoids_wmi_baseboard_by_default(monkeypatch):
    calls = []

    monkeypatch.delenv("PC_AGENT_ENABLE_WMI_FINGERPRINT", raising=False)
    monkeypatch.setattr(device_fingerprint.platform, "system", lambda: "Windows")
    monkeypatch.setattr(device_fingerprint, "_windows_machine_guid", lambda: "machine-guid")
    monkeypatch.setattr(device_fingerprint, "_windows_boot_volume", lambda: "boot-volume")
    monkeypatch.setattr(device_fingerprint, "_mac_hashes", lambda: ["mac-hash"])

    def fail_if_wmi_baseboard_is_used():
        calls.append("baseboard")
        raise AssertionError("WMI baseboard lookup should be disabled by default")

    monkeypatch.setattr(device_fingerprint, "_windows_baseboard", fail_if_wmi_baseboard_is_used)

    result = device_fingerprint.collect_device_fingerprint()

    assert calls == []
    assert "system_uuid" in result["components"]
    assert "boot_volume" in result["components"]
    assert result["mac_hashes"] == ["mac-hash"]
