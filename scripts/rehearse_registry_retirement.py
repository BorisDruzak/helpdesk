#!/usr/bin/env python3
"""Read-only retirement preflight for the future PR-11 schema migration.

The command never connects to PostgreSQL, invokes Alembic, emits SQL, or
writes evidence.  It only makes missing proof and remaining local dependency
explicit.  ``--dry-run`` is intentionally informational; a caller preparing a
destructive migration must use ``--require-ready`` and receive a zero exit
status before proceeding.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

try:  # Supports both ``python scripts/...`` and package imports in pytest.
    from scripts.registry_retirement_manifest import RETIREMENT_MANIFEST, manifest_validation_errors
except ModuleNotFoundError:  # pragma: no cover - depends on Python's script path setup.
    from registry_retirement_manifest import RETIREMENT_MANIFEST, manifest_validation_errors


EVIDENCE_RELATIVE_PATH = Path("artifacts") / "registry-retirement-evidence.json"
LOCAL_RUNTIME_PATHS = (
    Path("server/registry"),
    Path("server/app/repos/registry_repo.py"),
    Path("server/web_api/registry_handlers.py"),
)
LOCAL_MODEL_PREFIXES = ("Registry", "DeviceRegistration", "DeviceAccount", "DeviceBrowser")
EVIDENCE_OPERATIONS = frozenset(
    {
        "login_eligibility",
        "registration_request",
        "registration_approve",
        "registration_reject",
        "binding_revoke",
        "account_session_create",
        "account_session_validate",
        "account_session_logout",
        "account_session_revoke",
        "browser_pairing_create",
        "browser_pairing_confirm",
        "browser_pairing_pickup",
        "other_account_approval",
    }
)


@dataclass(frozen=True)
class PreflightBlocker:
    code: str
    detail: str


@dataclass(frozen=True)
class PreflightResult:
    ready: bool
    blockers: tuple[PreflightBlocker, ...]

    @property
    def blocker_codes(self) -> tuple[str, ...]:
        return tuple(blocker.code for blocker in self.blockers)

    def as_dict(self) -> dict[str, Any]:
        return {"ready": self.ready, "blockers": [asdict(blocker) for blocker in self.blockers]}


def _relative_python_paths(workspace: Path) -> Iterable[Path]:
    server_root = workspace / "server"
    if not server_root.exists():
        return ()
    return (
        path
        for path in server_root.rglob("*.py")
        if "__pycache__" not in path.parts
        and "tests" not in path.parts
        and not path.name.startswith("test_")
        and Path("app/db/migrations") not in path.relative_to(workspace).parents
        and Path("registry_adapter") not in path.relative_to(server_root).parents
        and Path("domain_ports") not in path.relative_to(server_root).parents
    )


def _find_local_consumers(workspace: Path) -> tuple[str, ...]:
    matches: list[str] = []
    for path in _relative_python_paths(workspace):
        relative = path.relative_to(workspace).as_posix()
        if relative.startswith("server/registry/"):
            continue
        if _imports_local_registry(path):
            matches.append(relative)
    return tuple(sorted(matches))


def _imports_local_registry(path: Path) -> bool:
    """Identify imports structurally, including parenthesised import lists."""

    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except SyntaxError:
        # A syntax-broken consumer cannot prove the local boundary is clean.
        return True
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "registry" or alias.name.startswith("registry.") for alias in node.names):
                return True
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        if module == "registry" or module.startswith("registry.") or module == "app.repos.registry_repo":
            return True
        if module == "app.db.models" and any(alias.name.startswith(LOCAL_MODEL_PREFIXES) for alias in node.names):
            return True
    return False


def _load_evidence(workspace: Path) -> dict[str, Any] | None:
    path = workspace / EVIDENCE_RELATIVE_PATH
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _valid_backup_restore_evidence(evidence: dict[str, Any]) -> bool:
    backup = evidence.get("backup")
    restore = evidence.get("restore_drill")
    return (
        isinstance(backup, dict)
        and isinstance(backup.get("sha256"), str)
        and bool(re.fullmatch(r"[0-9a-fA-F]{64}", backup["sha256"]))
        and isinstance(restore, dict)
        and restore.get("passed") is True
        and isinstance(restore.get("clone_id"), str)
        and bool(restore["clone_id"])
    )


def _valid_maintenance_evidence(evidence: dict[str, Any]) -> bool:
    maintenance = evidence.get("maintenance")
    return (
        isinstance(maintenance, dict)
        and maintenance.get("approved") is True
        and maintenance.get("writers_stopped") is True
        and isinstance(maintenance.get("advisory_lock_key"), str)
        and bool(maintenance["advisory_lock_key"])
    )


def _valid_external_acceptance(evidence: dict[str, Any]) -> bool:
    acceptance = evidence.get("external_command_acceptance")
    if not isinstance(acceptance, dict) or acceptance.get("accepted") is not True:
        return False
    operations = acceptance.get("operations")
    return isinstance(operations, list) and EVIDENCE_OPERATIONS <= {str(item) for item in operations}


def _valid_row_count_evidence(evidence: dict[str, Any]) -> bool:
    counts = evidence.get("row_counts")
    return isinstance(counts, dict) and RETIREMENT_MANIFEST.target_tables <= set(counts)


def run_preflight(workspace: Path) -> PreflightResult:
    """Inspect local code/evidence only and fail closed for every missing gate."""

    workspace = workspace.resolve()
    blockers: list[PreflightBlocker] = []
    for error in manifest_validation_errors():
        blockers.append(PreflightBlocker("invalid_retirement_manifest", error))

    active_paths = tuple(
        path.relative_to(workspace).as_posix()
        for relative in LOCAL_RUNTIME_PATHS
        if (path := workspace / relative).exists()
    )
    if active_paths:
        blockers.append(PreflightBlocker("local_registry_runtime_present", ", ".join(active_paths)))

    consumers = _find_local_consumers(workspace)
    if consumers:
        blockers.append(PreflightBlocker("local_registry_consumers_present", ", ".join(consumers)))

    evidence = _load_evidence(workspace)
    if evidence is None:
        blockers.extend(
            (
                PreflightBlocker("external_command_acceptance_missing", "acceptance evidence file is missing or invalid"),
                PreflightBlocker("backup_restore_evidence_missing", "backup hash and successful isolated restore drill are required"),
                PreflightBlocker("maintenance_advisory_lock_plan_missing", "approved window, writers stop and advisory lock key are required"),
                PreflightBlocker("row_count_evidence_missing", "clone catalog/count evidence for every target table is required"),
            )
        )
    else:
        if not _valid_external_acceptance(evidence):
            blockers.append(PreflightBlocker("external_command_acceptance_missing", "all command/session/pairing operations need acceptance evidence"))
        if not _valid_backup_restore_evidence(evidence):
            blockers.append(PreflightBlocker("backup_restore_evidence_missing", "backup sha256 and passed isolated restore drill are required"))
        if not _valid_maintenance_evidence(evidence):
            blockers.append(PreflightBlocker("maintenance_advisory_lock_plan_missing", "approved window, writers stop and advisory lock key are required"))
        if not _valid_row_count_evidence(evidence):
            blockers.append(PreflightBlocker("row_count_evidence_missing", "every target table needs clone row-count evidence"))
    return PreflightResult(ready=not blockers, blockers=tuple(blockers))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true", help="Print the read-only status; never changes exit code for pending gates.")
    parser.add_argument("--require-ready", action="store_true", help="Return non-zero unless all non-destructive gates are proven.")
    args = parser.parse_args(argv)
    if args.dry_run and args.require_ready:
        parser.error("--dry-run and --require-ready are mutually exclusive")
    result = run_preflight(args.workspace)
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.require_ready and not result.ready else 0


if __name__ == "__main__":
    raise SystemExit(main())
