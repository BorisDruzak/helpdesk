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
from pathlib import Path

# Минимальные зависимости; installer импортируется здесь
from pc_agent.core.runtime_paths import resolve_data_root, resolve_install_root
from pc_agent.launcher.installer import apply_update, _find_agent_binary
from pc_agent.version import EXIT_UPDATE_PENDING


def _log(msg: str) -> None:
    print(f"[launcher] {msg}", flush=True)


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
        agent_argv = [str(binary_path)]
        if use_gui:
            agent_argv.append("--gui")
        proc = subprocess.Popen(
            agent_argv,
            env=env,
            cwd=str(binary_path.parent),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        ret = proc.wait()
        if ret == EXIT_UPDATE_PENDING:
            _log("Agent exited with update-pending (42); will apply update and restart")
            backoff = 1.0
            continue
        if pending_path.exists():
            _log("pending_update.json present after exit; applying update")
            continue
        _log(f"Agent exited with code {ret}; restart in {backoff:.0f}s")
        time.sleep(min(backoff, max_backoff))
        backoff = min(backoff * 2, max_backoff)


if __name__ == "__main__":
    main()
