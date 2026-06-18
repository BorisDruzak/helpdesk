"""
Точка входа launcher: запуск текущей версии агента, при exit 42 или наличии pending_update — установка обновления.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Минимальные зависимости; installer импортируется здесь
from pc_agent.core.runtime_paths import resolve_data_root, resolve_install_root
from pc_agent.launcher.installer import apply_update, _find_agent_binary
from pc_agent.version import EXIT_UPDATE_PENDING


IMMEDIATE_CRASH_WINDOW_SEC = 20.0
IMMEDIATE_CRASH_RETRY_LIMIT = 3


def _log(msg: str) -> None:
    print(f"[launcher] {msg}", flush=True)


def _load_current_state(current_path: Path, versions_dir: Path) -> tuple[dict[str, Any], str, str | None, Path]:
    current = json.loads(current_path.read_text(encoding="utf-8-sig"))
    version = str(current.get("version") or "").strip()
    if not version:
        raise RuntimeError("current.json missing 'version'")
    previous = str(current.get("previous") or "").strip() or None
    version_dir = versions_dir / version
    if not version_dir.is_dir():
        raise RuntimeError(f"Version dir not found: {version_dir}")
    try:
        binary_path = _find_agent_binary(version_dir)
    except FileNotFoundError as exc:
        raise RuntimeError(str(exc)) from exc
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
        json.dumps({"version": fallback_version, "previous": crashed_version}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="PC Agent Launcher")
    parser.add_argument("--data-dir", type=str, default=None, help="Data root (default: env/config)")
    parser.add_argument("--install-root", type=str, default=None, help="Install root (default: env/config)")
    parser.add_argument("--gui", action="store_true", help="Запустить агент с GUI (по умолчанию)")
    parser.add_argument("--no-gui", action="store_true", help="Запустить агент без GUI (консольный режим)")
    args = parser.parse_args()
    use_gui = args.gui or not args.no_gui  # по умолчанию GUI включён
    data_root = resolve_data_root(cli_value=args.data_dir)
    install_root = resolve_install_root(cli_value=args.install_root)
    current_path = install_root / "current.json"
    pending_path = data_root / "updates" / "pending_update.json"
    updates_dir = data_root / "updates"
    versions_dir = install_root / "versions"
    if not current_path.exists():
        _log(f"current.json not found at {current_path}; create it with initial version")
        sys.exit(1)

    try:
        _, version, previous_version, binary_path = _load_current_state(current_path, versions_dir)
    except RuntimeError as e:
        _log(str(e))
        sys.exit(1)
    env = os.environ.copy()
    env["PC_AGENT_DATA_DIR"] = str(data_root)
    env["PC_AGENT_INSTALL_ROOT"] = str(install_root)
    backoff = 1.0
    max_backoff = 60.0
    immediate_crash_attempts = 0
    immediate_crash_version: str | None = None
    while True:
        if pending_path.exists():
            _log("pending_update.json found, applying update...")
            ok_, msg = apply_update(install_root, data_root, pending_path, log_message=_log)
            if ok_:
                _log(f"Update applied: {msg}; restarting with new version")
            else:
                _log(f"Update failed: {msg}; restarting current version")
            backoff = 1.0
            try:
                _, version, previous_version, binary_path = _load_current_state(current_path, versions_dir)
            except RuntimeError as e:
                _log(str(e))
                sys.exit(1)
            immediate_crash_attempts = 0
            immediate_crash_version = None
        agent_argv = [str(binary_path)]
        if use_gui:
            agent_argv.append("--gui")
        else:
            agent_argv.append("--no-gui")
        started_at = time.monotonic()
        proc = subprocess.Popen(
            agent_argv,
            env=env,
            cwd=str(binary_path.parent),
            stdout=sys.stdout,
            stderr=sys.stderr,
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
            raise SystemExit(0)

        if elapsed_sec <= IMMEDIATE_CRASH_WINDOW_SEC:
            if immediate_crash_version != version:
                immediate_crash_version = version
                immediate_crash_attempts = 0
            immediate_crash_attempts += 1
            _log(
                f"Agent {version} crashed after {elapsed_sec:.1f}s with code {ret} "
                f"(attempt {immediate_crash_attempts}/{IMMEDIATE_CRASH_RETRY_LIMIT})"
            )
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
                    _log(f"Rollback failed: {e}")
                    sys.exit(1)
                backoff = 1.0
                immediate_crash_attempts = 0
                immediate_crash_version = None
                continue
            if immediate_crash_attempts >= IMMEDIATE_CRASH_RETRY_LIMIT:
                message = (
                    f"Agent {version} failed to start {immediate_crash_attempts} times "
                    f"within {IMMEDIATE_CRASH_WINDOW_SEC:.0f}s; rollback is unavailable. "
                    "Stopping launcher. Check last_failed_launch.json and agent logs."
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
                raise SystemExit(ret or 1)
        else:
            immediate_crash_attempts = 0
            immediate_crash_version = None
        _log(f"Agent exited with code {ret}; restart in {backoff:.0f}s")
        time.sleep(min(backoff, max_backoff))
        backoff = min(backoff * 2, max_backoff)


if __name__ == "__main__":
    main()
