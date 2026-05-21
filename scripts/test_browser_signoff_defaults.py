from __future__ import annotations

from pathlib import Path


def test_remote_browser_signoff_defaults_to_https_profile_env() -> None:
    script = Path("webapp/scripts/remote-browser-signoff.mjs").read_text(encoding="utf-8")

    assert "process.env.PC_CLIENT_BROWSER_BASE_URL" in script
    assert "process.env.REMOTE_SMOKE_BASE_URL" in script
    assert 'const DEFAULT_BASE_URL = "http://192.168.100.17:8666";' not in script
    assert '"https://192.168.100.17:9443"' in script
