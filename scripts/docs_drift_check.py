#!/usr/bin/env python3
"""Require documentation updates for code changes without a navigation index."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTATION_SUFFIXES = (".md", ".mdc", ".toml")
DOCUMENTATION_FILES = {"PLANS.md"}
CODE_PREFIXES = ("server/", "webapp/", "mcp_helpdesk_server/", "scripts/")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Проверка дрифта между кодом и docs/CODEMAP.")
    parser.add_argument("--base", help="Git base revision for docs drift check")
    parser.add_argument("--staged", action="store_true", help="Смотреть staged diff вместо worktree")
    parser.add_argument("--paths", nargs="*", help="Ограничить анализ указанными путями")
    parser.add_argument("--json", action="store_true", help="Печатать результат в JSON")
    return parser.parse_args()


def repo_path(value: str | Path) -> str:
    return str(value).replace("\\", "/").strip("/")


@dataclass(frozen=True)
class ChangedPath:
    status: str
    path: str
    old_path: str | None = None


def _parse_name_status(output: str) -> list[ChangedPath]:
    changes: list[ChangedPath] = []
    for raw_line in output.splitlines():
        parts = raw_line.split("\t")
        status = parts[0].strip() if parts else ""
        if status.startswith("R") and len(parts) >= 3:
            changes.append(ChangedPath(status="R", old_path=repo_path(parts[1]), path=repo_path(parts[2])))
        elif len(parts) >= 2:
            changes.append(ChangedPath(status=status[:1], path=repo_path(parts[1])))
    return changes


def collect_changed_paths(
    *, base: str | None = None, staged: bool = False, pathspecs: Sequence[str] | None = None
) -> list[ChangedPath]:
    pathspec_list = [repo_path(item) for item in (pathspecs or ())]
    command = ["git", "diff", "--name-status", "--find-renames", "--relative"]
    if staged:
        command.append("--cached")
    if base:
        command.append(f"{base}...HEAD")
    elif not staged:
        command.append("HEAD")
    if pathspec_list:
        command.extend(("--", *pathspec_list))
    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    return _parse_name_status(result.stdout)


def is_documentation_artifact(path: str) -> bool:
    normalized = repo_path(path)
    return normalized in DOCUMENTATION_FILES or normalized.endswith(DOCUMENTATION_SUFFIXES) or normalized.endswith("/SKILL.md")


def needs_documentation(path: str) -> bool:
    normalized = repo_path(path)
    if not normalized.startswith(CODE_PREFIXES) or is_documentation_artifact(normalized):
        return False
    return "/tests/" not in normalized and not normalized.startswith("scripts/test_")


def main() -> int:
    args = parse_args()
    try:
        changes = collect_changed_paths(base=args.base, staged=args.staged, pathspecs=args.paths)
    except RuntimeError as exc:
        if args.json:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
            return 2
        print(f"docs_drift_check error: {exc}", file=sys.stderr)
        return 2

    if not changes:
        if args.json:
            print(json.dumps({"status": "ok", "message": "no changes found", "failures": []}, ensure_ascii=False, indent=2))
            return 0
        print("docs_drift_check: no changes found.")
        return 0

    code_changes = sorted(change.path for change in changes if needs_documentation(change.path))
    docs_changed = any(is_documentation_artifact(change.path) for change in changes)
    if code_changes and not docs_changed:
        message = "Code changes require at least one documentation or CODEMAP update: " + ", ".join(code_changes)
        if args.json:
            print(json.dumps({"status": "failed", "failures": [message]}, ensure_ascii=False, indent=2))
            return 1
        print(f"docs_drift_check failed: {message}")
        return 1

    message = "documentation coverage present" if code_changes else "no documentation-sensitive changes detected"
    if args.json:
        print(json.dumps({"status": "ok", "message": message, "failures": []}, ensure_ascii=False, indent=2))
        return 0
    print(f"docs_drift_check: {message}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
