from __future__ import annotations

import subprocess
import sys

import scripts.run_remote_migrations as migrations


def test_run_remote_migrations_uses_env_profile(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setenv("HELPDESK_REMOTE", "deploy@example.internal")
    monkeypatch.setenv("HELPDESK_REMOTE_ROOT", "/srv/helpdesk/current")
    monkeypatch.setenv("HELPDESK_REMOTE_SERVER_PYTHON", "/srv/helpdesk/current/server/venv/bin/python")
    monkeypatch.setattr(migrations.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["run_remote_migrations.py", "current"])

    assert migrations.main() == 0

    assert captured["command"][-2] == "deploy@example.internal"
    assert captured["command"][-1] == (
        "cd /srv/helpdesk/current/server && /srv/helpdesk/current/server/venv/bin/python "
        "scripts/run_migrations.py current"
    )
