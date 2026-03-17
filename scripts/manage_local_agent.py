#!/usr/bin/env python3
"""Manage isolated local Windows agent instances for pc_client."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parent.parent
VENV_DIR = WORKSPACE / ".venvs" / "agent-win"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
REQUIREMENTS = WORKSPACE / "pc_agent" / "requirements.txt"
INSTANCE_ROOT = WORKSPACE / ".local-agent" / "instances"
DEFAULT_WS_URL = "ws://192.168.100.17:8666/ws"
DEFAULT_API_URL = "http://192.168.100.17:8666/api"


def _configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _instance_dir(name: str) -> Path:
    return INSTANCE_ROOT / name


def _instance_file(name: str) -> Path:
    return _instance_dir(name) / "instance.json"


def _ensure_instance_layout(name: str) -> dict[str, Path]:
    base = _instance_dir(name)
    data_dir = base / "data"
    install_root = base / "install"
    base.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    install_root.mkdir(parents=True, exist_ok=True)
    return {
        "base": base,
        "data_dir": data_dir,
        "install_root": install_root,
        "instance_file": _instance_file(name),
        "launcher_log": base / "launcher.log",
    }


def _load_instance(name: str) -> dict | None:
    path = _instance_file(name)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_instance(name: str, payload: dict) -> None:
    path = _instance_file(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run(cmd: list[str], *, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=WORKSPACE, env=env, check=check)


def _venv_exists() -> bool:
    return VENV_PYTHON.exists()


def _bootstrap(python_exe: str, reinstall: bool) -> int:
    if reinstall and VENV_DIR.exists():
        shutil.rmtree(VENV_DIR)
    if not _venv_exists():
        print(f"[manage_local_agent] create venv: {VENV_DIR}")
        _run([python_exe, "-m", "venv", str(VENV_DIR)])
    print("[manage_local_agent] upgrade pip")
    _run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
    print("[manage_local_agent] install agent requirements")
    _run([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    print("[manage_local_agent] verify core imports")
    _run(
        [
            str(VENV_PYTHON),
            "-c",
            "import aiohttp, aiosqlite, loguru, pydantic, yaml; import PySide6, qasync; print('agent-win ok')",
        ]
    )
    print("[manage_local_agent] bootstrap complete")
    return 0


def _pid_is_running(pid: int) -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return str(pid) in result.stdout


def _build_env(ws_url: str, api_url: str, auth_token: str | None, ui_port: int | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PC_AGENT_WS_URL"] = ws_url
    env["PC_AGENT_API_URL"] = api_url
    if auth_token:
        env["AUTH_TOKEN"] = auth_token
    if ui_port is not None:
        env["PC_AGENT_UI_PORT"] = str(ui_port)
    return env


def _verify(name: str, ws_url: str, api_url: str, auth_token: str | None, ui_port: int | None = None) -> int:
    if not _venv_exists():
        raise SystemExit("Local agent venv is missing. Run: python scripts/manage_local_agent.py bootstrap")
    layout = _ensure_instance_layout(name)
    env = _build_env(ws_url, api_url, auth_token, ui_port)
    cmd = [
        str(VENV_PYTHON),
        "-m",
        "pc_agent.ws_agent",
        "--data-dir",
        str(layout["data_dir"]),
        "--install-root",
        str(layout["install_root"]),
        "--verify",
    ]
    print(f"[manage_local_agent] verify instance '{name}'")
    return _run(cmd, env=env).returncode


def _start(
    name: str,
    gui: bool,
    ws_url: str,
    api_url: str,
    auth_token: str | None,
    foreground: bool,
    ui_port: int | None = None,
) -> int:
    if not _venv_exists():
        raise SystemExit("Local agent venv is missing. Run: python scripts/manage_local_agent.py bootstrap")
    current = _load_instance(name)
    if current and current.get("pid") and _pid_is_running(int(current["pid"])):
        raise SystemExit(f"Instance '{name}' is already running with PID {current['pid']}")

    layout = _ensure_instance_layout(name)
    env = _build_env(ws_url, api_url, auth_token, ui_port)
    if not gui and not auth_token:
        print("[manage_local_agent] warning: headless start without --auth-token usually exits after token prompt")
    cmd = [
        str(VENV_PYTHON),
        "-m",
        "pc_agent.ws_agent",
        "--data-dir",
        str(layout["data_dir"]),
        "--install-root",
        str(layout["install_root"]),
    ]
    if gui:
        cmd.append("--gui")

    if foreground:
        print(f"[manage_local_agent] start foreground instance '{name}'")
        return _run(cmd, env=env).returncode

    layout["launcher_log"].parent.mkdir(parents=True, exist_ok=True)
    with layout["launcher_log"].open("a", encoding="utf-8") as stream:
        stream.write(f"\n[{_utc_now()}] start {name}\n")
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen(
            cmd,
            cwd=WORKSPACE,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            creationflags=creationflags,
        )
    payload = {
        "name": name,
        "pid": proc.pid,
        "started_at": _utc_now(),
        "gui": gui,
        "ws_url": ws_url,
        "api_url": api_url,
        "workspace": str(WORKSPACE),
        "venv_python": str(VENV_PYTHON),
        "data_dir": str(layout["data_dir"]),
        "install_root": str(layout["install_root"]),
        "launcher_log": str(layout["launcher_log"]),
    }
    _save_instance(name, payload)
    print(f"[manage_local_agent] started '{name}' pid={proc.pid}")
    return 0


def _stop(name: str) -> int:
    payload = _load_instance(name)
    if not payload:
        print(f"[manage_local_agent] instance '{name}' is not registered")
        return 0
    pid = int(payload.get("pid") or 0)
    if not pid or not _pid_is_running(pid):
        print(f"[manage_local_agent] instance '{name}' is already stopped")
        return 0
    print(f"[manage_local_agent] stop '{name}' pid={pid}")
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
    payload["stopped_at"] = _utc_now()
    _save_instance(name, payload)
    return 0


def _tail_text(path: Path, lines: int) -> str:
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def _logs(name: str, lines: int) -> int:
    payload = _load_instance(name)
    if not payload:
        raise SystemExit(f"Unknown instance '{name}'")
    launcher_log = Path(payload["launcher_log"])
    agent_log = Path(payload["data_dir"]) / "logs" / "agent.log"
    if launcher_log.exists():
        print(f"== launcher: {launcher_log} ==")
        print(_tail_text(launcher_log, lines))
    if agent_log.exists():
        print(f"== agent: {agent_log} ==")
        print(_tail_text(agent_log, lines))
    if not launcher_log.exists() and not agent_log.exists():
        print("[manage_local_agent] no logs yet")
    return 0


def _status(name: str | None) -> int:
    if name:
        names = [name]
    else:
        names = sorted(p.name for p in INSTANCE_ROOT.iterdir() if p.is_dir()) if INSTANCE_ROOT.exists() else []
    if not names:
        print("[manage_local_agent] no local agent instances")
        return 0
    for item in names:
        payload = _load_instance(item)
        if not payload:
            continue
        pid = int(payload.get("pid") or 0)
        running = _pid_is_running(pid) if pid else False
        state = "running" if running else "stopped"
        mode = "gui" if payload.get("gui") else "headless"
        print(f"{item}: {state}, pid={pid}, mode={mode}, ws={payload.get('ws_url')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage isolated local agent instances on Windows")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap", help="Create/update local Windows venv for agent")
    bootstrap.add_argument("--python", default=sys.executable, help="Python executable for venv creation")
    bootstrap.add_argument("--reinstall", action="store_true", help="Recreate venv from scratch")

    verify = subparsers.add_parser("verify", help="Run agent init/DB verify for a named instance")
    verify.add_argument("name")
    verify.add_argument("--ws-url", default=DEFAULT_WS_URL)
    verify.add_argument("--api-url", default=DEFAULT_API_URL)
    verify.add_argument("--auth-token", default=None)

    start = subparsers.add_parser("start", help="Start a named local agent instance")
    start.add_argument("name")
    start.add_argument("--gui", action="store_true", help="Start with GUI")
    start.add_argument("--foreground", action="store_true", help="Run in foreground")
    start.add_argument("--ws-url", default=DEFAULT_WS_URL)
    start.add_argument("--api-url", default=DEFAULT_API_URL)
    start.add_argument("--auth-token", default=None)
    start.add_argument("--ui-port", type=int, default=None, metavar="PORT", help="UI API port (default 8765; use if port is busy)")

    stop = subparsers.add_parser("stop", help="Stop a named local agent instance")
    stop.add_argument("name")

    status = subparsers.add_parser("status", help="Show status for one or all local instances")
    status.add_argument("name", nargs="?")

    logs = subparsers.add_parser("logs", help="Show launcher and agent logs for an instance")
    logs.add_argument("name")
    logs.add_argument("--lines", type=int, default=80)

    return parser


def main() -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "bootstrap":
        return _bootstrap(args.python, args.reinstall)
    if args.command == "verify":
        return _verify(args.name, args.ws_url, args.api_url, args.auth_token, getattr(args, "ui_port", None))
    if args.command == "start":
        return _start(args.name, args.gui, args.ws_url, args.api_url, args.auth_token, args.foreground, getattr(args, "ui_port", None))
    if args.command == "stop":
        return _stop(args.name)
    if args.command == "status":
        return _status(args.name)
    if args.command == "logs":
        return _logs(args.name, args.lines)
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
