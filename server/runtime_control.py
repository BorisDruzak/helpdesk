from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from config import SERVER_DATA_ROOT

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
SERVER_PYTHON = WORKSPACE_ROOT / "server" / "venv" / "bin" / "python"
AGENT_PYTHON = WORKSPACE_ROOT / "pc_agent" / "venv" / "bin" / "python"

SERVER_UNIT = "pc-client-server"
AGENT_UNIT = "pc-client-agent"
CONTROL_UNIT = "pc-client-control"
CONTROL_STATE_FILE = SERVER_DATA_ROOT / "control_plane_state.json"
DEFAULT_ADMIN_ORIGIN = "http://192.168.100.17:8666"

SYSTEMD_TARGETS = {"server", "agent", "control"}
ALL_TARGETS = (*SYSTEMD_TARGETS, "all")

_UNIT_BY_TARGET = {
    "server": SERVER_UNIT,
    "agent": AGENT_UNIT,
    "control": CONTROL_UNIT,
}

_DESCRIPTION_BY_TARGET = {
    "server": "pc_client server",
    "agent": "pc_client agent",
    "control": "pc_client control plane",
}


def unit_name(target: str) -> str:
    value = str(target or "").strip().lower()
    if value not in _UNIT_BY_TARGET:
        raise ValueError(f"Unsupported target: {target}")
    return _UNIT_BY_TARGET[value]


def runtime_command(target: str) -> str:
    value = str(target or "").strip().lower()
    if value == "server":
        return f"cd {WORKSPACE_ROOT} && {SERVER_PYTHON} scripts/run_server.py"
    if value == "agent":
        return f"cd {WORKSPACE_ROOT} && {AGENT_PYTHON} scripts/run_agent.py"
    if value == "control":
        return f"cd {WORKSPACE_ROOT} && {SERVER_PYTHON} scripts/run_control_plane.py"
    raise ValueError(f"Unsupported target: {target}")


