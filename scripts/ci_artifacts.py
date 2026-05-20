#!/usr/bin/env python3
"""Helpers for self-hosted CI artifact discovery and validation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_WORKSPACE = Path(r"C:\Users\admin-2\CodexProjects\pc_client")
DEFAULT_ARTIFACTS_ROOT = Path("artifacts") / "ci"
DEFAULT_WEBAPP_BUNDLE_DIRNAME = "webapp-dist"
DEFAULT_WEBAPP_BUNDLE_ARCHIVE_NAME = "webapp-dist.tar.gz"


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


def webapp_bundle_dir_for_commit(workspace: Path, commit: str) -> Path:
    return workspace / DEFAULT_ARTIFACTS_ROOT / commit / DEFAULT_WEBAPP_BUNDLE_DIRNAME


def webapp_bundle_archive_for_commit(workspace: Path, commit: str) -> Path:
    return workspace / DEFAULT_ARTIFACTS_ROOT / commit / DEFAULT_WEBAPP_BUNDLE_ARCHIVE_NAME


def load_summary(summary_path: Path) -> dict[str, Any]:
    with summary_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require_green_ci_artifact(workspace: Path, commit: str) -> Path:
    summary_path = summary_path_for_commit(workspace, commit)
    if not summary_path.exists():
        raise SystemExit(
            "Green CI artifact is required before deploy/release. "
            f"Missing: {summary_path}\n"
            "Release workflow: use targeted tests and --gate quick while iterating; "
            "run `python scripts/run_ci_suite.py` only after the release candidate commit is frozen."
        )
    summary = load_summary(summary_path)
    artifact_commit = str(summary.get("commit", "")).strip()
    if artifact_commit != commit:
        raise SystemExit(
            "Deploy/release requires a green CI artifact for the exact target commit. "
            f"{summary_path} reports commit={artifact_commit!r}, expected {commit!r}.\n"
            "Do not commit after full CI and before full-gate release. "
            "If another commit is required, treat it as a new release candidate and run full CI again."
        )
    if str(summary.get("status", "")).lower() != "green":
        raise SystemExit(
            "Deploy/release requires a green CI artifact. "
            f"{summary_path} reports status={summary.get('status')!r}.\n"
            "Use --gate quick only for staging/live iteration; do not make a final release claim from quick gate."
        )
    return summary_path


def require_webapp_bundle_artifact(workspace: Path, commit: str) -> Path:
    archive_path = webapp_bundle_archive_for_commit(workspace, commit)
    if not archive_path.exists():
        raise SystemExit(
            "Release requires a built web bundle artifact. "
            f"Missing: {archive_path}"
        )
    return archive_path
