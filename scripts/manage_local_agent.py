#!/usr/bin/env python3
"""Manage isolated local Windows agent instances for pc_client."""

from __future__ import annotations

import asyncio
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))
VENV_DIR = WORKSPACE / ".venvs" / "agent-win"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
REQUIREMENTS = WORKSPACE / "pc_agent" / "requirements.txt"
INSTANCE_ROOT = WORKSPACE / ".local-agent" / "instances"
DEFAULT_WS_URL = "wss://example.test:9443/ws"
DEFAULT_API_URL = "https://example.test:9443/api"
DEFAULT_UI_PORT = 8765
DEFAULT_RELEASE_BUILD_ROOT = WORKSPACE / "pc_agent" / "dist"
LOCAL_AGENT_MACHINE_ID_NAMESPACE = uuid.UUID("9242c452-fc83-4792-9f9f-ea07a5b13251")


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


def _read_agent_version() -> str:
    version_py = (WORKSPACE / "pc_agent" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'AGENT_VERSION\s*=\s*"([^"]+)"', version_py)
    if not match:
        raise SystemExit("Could not parse AGENT_VERSION from pc_agent/version.py")
    return match.group(1)


def _read_install_current_version(install_root: Path) -> str | None:
    current_path = install_root / "current.json"
    if not current_path.exists():
        return None
    try:
        payload = json.loads(current_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    version = str(payload.get("version") or "").strip()
    return version or None


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
    return _get_process_snapshot(pid) is not None


def _normalize_process_text(value: str | None) -> str:
    return str(value or "").strip().strip('"').replace("/", "\\").lower()


def _path_hint_matches_command_line(command_line: str | None, path_hint: str | Path | None) -> bool:
    normalized_hint = _normalize_process_text(str(path_hint or ""))
    if not normalized_hint:
        return True
    normalized_command = _normalize_process_text(command_line)
    return normalized_hint in normalized_command


def _get_process_snapshot(pid: int) -> dict[str, object] | None:
    if pid <= 0:
        return None
    ps_command = (
        f"$p = Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\"; "
        "if ($null -eq $p) { exit 1 }; "
        "$p | Select-Object ProcessId, Name, ExecutablePath, CommandLine | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None
    raw = str(result.stdout or "").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return {
        "pid": int(payload.get("ProcessId") or pid),
        "name": str(payload.get("Name") or ""),
        "executable_path": str(payload.get("ExecutablePath") or ""),
        "command_line": str(payload.get("CommandLine") or ""),
    }


def _pid_matches_instance(payload: dict | None) -> bool:
    if not payload:
        return False
    pid = int(payload.get("pid") or 0)
    snapshot = _get_process_snapshot(pid)
    if not snapshot:
        return False

    command_line = str(snapshot.get("command_line") or "")
    executable_path = _normalize_process_text(str(snapshot.get("executable_path") or ""))
    process_name = _normalize_process_text(str(snapshot.get("name") or ""))
    start_mode = str(payload.get("start_mode") or "source").strip().lower()

    if start_mode == "launcher":
        expected_launcher = Path(payload.get("install_root") or "") / "launcher.exe"
        normalized_expected_launcher = _normalize_process_text(str(expected_launcher))
        if executable_path and normalized_expected_launcher and executable_path != normalized_expected_launcher:
            return False
        if not executable_path and process_name != "launcher.exe":
            return False
        return _path_hint_matches_command_line(command_line, payload.get("data_dir"))

    expected_python = _normalize_process_text(str(payload.get("venv_python") or ""))
    if expected_python and executable_path and executable_path != expected_python:
        return False
    if not executable_path and process_name not in {"python.exe", "pythonw.exe"}:
        return False
    if "pc_agent.ws_agent" not in command_line.lower():
        return False
    return (
        _path_hint_matches_command_line(command_line, payload.get("data_dir"))
        and _path_hint_matches_command_line(command_line, payload.get("install_root"))
    )


def _normalize_machine_id(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return str(uuid.UUID(raw)).lower()
    except ValueError:
        return str(uuid.uuid5(LOCAL_AGENT_MACHINE_ID_NAMESPACE, raw))


def _resolve_start_machine_id(name: str, machine_id: str | None, current: dict | None) -> str | None:
    resolved_machine_id = _normalize_machine_id(machine_id)
    if resolved_machine_id:
        return resolved_machine_id
    if current:
        current_machine_id = _normalize_machine_id(str(current.get("machine_id") or ""))
        if current_machine_id:
            return current_machine_id
    return None


def _build_env(
    ws_url: str,
    api_url: str,
    auth_token: str | None,
    ui_port: int | None = None,
    machine_id: str | None = None,
    data_dir: str | Path | None = None,
    install_root: str | Path | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    env["PC_AGENT_WS_URL"] = ws_url
    env["PC_AGENT_API_URL"] = api_url
    if auth_token:
        env["AUTH_TOKEN"] = auth_token
    if ui_port is not None:
        env["PC_AGENT_UI_PORT"] = str(ui_port)
    if machine_id:
        env["PC_AGENT_MACHINE_ID"] = machine_id
    if data_dir:
        env["PC_AGENT_DATA_DIR"] = str(Path(data_dir).resolve())
    if install_root:
        env["PC_AGENT_INSTALL_ROOT"] = str(Path(install_root).resolve())
    return env


def _request_json(method: str, url: str, payload: dict[str, object] | None = None) -> tuple[int, dict[str, object]]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, json.loads(raw) if raw else {"error": f"HTTP {exc.code}"}
    except urllib.error.URLError as exc:
        raise SystemExit(f"Request failed for {url}: {exc}") from exc


def _issue_agent_token(api_url: str, device_id: str) -> str:
    parsed = urllib.parse.urlsplit(str(api_url or "").strip())
    normalized_path = parsed.path.rstrip("/")
    if normalized_path.endswith("/login"):
        normalized_path = normalized_path[: -len("/login")]
    if not normalized_path.endswith("/api"):
        normalized_path = f"{normalized_path}/api" if normalized_path else "/api"
    login_url = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, f"{normalized_path}/login", "", ""),
    )
    status, payload = _request_json(
        "POST",
        login_url,
        {"uuid": device_id},
    )
    if status != 200 or str(payload.get("status") or "").lower() not in {"success", "ok"}:
        raise SystemExit(
            f"Failed to issue local agent token for device_id={device_id}: "
            f"HTTP {status} {json.dumps(payload, ensure_ascii=False)}"
        )
    token = str(payload.get("token") or "").strip()
    if not token:
        raise SystemExit(f"Server response did not contain agent token for device_id={device_id}")
    print(f"[manage_local_agent] issued isolated token for device_id={device_id}")
    return token


def _choose_ui_port(preferred: int = DEFAULT_UI_PORT) -> int:
    port = preferred
    while port < preferred + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                port += 1
                continue
            return port
    raise SystemExit("No free local UI port available in the expected range")


def _default_primary_agent_data_dir() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        return (Path(local_appdata) / "PCClientAgent" / "data").resolve()
    return (Path.home() / "AppData" / "Local" / "PCClientAgent" / "data").resolve()


def _sync_instance_token_from_primary_install(instance_name: str, instance_data_dir: Path) -> bool:
    """
    Makes local testing easier: if an isolated instance on the same machine does
    not have its own token yet, reuse the active token from the main local
    agent installation.

    This is intentionally scoped to scripts/manage_local_agent.py so the
    production runtime contract stays token-based and per-data-root.
    """
    primary_data_dir = _default_primary_agent_data_dir()
    instance_data_dir = instance_data_dir.resolve()
    if primary_data_dir == instance_data_dir:
        return False

    try:
        from pc_agent.auth.token_source import import_missing_auth_token_from_data_roots

        return import_missing_auth_token_from_data_roots(
            primary_data_dir,
            instance_data_dir,
            log_message=lambda message: print(f"[manage_local_agent] {message}"),
        )
    except Exception as exc:
        print(
            f"[manage_local_agent] warning: failed to import token from primary install "
            f"for '{instance_name}': {exc}"
        )
        return False


def _seed_release_install(name: str, build_root: Path) -> str:
    layout = _ensure_instance_layout(name)
    install_root = layout["install_root"]
    launcher_src = build_root / "launcher.exe"
    agent_dir = build_root / "pc_agent"
    current_path = install_root / "current.json"
    launcher_dst = install_root / "launcher.exe"
    existing_version = _read_install_current_version(install_root)

    if current_path.exists() and launcher_dst.exists() and existing_version:
        existing_version_dir = install_root / "versions" / existing_version
        if existing_version_dir.exists():
            return existing_version

    if not launcher_src.exists():
        raise SystemExit(
            f"Launcher build not found: {launcher_src}. "
            "Build it first with pc_agent/build_windows_release.py or build_windows_release_v2.py"
        )
    if not (agent_dir / "pc_agent.exe").exists():
        raise SystemExit(
            f"Agent build not found: {agent_dir / 'pc_agent.exe'}. "
            "Build it first with pc_agent/build_windows_release.py or build_windows_release_v2.py"
        )

    version = _read_agent_version()
    version_dir = install_root / "versions" / version

    install_root.mkdir(parents=True, exist_ok=True)
    (install_root / "versions").mkdir(parents=True, exist_ok=True)
    if version_dir.exists():
        shutil.rmtree(version_dir, ignore_errors=True)
    version_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(launcher_src, launcher_dst)
    for item in agent_dir.iterdir():
        dst = version_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst)
    current_path.write_text(
        json.dumps({"version": version, "previous": version}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return version


def _verify(
    name: str,
    ws_url: str,
    api_url: str,
    auth_token: str | None,
    ui_port: int | None = None,
    machine_id: str | None = None,
) -> int:
    if not _venv_exists():
        raise SystemExit("Local agent venv is missing. Run: python scripts/manage_local_agent.py bootstrap")
    layout = _ensure_instance_layout(name)
    env = _build_env(
        ws_url,
        api_url,
        auth_token,
        ui_port,
        _normalize_machine_id(machine_id),
        layout["data_dir"],
        layout["install_root"],
    )
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
    use_launcher: bool = False,
    build_root: Path = DEFAULT_RELEASE_BUILD_ROOT,
    machine_id: str | None = None,
    issue_token: bool = False,
) -> int:
    if not _venv_exists():
        raise SystemExit("Local agent venv is missing. Run: python scripts/manage_local_agent.py bootstrap")
    current = _load_instance(name)
    if current and _pid_matches_instance(current):
        raise SystemExit(f"Instance '{name}' is already running with PID {current['pid']}")

    layout = _ensure_instance_layout(name)
    resolved_machine_id = _resolve_start_machine_id(name, machine_id, current)
    resolved_auth_token = auth_token
    if issue_token and not resolved_auth_token:
        if not resolved_machine_id:
            resolved_machine_id = _normalize_machine_id(f"local-agent:{name}")
        resolved_auth_token = _issue_agent_token(api_url, resolved_machine_id)
    if not resolved_auth_token and not resolved_machine_id:
        _sync_instance_token_from_primary_install(name, layout["data_dir"])
    resolved_ui_port = ui_port if ui_port is not None else _choose_ui_port()
    env = _build_env(
        ws_url,
        api_url,
        resolved_auth_token,
        ui_port,
        resolved_machine_id,
        layout["data_dir"],
        layout["install_root"],
    )
    env["PC_AGENT_UI_PORT"] = str(resolved_ui_port)
    if not gui and not resolved_auth_token:
        print("[manage_local_agent] warning: headless start without --auth-token usually exits after token prompt")
    start_mode = "launcher" if use_launcher else "source"
    seeded_version = None
    if use_launcher:
        seeded_version = _seed_release_install(name, build_root)
        cmd = [
            str(layout["install_root"] / "launcher.exe"),
            "--data-dir",
            str(layout["data_dir"]),
            "--install-root",
            str(layout["install_root"]),
        ]
    else:
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
        print(f"[manage_local_agent] start foreground instance '{name}' mode={start_mode}")
        return _run(cmd, env=env).returncode

    layout["launcher_log"].parent.mkdir(parents=True, exist_ok=True)
    with layout["launcher_log"].open("a", encoding="utf-8") as stream:
        stream.write(f"\n[{_utc_now()}] start {name}\n")
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            # С GUI не использовать CREATE_NO_WINDOW, иначе окно может не появиться
            if not gui:
                creationflags |= subprocess.CREATE_NO_WINDOW
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
        "ui_port": resolved_ui_port,
        "machine_id": resolved_machine_id,
        "start_mode": start_mode,
        "seeded_version": seeded_version,
        "build_root": str(build_root) if use_launcher else None,
        "workspace": str(WORKSPACE),
        "venv_python": str(VENV_PYTHON),
        "data_dir": str(layout["data_dir"]),
        "install_root": str(layout["install_root"]),
        "launcher_log": str(layout["launcher_log"]),
    }
    _save_instance(name, payload)
    print(
        f"[manage_local_agent] started '{name}' pid={proc.pid} "
        f"mode={start_mode} ui_port={resolved_ui_port}"
    )
    return 0


def _stop(name: str) -> int:
    payload = _load_instance(name)
    if not payload:
        print(f"[manage_local_agent] instance '{name}' is not registered")
        return 0
    pid = int(payload.get("pid") or 0)
    if not pid or not _pid_matches_instance(payload):
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
        running = _pid_matches_instance(payload) if pid else False
        state = "running" if running else "stopped"
        ui_mode = "gui" if payload.get("gui") else "headless"
        start_mode = payload.get("start_mode") or "source"
        print(f"{item}: {state}, pid={pid}, mode={ui_mode}/{start_mode}, ws={payload.get('ws_url')}")
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
    verify.add_argument(
        "--machine-id",
        default=None,
        help="Override PC_AGENT_MACHINE_ID for this instance; accepts UUID or arbitrary stable seed",
    )

    start = subparsers.add_parser("start", help="Start a named local agent instance")
    start.add_argument("name")
    start.add_argument("--gui", action="store_true", help="Start with GUI")
    start.add_argument("--foreground", action="store_true", help="Run in foreground")
    start.add_argument("--ws-url", default=DEFAULT_WS_URL)
    start.add_argument("--api-url", default=DEFAULT_API_URL)
    start.add_argument("--auth-token", default=None)
    start.add_argument(
        "--machine-id",
        default=None,
        help="Override PC_AGENT_MACHINE_ID for this instance; accepts UUID or arbitrary stable seed",
    )
    start.add_argument(
        "--issue-token",
        action="store_true",
        help="Request a fresh agent token for the resolved machine_id via /api/login before startup",
    )
    start.add_argument("--ui-port", type=int, default=None, metavar="PORT", help="UI API port (default 8765; use if port is busy)")
    start.add_argument("--launcher", action="store_true", help="Run the built Windows launcher.exe instead of source ws_agent")
    start.add_argument("--build-root", default=str(DEFAULT_RELEASE_BUILD_ROOT), help="Path to built launcher.exe and pc_agent/ directory")

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
        return _verify(
            args.name,
            args.ws_url,
            args.api_url,
            args.auth_token,
            getattr(args, "ui_port", None),
            getattr(args, "machine_id", None),
        )
    if args.command == "start":
        return _start(
            args.name,
            args.gui,
            args.ws_url,
            args.api_url,
            args.auth_token,
            args.foreground,
            getattr(args, "ui_port", None),
            getattr(args, "launcher", False),
            Path(args.build_root),
            getattr(args, "machine_id", None),
            getattr(args, "issue_token", False),
        )
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