def controller_allowed_origins() -> tuple[str, ...]:
    raw = os.getenv("PC_CLIENT_CONTROL_ALLOWED_ORIGINS", DEFAULT_ADMIN_ORIGIN)
    values = [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    return tuple(values) or (DEFAULT_ADMIN_ORIGIN,)


def load_control_state() -> dict[str, Any]:
    try:
        raw = CONTROL_STATE_FILE.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_control_state(data: dict[str, Any]) -> None:
    CONTROL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_path = CONTROL_STATE_FILE.with_suffix(".tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    temp_path.write_text(payload, encoding="utf-8")
    temp_path.replace(CONTROL_STATE_FILE)


def update_last_server_action(
    *,
    action: str,
    reason: str | None,
    actor_id: str | None,
    actor_role: str | None,
    status: str,
    error: str | None = None,
    requested_at: str | None = None,
    completed_at: str | None = None,
) -> dict[str, Any]:
    state = load_control_state()
    state["last_server_action"] = {
        "action": action,
        "reason": (reason or "").strip() or None,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "status": status,
        "error": error,
        "requested_at": requested_at,
        "completed_at": completed_at,
    }
    save_control_state(state)
    return state["last_server_action"]


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=check,
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _run_shell(command: str, *, check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(["/bin/bash", "-lc", command], cwd=WORKSPACE_ROOT, check=check, capture_output=capture_output)


def _systemctl_show(unit: str, properties: Iterable[str]) -> dict[str, str]:
    prop_arg = ",".join(str(item) for item in properties)
    completed = _run(
        ["systemctl", "--user", "show", unit, f"--property={prop_arg}"],
        cwd=WORKSPACE_ROOT,
        check=False,
    )
    result: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value
    return result


def _status_excerpt(unit: str, *, lines: int = 12) -> str:
    completed = _run(
        ["systemctl", "--user", "status", unit, "--no-pager", f"--lines={max(1, int(lines))}"],
        cwd=WORKSPACE_ROOT,
        check=False,
    )
    return completed.stdout.strip() or completed.stderr.strip()


def _parse_optional_int(raw: str | None) -> int | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        value = int(text)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _to_utc_iso(timestamp: datetime) -> str:
    value = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_systemd_timestamp(raw: str | None) -> str | None:
    text = str(raw or "").strip()
    if not text or text.lower() in {"n/a", "0"}:
        return None
    parsed_usec = _parse_optional_int(text)
    if parsed_usec:
        return datetime.fromtimestamp(parsed_usec / 1_000_000, tz=timezone.utc).isoformat()
    offset_match = re.match(
        r"^(?P<head>(?:[A-Za-z]{3}\s+)?\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<sign>[+-])(?P<hours>\d{2})(?::?(?P<minutes>\d{2}))?$",
        text,
    )
    if offset_match:
        head = offset_match.group("head")
        offset_hours = int(offset_match.group("hours"))
        offset_minutes = int(offset_match.group("minutes") or "0")
        total_minutes = offset_hours * 60 + offset_minutes
        if offset_match.group("sign") == "-":
            total_minutes *= -1
        tzinfo = timezone(timezone.utc.utcoffset(None) + timedelta(minutes=total_minutes))
        for pattern in ("%a %Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(head, pattern).replace(tzinfo=tzinfo)
                return _to_utc_iso(parsed)
            except ValueError:
                continue
    normalized_text = re.sub(r"([+-]\d{2})$", lambda match: f"{match.group(1)}00", text)
    for candidate in (text, normalized_text):
        for pattern in (
        "%a %Y-%m-%d %H:%M:%S %z",
        "%a %Y-%m-%d %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S %Z",
        ):
            try:
                return _to_utc_iso(datetime.strptime(candidate, pattern))
            except ValueError:
                continue
    try:
        return _to_utc_iso(datetime.fromisoformat(text))
    except ValueError:
        return None


def _parse_usec_timestamp(raw: str | None) -> str | None:
    usec = _parse_optional_int(raw)
    if not usec:
        return None
    return datetime.fromtimestamp(usec / 1_000_000, tz=timezone.utc).isoformat()


def _uptime_seconds(started_at_iso: str | None) -> int | None:
    if not started_at_iso:
        return None
    try:
        started_at = datetime.fromisoformat(started_at_iso)
    except ValueError:
        return None
    return max(0, int((datetime.now(timezone.utc) - started_at).total_seconds()))


def display_state_for_unit(active_state: str | None, sub_state: str | None, *, pending_action: str | None = None) -> str:
    active = str(active_state or "").strip().lower()
    sub = str(sub_state or "").strip().lower()
    action = str(pending_action or "").strip().lower()
    if active == "active" and sub in {"running", "listening", "exited"}:
        return "running"
    if active == "inactive":
        return "stopped"
    if active == "failed":
        return "failed"
    if active == "activating":
        return "restarting" if action == "restart" else "starting"
    if active == "deactivating":
        return "restarting" if action == "restart" else "stopping"
    return active or "unknown"


def get_unit_status(target: str, *, pending_action: str | None = None) -> dict[str, Any]:
    unit = unit_name(target)
    show = _systemctl_show(
        unit,
        (
            "Id",
            "ActiveState",
            "SubState",
            "Result",
            "ExecMainPID",
            "MainPID",
            "ActiveEnterTimestamp",
            "ActiveEnterTimestampUSec",
            "InactiveEnterTimestamp",
            "InactiveEnterTimestampUSec",
            "ExecMainStatus",
            "UnitFileState",
            "FragmentPath",
        ),
    )
    started_at = _parse_systemd_timestamp(show.get("ActiveEnterTimestampUSec")) or _parse_systemd_timestamp(
        show.get("ActiveEnterTimestamp")
    )
    active_state = str(show.get("ActiveState") or "").strip().lower() or "unknown"
    sub_state = str(show.get("SubState") or "").strip().lower() or "unknown"
    main_pid = _parse_optional_int(show.get("ExecMainPID")) or _parse_optional_int(show.get("MainPID"))
    return {
        "target": target,
        "unit": unit,
        "display_state": display_state_for_unit(active_state, sub_state, pending_action=pending_action),
        "active_state": active_state,
        "sub_state": sub_state,
        "result": str(show.get("Result") or "").strip() or None,
        "main_pid": main_pid,
        "started_at": started_at,
        "stopped_at": _parse_systemd_timestamp(show.get("InactiveEnterTimestampUSec"))
        or _parse_systemd_timestamp(show.get("InactiveEnterTimestamp")),
        "uptime_sec": _uptime_seconds(started_at) if active_state == "active" else None,
        "exec_main_status": _parse_optional_int(show.get("ExecMainStatus")),
        "unit_file_state": str(show.get("UnitFileState") or "").strip() or None,
        "fragment_path": str(show.get("FragmentPath") or "").strip() or None,
        "status_excerpt": _status_excerpt(unit),
    }


def _reset_failed(unit: str) -> None:
    _run(["systemctl", "--user", "reset-failed", unit], cwd=WORKSPACE_ROOT, check=False)


def _stop_unit(unit: str) -> None:
    _run(["systemctl", "--user", "stop", unit], cwd=WORKSPACE_ROOT, check=False)


def start_target(target: str) -> subprocess.CompletedProcess[str]:
    unit = unit_name(target)
    _reset_failed(unit)
    _stop_unit(unit)
    return _run(
        [
            "systemd-run",
            "--user",
            f"--unit={unit}",
            f"--description={_DESCRIPTION_BY_TARGET[target]}",
            "/bin/bash",
            "-lc",
            runtime_command(target),
        ],
        cwd=WORKSPACE_ROOT,
        check=True,
    )


def stop_target(target: str) -> subprocess.CompletedProcess[str]:
    if target == "server":
        _run([str(SERVER_PYTHON), "scripts/stop_server.py"], cwd=WORKSPACE_ROOT, check=False)
        _stop_unit(SERVER_UNIT)
        return subprocess.CompletedProcess(args=["stop", target], returncode=0, stdout="", stderr="")
    if target == "agent":
        _run([str(AGENT_PYTHON), "scripts/stop_agent.py"], cwd=WORKSPACE_ROOT, check=False)
        _stop_unit(AGENT_UNIT)
        return subprocess.CompletedProcess(args=["stop", target], returncode=0, stdout="", stderr="")
    if target == "control":
        _stop_unit(CONTROL_UNIT)
        return subprocess.CompletedProcess(args=["stop", target], returncode=0, stdout="", stderr="")
    raise ValueError(f"Unsupported target: {target}")


def restart_target(target: str) -> subprocess.CompletedProcess[str]:
    stop_target(target)
    return start_target(target)


def wait_for_target_state(
    target: str,
    desired_states: Iterable[str],
    *,
    timeout_sec: float = 20.0,
    pending_action: str | None = None,
) -> dict[str, Any]:
    expected = {str(item).strip().lower() for item in desired_states if str(item).strip()}
    deadline = time.monotonic() + timeout_sec
    last_status = get_unit_status(target, pending_action=pending_action)
    while time.monotonic() <= deadline:
        last_status = get_unit_status(target, pending_action=pending_action)
        display_state = str(last_status.get("display_state") or "").lower()
        if display_state in expected or display_state == "failed":
            return last_status
        time.sleep(0.5)
    return last_status


def smoke_server() -> subprocess.CompletedProcess[str]:
    return _run_shell(
        f"cd {WORKSPACE_ROOT} && BASE_URL=http://192.168.100.17:8666 {SERVER_PYTHON} scripts/smoke_test.py",
        check=True,
    )


def run_action_and_wait(target: str, action: str) -> dict[str, Any]:
    normalized_target = str(target or "").strip().lower()
    normalized_action = str(action or "").strip().lower()
    if normalized_target not in SYSTEMD_TARGETS:
        raise ValueError(f"Unsupported target: {target}")
    if normalized_action == "start":
        start_target(normalized_target)
        return wait_for_target_state(normalized_target, {"running"}, timeout_sec=25.0, pending_action="start")
    if normalized_action == "stop":
        stop_target(normalized_target)
        return wait_for_target_state(normalized_target, {"stopped"}, timeout_sec=20.0, pending_action="stop")
    if normalized_action == "restart":
        restart_target(normalized_target)
        return wait_for_target_state(normalized_target, {"running"}, timeout_sec=30.0, pending_action="restart")
    raise ValueError(f"Unsupported action: {action}")


def level_name_from_priority(raw: int | None) -> str:
    priority = int(raw) if raw is not None else 6
    if priority <= 2:
        return "critical"
    if priority == 3:
        return "error"
    if priority == 4:
        return "warning"
    if priority == 5:
        return "notice"
    if priority == 6:
        return "info"
    return "debug"


def _timestamp_from_journal_usec(raw: str | None) -> str | None:
    value = _parse_optional_int(raw)
    if not value:
        return None
    return datetime.fromtimestamp(value / 1_000_000, tz=timezone.utc).isoformat()


def list_journal_entries(target: str, *, lines: int = 200) -> list[dict[str, Any]]:
    unit = unit_name(target)
    completed = _run(
        ["journalctl", "--user", "-u", unit, "-n", str(max(1, min(int(lines), 2000))), "--no-pager", "-o", "json"],
        cwd=WORKSPACE_ROOT,
        check=False,
    )
    entries: list[dict[str, Any]] = []
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except (TypeError, ValueError):
            continue
        priority = _parse_optional_int(payload.get("PRIORITY"))
        entries.append(
            {
                "timestamp": _timestamp_from_journal_usec(payload.get("__REALTIME_TIMESTAMP")),
                "priority": priority,
                "level": level_name_from_priority(priority),
                "message": str(payload.get("MESSAGE") or "").strip(),
                "pid": _parse_optional_int(payload.get("_PID")),
                "identifier": str(payload.get("SYSLOG_IDENTIFIER") or payload.get("_COMM") or "").strip() or None,
                "unit": unit,
            }
        )
    return entries


def filter_log_entries(
    entries: Iterable[dict[str, Any]],
    *,
    levels: Iterable[str] | None = None,
    contains: str | None = None,
) -> list[dict[str, Any]]:
    level_filter = {str(item).strip().lower() for item in (levels or []) if str(item).strip()}
    needle = str(contains or "").strip().lower()
    result: list[dict[str, Any]] = []
    for entry in entries:
        if level_filter and str(entry.get("level") or "").lower() not in level_filter:
            continue
        if needle:
            haystack = " ".join(
                [
                    str(entry.get("message") or ""),
                    str(entry.get("identifier") or ""),
                    str(entry.get("pid") or ""),
                ]
            ).lower()
            if needle not in haystack:
                continue
        result.append(entry)
    return result


def format_log_entries_as_text(entries: Iterable[dict[str, Any]]) -> str:
    lines: list[str] = []
    for entry in entries:
        timestamp = entry.get("timestamp") or "-"
        level = str(entry.get("level") or "info").upper()
        identifier = entry.get("identifier") or "server"
        pid = entry.get("pid")
        pid_suffix = f" pid={pid}" if pid else ""
        lines.append(f"[{timestamp}] [{level}] [{identifier}{pid_suffix}] {entry.get('message') or ''}".rstrip())
    return "\n".join(lines)


def stream_journal_logs(target: str, *, lines: int = 80, follow: bool = False) -> int:
    unit = unit_name(target)
    args = ["journalctl", "--user", "-u", unit, "-n", str(max(1, int(lines))), "--no-pager"]
    if follow:
        args.insert(-1, "-f")
    completed = subprocess.run(args, cwd=WORKSPACE_ROOT, check=False)
    return int(completed.returncode)
