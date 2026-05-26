"""
Portable launcher entrypoint for Windows release.

Behavior:
- prefers local install/data roots near launcher.exe
- supports legacy CLI args --install-root / --data-dir
- applies pending updates and restarts agent
- rolls back to the previous version after a repeated immediate crash loop
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pc_agent.auth.token_source import import_missing_auth_token_from_data_roots
from pc_agent.core.runtime_paths import resolve_data_root, resolve_install_root
from pc_agent.core.single_instance import SingleInstanceLock
from pc_agent.launcher.installer import _find_agent_binary, apply_update
from pc_agent.version import EXIT_UPDATE_PENDING

IMMEDIATE_CRASH_WINDOW_SEC = 20.0
IMMEDIATE_CRASH_RETRY_LIMIT = 3
AGENT_EXIT_ALREADY_RUNNING = 2


def _log(msg: str) -> None:
    line = f"[launcher] {msg}"
    # In windowed (console=False) builds, stdout/stderr can be invalid handles.
    # Keep logging best-effort and never crash launcher because of diagnostics.
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        log_path = exe_dir / "launcher.log"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _show_user_error(title: str, message: str) -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        pass


def _fail_fast(message: str, *, title: str = "Maria Agent Launcher", exit_code: int = 1) -> None:
    _log(message)
    _show_user_error(title, message)
    raise SystemExit(exit_code)


def _detect_install_root(exe_dir: Path) -> Path | None:
    direct = exe_dir / "install"
    if (direct / "current.json").exists():
        return direct
    if (exe_dir / "current.json").exists() and (exe_dir / "versions").is_dir():
        return exe_dir
    release_dir = exe_dir / "release"
    if release_dir.is_dir():
        candidates = list(release_dir.rglob("install/current.json"))
        if candidates:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return candidates[0].parent
    return None


def _detect_data_root(exe_dir: Path) -> Path:
    data_root = exe_dir / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    return data_root


def _default_primary_agent_data_dir() -> Path | None:
    if os.name != "nt":
        return None
    local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
    if local_appdata:
        return (Path(local_appdata) / "PCClientAgent" / "data").resolve()
    return (Path.home() / "AppData" / "Local" / "PCClientAgent" / "data").resolve()


def _seed_auth_token_from_primary_install(data_root: Path) -> bool:
    if os.environ.get("AUTH_TOKEN"):
        return False
    primary_data_dir = _default_primary_agent_data_dir()
    if primary_data_dir is None:
        return False
    return import_missing_auth_token_from_data_roots(
        primary_data_dir,
        data_root,
        log_message=_log,
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_current_state(current_path: Path, versions_dir: Path) -> tuple[dict[str, Any], str, str | None, Path]:
    try:
        current = _read_json(current_path)
    except Exception as e:
        raise RuntimeError(f"Invalid current.json: {e}") from e
    version = str(current.get("version") or "").strip()
    if not version:
        raise RuntimeError("current.json missing 'version'")
    previous = str(current.get("previous") or "").strip() or None
    version_dir = versions_dir / version
    if not version_dir.is_dir():
        raise RuntimeError(f"Version dir not found: {version_dir}")
    try:
        binary_path = _find_agent_binary(version_dir)
    except FileNotFoundError as e:
        raise RuntimeError(str(e)) from e
    return current, version, previous, binary_path


def _append_update_history(updates_dir: Path, entry: dict[str, Any]) -> None:
    history_path = updates_dir / "update_history.json"
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            history = []
    else:
        history = []
    if not isinstance(history, list):
        history = []
    history.append(entry)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history[-100:], ensure_ascii=False, indent=2), encoding="utf-8")


def _write_failed_launch_marker(
    updates_dir: Path,
    *,
    crashed_version: str,
    rollback_version: str | None,
    exit_code: int,
    elapsed_sec: float,
    attempts: int,
    message: str | None = None,
) -> None:
    payload = {
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "reason": "startup_crash_rollback" if rollback_version else "startup_crash",
        "crashed_version": crashed_version,
        "rollback_version": rollback_version,
        "exit_code": exit_code,
        "elapsed_sec": round(elapsed_sec, 3),
        "attempts": attempts,
    }
    if message:
        payload["message"] = message
    updates_dir.mkdir(parents=True, exist_ok=True)
    (updates_dir / "last_failed_launch.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _rollback_current_version(current_path: Path, *, crashed_version: str, fallback_version: str) -> None:
    current_path.write_text(
        json.dumps(
            {"version": fallback_version, "previous": crashed_version},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _read_log_tail(log_path: Path, *, max_lines: int = 40) -> list[str]:
    if not log_path.exists():
        return []
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    return [line.rstrip() for line in lines[-max_lines:] if line.strip()]


def _log_crash_context(session_log_path: Path) -> None:
    for line in _read_log_tail(session_log_path):
        _log(f"agent> {line}")


def main() -> None:
    parser = argparse.ArgumentParser(description="PC Agent Launcher (portable)")
    parser.add_argument("--data-dir", type=str, default=None, help="Data root")
    parser.add_argument("--install-root", type=str, default=None, help="Install root")
    args = parser.parse_args()

    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

    install_cli = args.install_root
    data_cli = args.data_dir
    if not install_cli and "PC_AGENT_INSTALL_ROOT" not in os.environ:
        local_install = _detect_install_root(exe_dir)
        if local_install is not None:
            install_cli = str(local_install)
            _log(f"auto-detected install_root: {install_cli}")
    if not data_cli and "PC_AGENT_DATA_DIR" not in os.environ:
        local_data = _detect_data_root(exe_dir)
        data_cli = str(local_data)
        _log(f"auto-detected data_root: {data_cli}")

    data_root = resolve_data_root(cli_value=data_cli)
    install_root = resolve_install_root(cli_value=install_cli)
    lock = SingleInstanceLock(data_root / "launcher.lock")
    if not lock.acquire():
        _fail_fast(
            "Maria Agent is already running from this portable folder.",
            title="Maria Agent is already running",
            exit_code=0,
        )

    current_path = install_root / "current.json"
    pending_path = data_root / "updates" / "pending_update.json"
    updates_dir = data_root / "updates"
    session_log_path = data_root / "logs" / "launcher-child-session.log"
    versions_dir = install_root / "versions"
    if not current_path.exists():
        _fail_fast(f"current.json not found at {current_path}; create it with initial version")

    try:
        _, version, previous_version, binary_path = _load_current_state(current_path, versions_dir)
    except RuntimeError as e:
        _fail_fast(str(e))

    env = os.environ.copy()
    env["PC_AGENT_DATA_DIR"] = str(data_root)
    env["PC_AGENT_INSTALL_ROOT"] = str(install_root)
    backoff = 1.0
    max_backoff = 60.0
    immediate_crash_attempts = 0
    immediate_crash_version: str | None = None

    try:
        _seed_auth_token_from_primary_install(data_root)
        while True:
            if pending_path.exists():
                _log("pending_update.json found, applying update...")
                ok_, msg = apply_update(install_root, data_root, pending_path, log_message=_log)
                if ok_:
                    _log(f"Update applied: {msg}; restarting with new version")
                    backoff = 1.0
                else:
                    _log(f"Update failed: {msg}; restarting current version")
                try:
                    _, version, previous_version, binary_path = _load_current_state(current_path, versions_dir)
                except RuntimeError as e:
                    _fail_fast(str(e))
                immediate_crash_attempts = 0
                immediate_crash_version = None

            session_log_path.parent.mkdir(parents=True, exist_ok=True)
            with session_log_path.open("wb") as session_log:
                started_at = time.monotonic()
                proc = subprocess.Popen(
                    [str(binary_path)],
                    env=env,
                    cwd=str(binary_path.parent),
                    stdout=session_log,
                    stderr=session_log,
                )
                ret = proc.wait()
                elapsed_sec = time.monotonic() - started_at

            if ret == EXIT_UPDATE_PENDING:
                _log("Agent exited with update-pending (42); will apply update and restart")
                backoff = 1.0
                immediate_crash_attempts = 0
                immediate_crash_version = None
                continue
            if pending_path.exists():
                _log("pending_update.json present after exit; applying update")
                immediate_crash_attempts = 0
                immediate_crash_version = None
                continue
            if ret == 0:
                _log("Agent exited normally (code 0); stopping launcher")
                break
            if ret == AGENT_EXIT_ALREADY_RUNNING:
                _log_crash_context(session_log_path)
                _fail_fast(
                    "Another Maria Agent instance is already using this portable data folder.",
                    title="Maria Agent is already running",
                    exit_code=0,
                )
                break

            if elapsed_sec <= IMMEDIATE_CRASH_WINDOW_SEC:
                if immediate_crash_version != version:
                    immediate_crash_version = version
                    immediate_crash_attempts = 0
                immediate_crash_attempts += 1
                _log(
                    f"Agent {version} crashed after {elapsed_sec:.1f}s with code {ret} "
                    f"(attempt {immediate_crash_attempts}/{IMMEDIATE_CRASH_RETRY_LIMIT})"
                )
                _log_crash_context(session_log_path)
                if immediate_crash_attempts >= IMMEDIATE_CRASH_RETRY_LIMIT and previous_version and previous_version != version:
                    _log(
                        f"Terminal startup crash detected for {version}; "
                        f"rolling back to previous version {previous_version}"
                    )
                    _append_update_history(
                        updates_dir,
                        {
                            "version": version,
                            "success": False,
                            "at": datetime.now(timezone.utc).isoformat(),
                            "reason": "startup_crash_rollback",
                            "message": (
                                f"Rolled back to {previous_version} after "
                                f"{immediate_crash_attempts} immediate crashes (exit code {ret})"
                            ),
                            "previous_version": previous_version,
                        },
                    )
                    _write_failed_launch_marker(
                        updates_dir,
                        crashed_version=version,
                        rollback_version=previous_version,
                        exit_code=ret,
                        elapsed_sec=elapsed_sec,
                        attempts=immediate_crash_attempts,
                    )
                    try:
                        _rollback_current_version(
                            current_path,
                            crashed_version=version,
                            fallback_version=previous_version,
                        )
                        _, version, previous_version, binary_path = _load_current_state(current_path, versions_dir)
                    except RuntimeError as e:
                        _fail_fast(f"Rollback failed: {e}")
                    backoff = 1.0
                    immediate_crash_attempts = 0
                    immediate_crash_version = None
                    continue
                if immediate_crash_attempts >= IMMEDIATE_CRASH_RETRY_LIMIT:
                    message = (
                        f"Agent {version} failed to start {immediate_crash_attempts} times "
                        f"within {IMMEDIATE_CRASH_WINDOW_SEC:.0f}s; rollback is unavailable. "
                        "Stopping launcher. Check data/logs/launcher-child-session.log "
                        "and data/updates/last_failed_launch.json."
                    )
                    _log(message)
                    _append_update_history(
                        updates_dir,
                        {
                            "version": version,
                            "success": False,
                            "at": datetime.now(timezone.utc).isoformat(),
                            "reason": "startup_crash",
                            "message": message,
                            "previous_version": previous_version,
                        },
                    )
                    _write_failed_launch_marker(
                        updates_dir,
                        crashed_version=version,
                        rollback_version=None,
                        exit_code=ret,
                        elapsed_sec=elapsed_sec,
                        attempts=immediate_crash_attempts,
                        message=message,
                    )
                    _fail_fast(message, title="Maria Agent failed to start", exit_code=ret or 1)
            else:
                immediate_crash_attempts = 0
                immediate_crash_version = None

            _log(f"Agent exited with code {ret}; restart in {backoff:.0f}s")
            time.sleep(min(backoff, max_backoff))
            backoff = min(backoff * 2, max_backoff)
    finally:
        lock.release()


if __name__ == "__main__":
    main()
