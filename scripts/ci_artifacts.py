#!/usr/bin/env python3
"""Helpers for self-hosted CI artifact discovery and validation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_WORKSPACE = Path(r"C:\Users\admin-2\CodexProjects\pc_client")
DEFAULT_ARTIFACTS_ROOT = Path("artifacts") / "ci"


def detect_commit(workspace: Path, commit: str | None = None) -> str:
    if commit:
        return commit
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def summary_path_for_commit(workspace: Path, commit: str) -> Path:
    return workspace / DEFAULT_ARTIFACTS_ROOT / commit / "summary.json"


def load_summary(summary_path: Path) -> dict[str, Any]:
    with summary_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require_green_ci_artifact(workspace: Path, commit: str) -> Path:
    summary_path = summary_path_for_commit(workspace, commit)
    if not summary_path.exists():
        raise SystemExit(
            "Green CI artifact is required before deploy/release. "
            f"Missing: {summary_path}"
        )
    summary = load_summary(summary_path)
    if str(summary.get("status", "")).lower() != "green":
        raise SystemExit(
            "Deploy/release requires a green CI artifact. "
            f"{summary_path} reports status={summary.get('status')!r}"
        )
    return summary_path
