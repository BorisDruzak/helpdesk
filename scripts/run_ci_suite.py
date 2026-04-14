#!/usr/bin/env python3
"""Run the canonical self-hosted CI suite and store artifacts under artifacts/ci/<sha>/."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.ci_artifacts import DEFAULT_WORKSPACE, detect_commit, summary_path_for_commit
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.ci_artifacts import DEFAULT_WORKSPACE, detect_commit, summary_path_for_commit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--commit")
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_and_capture(command: list[str], *, cwd: Path, log_path: Path) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as handle:
        if completed.stdout:
            handle.write(completed.stdout)
        if completed.stderr:
            if completed.stdout:
                handle.write("\n")
            handle.write(completed.stderr)
    return {
        "command": command,
        "returncode": completed.returncode,
        "log": str(log_path),
    }


def main() -> None:
    args = parse_args()
    commit = detect_commit(args.workspace, args.commit)
    summary_path = summary_path_for_commit(args.workspace, commit)
    artifact_dir = summary_path.parent
    logs_dir = artifact_dir / "logs"
    started_at = now_iso()

    steps = [
        (
            "verify_workspace",
            [sys.executable, str(args.workspace / "scripts" / "verify_workspace.py")],
            logs_dir / "verify_workspace.log",
        ),
        (
            "server_pytest",
            [
                sys.executable,
                "-m",
                "pytest",
                "server/tests",
                "-m",
                "not manual",
                "--junitxml",
                str(artifact_dir / "junit-server.xml"),
            ],
            logs_dir / "server_pytest.log",
        ),
        (
            "pc_agent_pytest",
            [
                sys.executable,
                "-m",
                "pytest",
                "pc_agent/tests",
                "-m",
                "not manual",
                "--junitxml",
                str(artifact_dir / "junit-pc-agent.xml"),
            ],
            logs_dir / "pc_agent_pytest.log",
        ),
    ]

    results: list[dict[str, object]] = []
    status = "green"
    for step_name, command, log_path in steps:
        result = run_and_capture(command, cwd=args.workspace, log_path=log_path)
        result["name"] = step_name
        results.append(result)
        if result["returncode"] != 0:
            status = "red"

    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "commit": commit,
        "status": status,
        "started_at": started_at,
        "finished_at": now_iso(),
        "steps": results,
    }
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    if status != "green":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
