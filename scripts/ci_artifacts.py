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
SERVER_DB_GATE_LAYER_PREFIX = "server_pytest_db_"
SERVER_DB_GATE_LAYER_NAMES = {"server_pytest_agent_ws"}
SHARED_DB_FALLBACK_MARKERS = (
    "shared test DB fallback",
    "PC_CLIENT_ALLOW_SHARED_TEST_DB=1",
)


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


def _is_server_db_gate_step(step_name: str) -> bool:
    return step_name.startswith(SERVER_DB_GATE_LAYER_PREFIX) or step_name in SERVER_DB_GATE_LAYER_NAMES


def _log_path_from_step(summary_path: Path, step: dict[str, Any]) -> Path | None:
    raw_log = step.get("log")
    if not raw_log:
        return None
    log_path = Path(str(raw_log))
    if log_path.is_absolute():
        return log_path
    return summary_path.parent / log_path


def _log_contains_shared_db_fallback(log_path: Path) -> bool:
    if not log_path.exists():
        return False
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return any(marker in text for marker in SHARED_DB_FALLBACK_MARKERS)


def shared_db_fallback_logs(summary_path: Path, summary: dict[str, Any]) -> list[tuple[str, Path]]:
    offenders: list[tuple[str, Path]] = []
    raw_steps = summary.get("steps") or []
    if not isinstance(raw_steps, list):
        return offenders
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            continue
        step_name = str(raw_step.get("name") or "")
        if not _is_server_db_gate_step(step_name):
            continue
        log_path = _log_path_from_step(summary_path, raw_step)
        if log_path is not None and _log_contains_shared_db_fallback(log_path):
            offenders.append((step_name, log_path))
    return offenders


def _is_full_merge_gate_summary(summary: dict[str, Any]) -> bool:
    gate_mode = str(summary.get("gate_mode") or "").strip().lower()
    if gate_mode in {"affected", "selected"}:
        return False
    if summary.get("full_merge_gate_satisfied") is False:
        return False
    requested_layers = summary.get("requested_layers")
    if isinstance(requested_layers, list) and requested_layers:
        return False
    return True


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
    if not _is_full_merge_gate_summary(summary):
        gate_mode = str(summary.get("gate_mode") or "selected")
        effective_layers = summary.get("effective_layers") or summary.get("requested_layers") or []
        raise SystemExit(
            "Deploy/release requires a green full merge gate artifact. "
            f"{summary_path} reports gate_mode={gate_mode!r} and layers={effective_layers!r}.\n"
            "Affected-suite and --layer runs are fast PR evidence only. "
            "Run `python scripts/run_ci_suite.py` for the frozen commit before full release/deploy."
        )
    shared_db_logs = shared_db_fallback_logs(summary_path, summary)
    if shared_db_logs:
        offenders = "\n".join(f"  {step_name}: {log_path}" for step_name, log_path in shared_db_logs)
        raise SystemExit(
            "Green CI artifact used shared test DB fallback, which is not valid for full release gate.\n"
            f"{offenders}\n"
            "Set TEST_DATABASE_ADMIN_URL so DB/WS layers use isolated pc_support_test_<runid> databases, "
            "then rerun full CI for the frozen commit."
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
