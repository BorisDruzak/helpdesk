"""
Standalone updater process for pc_agent self-update (in-place).

DEPRECATED (Update v2): Агент больше не запускает этот процесс. Вместо этого агент
пишет data_root/updates/pending_update.json и выходит с кодом 42; обновление
применяет launcher (pc_agent/launcher/). Оставлен для обратной совместимости/ручного отката.

Designed to run in a separate process; uses only stdlib (no project imports).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


PRESERVE_DIRS = {"data", "logs", "uploads", "venv", ".venv", "__pycache__"}
PRESERVE_FILES = {"config/settings.yaml", ".env", ".env.local"}


@dataclass(frozen=True)
class RestartSpec:
    python: str
    args: list[str]
    cwd: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _wait_for_pid_exit(pid: int, timeout_sec: int = 120) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.25)
    raise TimeoutError(f"Parent process did not exit within {timeout_sec}s (pid={pid})")


def _rm_tree(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=False)
    else:
        path.unlink(missing_ok=True)


def _copy_any(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=False)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _backup_item(item: Path, backup_root: Path) -> None:
    rel = item.name
    dst = backup_root / rel
    if dst.exists():
        _rm_tree(dst)
    _copy_any(item, dst)


def _detect_payload_root(extracted_dir: Path) -> Path:
    # Prefer pc_agent/ subdir if the zip was made from project root.
    candidate = extracted_dir / "pc_agent"
    if candidate.exists() and candidate.is_dir():
        return candidate
    return extracted_dir


def _restore_preserved_files(agent_dir: Path, preserved: dict[str, bytes]) -> None:
    for rel, content in preserved.items():
        p = agent_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)


def _apply_update_in_place(
    *,
    payload_root: Path,
    agent_dir: Path,
    backup_dir: Path,
) -> list[str]:
    """
    Replace top-level items in agent_dir with those from payload_root.

    Returns list of updated item names for reporting.
    """
    updated_items: list[str] = []

    payload_items = [p for p in payload_root.iterdir() if p.name not in PRESERVE_DIRS]
    # Update utils last (minimize chance of breaking the updater mid-run)
    payload_items.sort(key=lambda p: (p.name == "utils", p.name))

    for src_item in payload_items:
        name = src_item.name
        dst_item = agent_dir / name

        if name in PRESERVE_DIRS:
            continue

        if dst_item.exists():
            _backup_item(dst_item, backup_dir)
            _rm_tree(dst_item)

        _copy_any(src_item, dst_item)
        updated_items.append(name)

    return updated_items


def _rollback_from_backup(agent_dir: Path, backup_dir: Path) -> None:
    for src in backup_dir.iterdir():
        dst = agent_dir / src.name
        if dst.exists():
            _rm_tree(dst)
        _copy_any(src, dst)


def _parse_restart(payload: dict) -> Optional[RestartSpec]:
    rs = payload.get("restart")
    if not isinstance(rs, dict):
        return None
    python = rs.get("python")
    args = rs.get("args")
    cwd = rs.get("cwd")
    if not isinstance(python, str) or not isinstance(cwd, str) or not isinstance(args, list):
        return None
    args2: list[str] = []
    for a in args:
        if isinstance(a, str):
            args2.append(a)
    return RestartSpec(python=python, args=args2, cwd=cwd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pending", required=True, help="Path to pending_update.json")
    ap.add_argument("--wait-timeout-sec", type=int, default=180)
    ns = ap.parse_args()

    pending_path = Path(ns.pending).resolve()
    pending = _read_json(pending_path)

    agent_dir = Path(pending["agent_dir"]).resolve()
    zip_path = Path(pending["zip_path"]).resolve()
    parent_pid = int(pending.get("parent_pid") or 0)

    updates_dir = pending_path.parent
    report_path = updates_dir / "last_update.json"
    backup_root = agent_dir / "data" / "agent_backups"
    backup_dir = backup_root / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    extract_dir = updates_dir / "extract_tmp"

    preserved_files: dict[str, bytes] = {}
    for rel in PRESERVE_FILES:
        p = agent_dir / rel
        if p.exists() and p.is_file():
            preserved_files[rel] = p.read_bytes()

    report: dict = {
        "started_at": _utc_now_iso(),
        "version": pending.get("version"),
        "target": pending.get("target"),
        "channel": pending.get("channel"),
        "zip_path": str(zip_path),
        "status": "running",
    }
    _write_json(report_path, report)

    try:
        if parent_pid:
            _wait_for_pid_exit(parent_pid, timeout_sec=int(ns.wait_timeout_sec))

        # Chdir out of agent_dir to reduce Windows rename/delete quirks
        try:
            os.chdir(str(agent_dir.parent))
        except Exception:
            pass

        if extract_dir.exists():
            _rm_tree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        payload_root = _detect_payload_root(extract_dir)

        backup_dir.mkdir(parents=True, exist_ok=True)
        updated_items = _apply_update_in_place(payload_root=payload_root, agent_dir=agent_dir, backup_dir=backup_dir)

        _restore_preserved_files(agent_dir, preserved_files)

        report.update(
            {
                "status": "success",
                "finished_at": _utc_now_iso(),
                "updated_items": updated_items,
                "backup_dir": str(backup_dir),
            }
        )
        _write_json(report_path, report)

    except Exception as e:
        # Best-effort rollback
        try:
            if backup_dir.exists():
                _rollback_from_backup(agent_dir, backup_dir)
                _restore_preserved_files(agent_dir, preserved_files)
        except Exception:
            pass

        report.update(
            {
                "status": "error",
                "finished_at": _utc_now_iso(),
                "error": str(e),
                "backup_dir": str(backup_dir) if backup_dir.exists() else None,
            }
        )
        _write_json(report_path, report)
        return 2
    finally:
        try:
            if extract_dir.exists():
                _rm_tree(extract_dir)
        except Exception:
            pass

    restart = _parse_restart(pending)
    if restart:
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
        try:
            subprocess.Popen(
                [restart.python, *restart.args],
                cwd=restart.cwd,
                creationflags=creationflags,
                close_fds=(os.name != "nt"),
            )
            report["restart"] = {"status": "started", "at": _utc_now_iso()}
            _write_json(report_path, report)
        except Exception as e:
            report["restart"] = {"status": "error", "at": _utc_now_iso(), "error": str(e)}
            _write_json(report_path, report)
            return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

