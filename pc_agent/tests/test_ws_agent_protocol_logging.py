from __future__ import annotations

from pathlib import Path

def test_handshake_protocol_log_uses_current_protocol_version():
    source = (Path(__file__).resolve().parents[1] / "ws_agent.py").read_text(encoding="utf-8")

    assert "Protocol: {PROTOCOL_VERSION}" in source
    assert "Protocol: ws_mcp_v1" not in source
