from __future__ import annotations

import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import scripts.manage_remote_stack as manage_remote_stack

SERVER_DIR = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import runtime_control  # noqa: E402


def test_manage_remote_stack_forwards_smoke_base_url_and_tls_flag() -> None:
    command = manage_remote_stack.build_remote_command(
        Namespace(
            action="smoke",
            target="server",
            lines=80,
            follow=False,
            levels="",
            contains="",
            json=False,
            base_url="https://192.168.100.19:9443",
            insecure_tls=True,
        )
    )

    assert "curl --fail --silent --show-error --insecure https://192.168.100.19:9443/api/health" == command


def test_manage_remote_stack_uses_env_profile_paths(monkeypatch) -> None:
    monkeypatch.setenv("HELPDESK_REMOTE_ROOT", "/srv/helpdesk/current")
    monkeypatch.setenv("HELPDESK_REMOTE_SERVER_PYTHON", "/srv/helpdesk/current/server/venv/bin/python")

    command = manage_remote_stack.build_remote_command(
        Namespace(
            action="status",
            target="server",
            lines=80,
            follow=False,
            levels="",
            contains="",
            json=False,
            base_url="",
            insecure_tls=False,
        )
    )

    assert command == "sudo systemctl status helpdesk-server.service --no-pager"


def test_remote_management_script_bootstraps_workspace_for_direct_execution() -> None:
    source = (Path(manage_remote_stack.__file__).resolve()).read_text(encoding="utf-8")

    assert "sys.path.insert(0, str(WORKSPACE))" in source


def test_runtime_smoke_uses_env_https_url_and_insecure_tls(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_run_shell(command: str, *, check: bool = True, capture_output: bool = True):
        captured["command"] = command
        return subprocess.CompletedProcess(args=["bash"], returncode=0, stdout="ok", stderr="")

    monkeypatch.setenv("REMOTE_SMOKE_BASE_URL", "https://192.168.100.19:9443")
    monkeypatch.setenv("REMOTE_SMOKE_INSECURE_TLS", "true")
    monkeypatch.setattr(runtime_control, "_run_shell", fake_run_shell)

    runtime_control.smoke_server()

    assert "BASE_URL=https://192.168.100.19:9443" in captured["command"]
    assert "REMOTE_SMOKE_INSECURE_TLS=true" in captured["command"]
    assert "SMOKE_INSECURE_TLS=true" in captured["command"]


def test_runtime_smoke_explicit_args_override_env(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_run_shell(command: str, *, check: bool = True, capture_output: bool = True):
        captured["command"] = command
        return subprocess.CompletedProcess(args=["bash"], returncode=0, stdout="ok", stderr="")

    monkeypatch.setenv("REMOTE_SMOKE_BASE_URL", "http://legacy:8666")
    monkeypatch.setenv("REMOTE_SMOKE_INSECURE_TLS", "false")
    monkeypatch.setattr(runtime_control, "_run_shell", fake_run_shell)

    runtime_control.smoke_server(base_url="https://stand.example:9443", insecure_tls=True)

    assert "BASE_URL=https://stand.example:9443" in captured["command"]
    assert "legacy:8666" not in captured["command"]
    assert "SMOKE_INSECURE_TLS=true" in captured["command"]
