#!/usr/bin/env python3
"""Preflight a frozen release candidate before full-gate deploy/release."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    from scripts.ci_artifacts import (
        DEFAULT_WORKSPACE,
        detect_commit,
        require_green_ci_artifact,
        require_webapp_bundle_artifact,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.ci_artifacts import (
        DEFAULT_WORKSPACE,
        detect_commit,
        require_green_ci_artifact,
        require_webapp_bundle_artifact,
    )


GENERATED_DIRTY_PREFIXES = ("artifacts/",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--commit")
    parser.add_argument(
        "--allow-local-dirty",
        action="store_true",
        help="Allow uncommitted local files. Full release still deploys committed Git state only.",
    )
    parser.add_argument(
        "--skip-webapp-bundle",
        action="store_true",
        help="Skip checking the webapp bundle artifact for the candidate commit.",
    )
    return parser.parse_args()


def git_status_short(workspace: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--short", "--untracked-files=normal"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line.rstrip() for line in completed.stdout.splitlines() if line.strip()]


def release_relevant_dirty_entries(entries: list[str]) -> list[str]:
    relevant: list[str] = []
    for entry in entries:
        path = entry[3:].strip() if len(entry) > 3 else entry.strip()
        normalized = path.replace("\\", "/")
        if any(normalized.startswith(prefix) for prefix in GENERATED_DIRTY_PREFIXES):
            continue
        relevant.append(entry)
    return relevant


def build_dirty_message(entries: list[str]) -> str:
    preview_limit = 20
    preview_lines = entries[:preview_limit]
    preview = "\n".join(f"  {line}" for line in preview_lines)
    if len(entries) > preview_limit:
        preview = f"{preview}\n  ... and {len(entries) - preview_limit} more"
    return (
        "Release candidate preflight found uncommitted local changes.\n"
        "Full CI and full gate are keyed to the committed HEAD only, so committing after "
        "green CI invalidates the artifact and forces another full run.\n"
        f"{preview}\n"
        "Commit/stash these changes before freezing the release candidate, or rerun with "
        "`--allow-local-dirty` only when you intentionally want to release the last committed state."
    )


def main() -> None:
    args = parse_args()
    workspace = args.workspace
    commit = detect_commit(workspace, args.commit)
    all_dirty_entries = git_status_short(workspace)
    dirty_entries = release_relevant_dirty_entries(all_dirty_entries)
    if dirty_entries and not args.allow_local_dirty:
        raise SystemExit(build_dirty_message(dirty_entries))

    print(f"[release-preflight] candidate_commit={commit}")
    if dirty_entries:
        print(
            "[release-preflight] WARNING: local workspace is dirty; full gate will validate "
            "and deploy only the committed candidate."
        )
    if all_dirty_entries and not dirty_entries:
        print("[release-preflight] generated/untracked artifacts are ignored for release-candidate dirtiness.")

    summary_path = require_green_ci_artifact(workspace, commit)
    print(f"[release-preflight] green_ci_artifact={summary_path}")

    if not args.skip_webapp_bundle:
        bundle_path = require_webapp_bundle_artifact(workspace, commit)
        print(f"[release-preflight] webapp_bundle={bundle_path}")

    print(
        "[release-preflight] OK: frozen release candidate is ready for full gate. "
        "Do not commit before `python scripts/release_server_to_remote.py --gate full`."
    )


if __name__ == "__main__":
    main()
