"""
Portable launcher entrypoint for Windows release.

Behavior:
- prefers local install/data roots near launcher.exe
- supports legacy CLI args --install-root / --data-dir
- applies pending updates and restarts agent
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from pc_agent.core.runtime_paths import resolve_data_root, resolve_install_root
from pc_agent.core.single_instance import SingleInstanceLock
from pc_agent.launcher.installer import _find_agent_binary, apply_update
from pc_agent.version import EXIT_UPDATE_PENDING


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
        _log("another launcher instance is already running; exiting")
        sys.exit(0)

    current_path = install_root / "current.json"
    pending_path = data_root / "updates" / "pending_update.json"
    versions_dir = install_root / "versions"
    if not current_path.exists():
        _log(f"current.json not found at {current_path}; create it with initial version")
        sys.exit(1)

    try:
        current = json.loads(current_path.read_text(encoding="utf-8"))
        version = current.get("version")
    except Exception as e:
        _log(f"Invalid current.json: {e}")
        sys.exit(1)
    if not version:
        _log("current.json missing 'version'")
        sys.exit(1)

    version_dir = versions_dir / version
    if not version_dir.is_dir():
        _log(f"Version dir not found: {version_dir}")
        sys.exit(1)
    try:
        binary_path = _find_agent_binary(version_dir)
    except FileNotFoundError as e:
        _log(str(e))
        sys.exit(1)

    env = os.environ.copy()
    env["PC_AGENT_DATA_DIR"] = str(data_root)
    env["PC_AGENT_INSTALL_ROOT"] = str(install_root)
    backoff = 1.0
    max_backoff = 60.0

    try:
        while True:
            if pending_path.exists():
                _log("pending_update.json found, applying update...")
                ok_, msg = apply_update(install_root, data_root, pending_path, log_message=_log)
                if ok_:
                    _log(f"Update applied: {msg}; restarting with new version")
                    backoff = 1.0
                    try:
                        current = json.loads(current_path.read_text(encoding="utf-8"))
                        version = current.get("version")
                        version_dir = versions_dir / version
                        binary_path = _find_agent_binary(version_dir)
                    except Exception:
                        pass
                else:
                    _log(f"Update failed: {msg}; restarting current version")

            proc = subprocess.Popen(
                [str(binary_path)],
                env=env,
                cwd=str(binary_path.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            ret = proc.wait()
            if ret == EXIT_UPDATE_PENDING:
                _log("Agent exited with update-pending (42); will apply update and restart")
                backoff = 1.0
                continue
            if pending_path.exists():
                _log("pending_update.json present after exit; applying update")
                continue
            if ret == 0:
                _log("Agent exited normally (code 0); stopping launcher")
                break
            _log(f"Agent exited with code {ret}; restart in {backoff:.0f}s")
            time.sleep(min(backoff, max_backoff))
            backoff = min(backoff * 2, max_backoff)
    finally:
        lock.release()


if __name__ == "__main__":
    main()
