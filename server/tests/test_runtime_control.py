from __future__ import annotations

from datetime import datetime, timezone

import pytest

from runtime_control import _parse_systemd_timestamp, get_unit_status, start_target, stop_target

pytestmark = pytest.mark.no_db


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

    monkeypatch.setattr("runtime_control._stop_workspace_server_processes", lambda: calls.append(("cleanup", "server")))
    monkeypatch.setattr("runtime_control._stop_unit", lambda unit: calls.append(("stop", unit)))
    monkeypatch.setattr("runtime_control._reset_failed", lambda unit: calls.append(("reset", unit)))

    result = stop_target("server")

    assert result.returncode == 0
    assert calls == [("cleanup", "server"), ("stop", "pc-client-server"), ("reset", "pc-client-server")]


def test_start_target_cleans_workspace_server_before_systemd_run(monkeypatch):
    calls = []

    monkeypatch.setattr("runtime_control._stop_workspace_server_processes", lambda: calls.append(("cleanup", "server")))
    monkeypatch.setattr("runtime_control._reset_failed", lambda unit: calls.append(("reset", unit)))
    monkeypatch.setattr("runtime_control._stop_unit", lambda unit: calls.append(("stop", unit)))
    monkeypatch.setattr(
        "runtime_control._run",
        lambda args, cwd=None, check=True, capture_output=True: calls.append(("run", args)) or type(
            "CompletedProcess",
            (),
            {"stdout": "", "stderr": "", "returncode": 0},
        )(),
    )

    start_target("server")

    assert calls[0:3] == [
        ("cleanup", "server"),
        ("reset", "pc-client-server"),
        ("stop", "pc-client-server"),
    ]
    run_args = calls[3][1]
    assert "--property=Restart=on-failure" in run_args
    assert "--property=RestartSec=2s" in run_args
    assert "--property=StartLimitBurst=3" in run_args
    assert "--property=StartLimitIntervalSec=60s" in run_args


def test_get_unit_status_marks_external_listener(monkeypatch):
    monkeypatch.setattr(
        "runtime_control._systemctl_show",
        lambda unit, properties: {
            "ActiveState": "failed",
            "SubState": "failed",
            "ExecMainPID": "3612833",
            "MainPID": "3612833",
            "UnitFileState": "transient",
            "FragmentPath": "/run/user/1000/systemd/transient/pc-client-server.service",
        },
    )
    monkeypatch.setattr("runtime_control._status_excerpt", lambda unit, lines=12: "failed")
    monkeypatch.setattr(
        "runtime_control._get_server_port_listener",
        lambda: {
            "pid": 3872577,
            "ppid": 3872572,
            "cmd": "/var/chat_bot/pc_client/server/venv/bin/python server.py",
            "cwd": "/var/chat_bot/pc_client/server",
            "port": 8666,
        },
    )

    status = get_unit_status("server")

    assert status["external_listener_detected"] is True
    assert status["port_listener"]["pid"] == 3872577
