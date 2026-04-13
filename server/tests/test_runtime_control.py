from __future__ import annotations

from datetime import datetime, timezone

from runtime_control import _parse_systemd_timestamp, stop_target


def test_parse_systemd_timestamp_supports_usec_value():
    raw = "1744573200000000"
    expected = datetime.fromtimestamp(int(raw) / 1_000_000, tz=timezone.utc).isoformat()
    assert _parse_systemd_timestamp(raw) == expected


def test_parse_systemd_timestamp_supports_textual_systemctl_value():
    assert _parse_systemd_timestamp("Mon 2026-04-13 19:29:18 +05") == "2026-04-13T14:29:18+00:00"


def test_parse_systemd_timestamp_supports_textual_offset_with_colon():
    assert _parse_systemd_timestamp("2026-04-13 19:29:18 +05:00") == "2026-04-13T14:29:18+00:00"


def test_parse_systemd_timestamp_ignores_na():
    assert _parse_systemd_timestamp("n/a") is None


def test_stop_target_uses_systemctl_for_server(monkeypatch):
    calls = []

    monkeypatch.setattr("runtime_control._stop_unit", lambda unit: calls.append(("stop", unit)))
    monkeypatch.setattr("runtime_control._reset_failed", lambda unit: calls.append(("reset", unit)))

    result = stop_target("server")

    assert result.returncode == 0
    assert calls == [("stop", "pc-client-server"), ("reset", "pc-client-server")]
