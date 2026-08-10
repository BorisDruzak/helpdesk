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
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from importlib import import_module
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

try:  # Supports both ``python scripts/...`` and package imports in pytest.
    from scripts.registry_retirement_manifest import (
        RETIREMENT_MANIFEST,
        current_target_foreign_key_edges,
        manifest_validation_errors,
    )
except ModuleNotFoundError:  # pragma: no cover - depends on Python's script path setup.
    from registry_retirement_manifest import (  # type: ignore[no-redef]
        RETIREMENT_MANIFEST,
        current_target_foreign_key_edges,
        manifest_validation_errors,
    )


EVIDENCE_RELATIVE_PATH = Path("artifacts") / "registry-retirement-evidence.json"
LOCAL_RUNTIME_PATHS = (
    Path("server/registry"),
    Path("server/app/repos/registry_repo.py"),
    Path("server/app/repos/registration_repo.py"),
    Path("server/web_api/registry_handlers.py"),
    Path("server/registry_adapter/local.py"),
)
LOCAL_MODEL_PREFIXES = ("Registry", "DeviceRegistration", "DeviceAccount", "DeviceBrowser")
EVIDENCE_SCHEMA = "pc_client.registry_retirement_evidence.v1"
IMMUTABLE_ID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE)
REVISION_PATTERN = re.compile(r"^[0-9a-f]{7,64}$", re.IGNORECASE)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
MAX_EVIDENCE_AGE = timedelta(hours=24)
MAX_FUTURE_EVIDENCE_SKEW = timedelta(minutes=5)
AttestationVerifier = Callable[[bytes, str, str, str], bool]
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
    )


def _find_local_consumers(workspace: Path) -> tuple[str, ...]:
    matches: list[str] = []
    for path in _relative_python_paths(workspace):
        relative = path.relative_to(workspace).as_posix()
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
            if any(
                alias.name == "registry"
                or alias.name.startswith("registry.")
                or alias.name == "registry_adapter.local"
                or alias.name == "app.repos.registry_repo"
                or alias.name == "app.repos.registration_repo"
                for alias in node.names
            ):
                return True
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        if (
            module == "registry"
            or module.startswith("registry.")
            or module in {"app.repos.registry_repo", "app.repos.registration_repo", "registry_adapter.local"}
        ):
            return True
        if module == "registry_adapter" and any(alias.name == "LocalRegistryAdapter" for alias in node.names):
            return True
        if module == "app.repos" and any(
            alias.name in {"RegistryRepo", "RegistrationRepo"} for alias in node.names
        ):
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


def _is_immutable_id(value: object) -> bool:
    return isinstance(value, str) and bool(IMMUTABLE_ID_PATTERN.fullmatch(value))


def _is_timestamp(value: object) -> bool:
    return _parse_timestamp(value) is not None


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _matches_evidence_context(component: object, *, environment: object, revision: object) -> bool:
    return (
        isinstance(component, dict)
        and component.get("environment") == environment
        and component.get("revision") == revision
    )


def attestable_evidence_payload(evidence: dict[str, Any]) -> bytes:
    """Return canonical signed bytes excluding the detached attestation envelope."""

    signed = {key: value for key, value in evidence.items() if key != "attestation"}
    return json.dumps(
        signed,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def current_foreign_key_graph_signature() -> str:
    """Hash the reviewed current target-table FK graph without opening PostgreSQL."""

    lines = (f"{child}->{parent}" for child, parent in current_target_foreign_key_edges())
    canonical_graph = "registry-retirement-target-fks.v1\n" + "\n".join(lines) + "\n"
    return sha256(canonical_graph.encode("utf-8")).hexdigest()


def _valid_evidence_envelope(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("schema") == EVIDENCE_SCHEMA
        and isinstance(evidence.get("environment"), str)
        and bool(str(evidence.get("environment")).strip())
        and isinstance(evidence.get("revision"), str)
        and bool(REVISION_PATTERN.fullmatch(str(evidence.get("revision"))))
        and _is_timestamp(evidence.get("attested_at"))
    )


def _valid_backup_restore_evidence(evidence: dict[str, Any]) -> bool:
    backup = evidence.get("backup")
    restore = evidence.get("restore_drill")
    catalog = evidence.get("catalog")
    environment = evidence.get("environment")
    revision = evidence.get("revision")
    if not _valid_evidence_envelope(evidence):
        return False
    return (
        isinstance(backup, dict)
        and _matches_evidence_context(backup, environment=environment, revision=revision)
        and _is_immutable_id(backup.get("artifact_id"))
        and isinstance(backup.get("sha256"), str)
        and bool(SHA256_PATTERN.fullmatch(backup["sha256"]))
        and _is_timestamp(backup.get("created_at"))
        and isinstance(restore, dict)
        and _matches_evidence_context(restore, environment=environment, revision=revision)
        and restore.get("passed") is True
        and _is_immutable_id(restore.get("drill_id"))
        and _is_immutable_id(restore.get("clone_id"))
        and restore.get("backup_artifact_id") == backup.get("artifact_id")
        and restore.get("backup_sha256") == backup.get("sha256")
        and _is_timestamp(restore.get("completed_at"))
        and isinstance(catalog, dict)
        and _matches_evidence_context(catalog, environment=environment, revision=revision)
        and _is_immutable_id(catalog.get("catalog_id"))
        and catalog.get("clone_id") == restore.get("clone_id")
        and catalog.get("backup_artifact_id") == backup.get("artifact_id")
        and _is_timestamp(catalog.get("captured_at"))
    )


def _valid_maintenance_evidence(evidence: dict[str, Any]) -> bool:
    maintenance = evidence.get("maintenance")
    environment = evidence.get("environment")
    revision = evidence.get("revision")
    return (
        isinstance(maintenance, dict)
        and _matches_evidence_context(maintenance, environment=environment, revision=revision)
        and _is_immutable_id(maintenance.get("plan_id"))
        and maintenance.get("approved") is True
        and maintenance.get("writers_stopped") is True
        and isinstance(maintenance.get("advisory_lock_key"), str)
        and bool(maintenance["advisory_lock_key"])
        and _is_timestamp(maintenance.get("approved_at"))
    )


def _valid_external_acceptance(evidence: dict[str, Any]) -> bool:
    acceptance = evidence.get("external_command_acceptance")
    environment = evidence.get("environment")
    revision = evidence.get("revision")
    if (
        not isinstance(acceptance, dict)
        or not _matches_evidence_context(acceptance, environment=environment, revision=revision)
        or not _is_immutable_id(acceptance.get("acceptance_id"))
        or not _is_timestamp(acceptance.get("accepted_at"))
        or acceptance.get("accepted") is not True
    ):
        return False
    operations = acceptance.get("operations")
    return isinstance(operations, list) and EVIDENCE_OPERATIONS <= {str(item) for item in operations}


def _valid_row_count_evidence(evidence: dict[str, Any]) -> bool:
    catalog = evidence.get("catalog")
    if not isinstance(catalog, dict):
        return False
    counts = catalog.get("table_counts")
    return (
        isinstance(counts, dict)
        and set(counts) == RETIREMENT_MANIFEST.target_tables
        and all(isinstance(count, int) and not isinstance(count, bool) and count >= 0 for count in counts.values())
        and catalog.get("foreign_key_signature") == current_foreign_key_graph_signature()
    )


def _evidence_timestamps(evidence: dict[str, Any]) -> dict[str, datetime] | None:
    backup = evidence.get("backup")
    restore = evidence.get("restore_drill")
    catalog = evidence.get("catalog")
    maintenance = evidence.get("maintenance")
    acceptance = evidence.get("external_command_acceptance")
    components = (
        ("external_acceptance", acceptance, "accepted_at"),
        ("backup", backup, "created_at"),
        ("restore", restore, "completed_at"),
        ("catalog", catalog, "captured_at"),
        ("maintenance", maintenance, "approved_at"),
        ("attestation", evidence, "attested_at"),
    )
    timestamps: dict[str, datetime] = {}
    for name, component, field in components:
        if not isinstance(component, dict):
            return None
        timestamp = _parse_timestamp(component.get(field))
        if timestamp is None:
            return None
        timestamps[name] = timestamp
    return timestamps


def _evidence_time_blocker(evidence: dict[str, Any], *, now: datetime) -> PreflightBlocker | None:
    timestamps = _evidence_timestamps(evidence)
    if timestamps is None:
        return PreflightBlocker(
            "retirement_evidence_timeline_invalid",
            "every signed evidence stage requires an offset-aware UTC timestamp",
        )
    if any(timestamp > now + MAX_FUTURE_EVIDENCE_SKEW for timestamp in timestamps.values()):
        return PreflightBlocker(
            "retirement_evidence_timestamp_in_future",
            "signed evidence timestamps may not exceed the bounded future clock-skew allowance",
        )
    stale_stages = tuple(
        name for name, timestamp in timestamps.items() if now - timestamp > MAX_EVIDENCE_AGE
    )
    if stale_stages:
        return PreflightBlocker(
            "retirement_evidence_replayed_or_stale",
            "signed evidence stage(s) exceed the bounded freshness window: " + ", ".join(stale_stages),
        )
    attested_at = timestamps["attestation"]
    if not (
        timestamps["backup"]
        < timestamps["restore"]
        < timestamps["catalog"]
        < timestamps["maintenance"]
        < timestamps["attestation"]
    ) or timestamps["external_acceptance"] > attested_at:
        return PreflightBlocker(
            "retirement_evidence_timeline_invalid",
            "backup, restore, catalog, maintenance and attestation must be strictly chronological",
        )
    return None


def workspace_git_revision(workspace: Path) -> str | None:
    """Return the checked-out commit only when the workspace is immutable/clean."""

    try:
        status = subprocess.run(
            ("git", "-C", str(workspace), "status", "--porcelain=v1", "--untracked-files=all"),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        completed = subprocess.run(
            ("git", "-C", str(workspace), "rev-parse", "--verify", "HEAD^{commit}"),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if status.returncode != 0 or status.stdout.strip():
        return None
    revision = completed.stdout.strip().lower() if completed.returncode == 0 else ""
    return revision if len(revision) == 40 and bool(REVISION_PATTERN.fullmatch(revision)) else None


def _trusted_attestation(
    evidence: dict[str, Any],
    attestation_verifier: AttestationVerifier | None,
) -> bool:
    attestation = evidence.get("attestation")
    if (
        attestation_verifier is None
        or not isinstance(attestation, dict)
        or not isinstance(attestation.get("algorithm"), str)
        or not attestation.get("algorithm")
        or not isinstance(attestation.get("key_id"), str)
        or not attestation.get("key_id")
        or not isinstance(attestation.get("signature"), str)
        or not attestation.get("signature")
    ):
        return False
    try:
        return bool(
            attestation_verifier(
                attestable_evidence_payload(evidence),
                attestation["algorithm"],
                attestation["key_id"],
                attestation["signature"],
            )
        )
    except Exception:
        return False


def _local_registry_configuration_detail(workspace: Path) -> str | None:
    configured_mode = (os.getenv("REGISTRY_PORT_MODE") or "").strip().lower()
    if configured_mode == "local":
        return "REGISTRY_PORT_MODE environment resolves to local"
    config_path = workspace / "server" / "config.py"
    if not config_path.is_file():
        return None
    try:
        tree = ast.parse(config_path.read_text(encoding="utf-8", errors="replace"), filename=str(config_path))
    except SyntaxError:
        return "server/config.py is syntax-invalid and cannot prove a non-local Registry mode"
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        if not any(isinstance(target, ast.Name) and target.id == "REGISTRY_PORT_MODE" for target in targets):
            continue
        if any(isinstance(value, ast.Constant) and value.value == "local" for value in ast.walk(node)):
            return "server/config.py resolves REGISTRY_PORT_MODE to local"
    return None


def load_attestation_verifier(specification: str) -> AttestationVerifier:
    """Load an operator-selected trusted public-key/KMS verifier, never a key from evidence."""

    module_name, separator, attribute_name = specification.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("attestation verifier must use module:function syntax")
    verifier = getattr(import_module(module_name), attribute_name, None)
    if not callable(verifier):
        raise ValueError("configured attestation verifier is not callable")
    return verifier


def run_preflight(
    workspace: Path,
    *,
    attestation_verifier: AttestationVerifier | None = None,
    expected_environment: str | None = None,
    expected_revision: str | None = None,
    now: datetime | None = None,
) -> PreflightResult:
    """Inspect local code/evidence only and fail closed for every missing gate."""

    workspace = workspace.resolve()
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
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

    local_configuration = _local_registry_configuration_detail(workspace)
    if local_configuration:
        blockers.append(PreflightBlocker("local_registry_configuration_present", local_configuration))

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
                PreflightBlocker(
                    "retirement_evidence_attestation_missing_or_untrusted",
                    "a configured trusted public-key/KMS verifier must validate the canonical evidence signature",
                ),
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
        if not _trusted_attestation(evidence, attestation_verifier):
            blockers.append(
                PreflightBlocker(
                    "retirement_evidence_attestation_missing_or_untrusted",
                    "a configured trusted public-key/KMS verifier must validate the canonical evidence signature",
                )
            )
        time_blocker = _evidence_time_blocker(evidence, now=now)
        if time_blocker is not None:
            blockers.append(time_blocker)
        if expected_environment is not None and evidence.get("environment") != expected_environment:
            blockers.append(
                PreflightBlocker(
                    "retirement_evidence_environment_mismatch",
                    "signed evidence environment does not match the required release environment",
                )
            )
        if expected_revision is not None and evidence.get("revision") != expected_revision:
            blockers.append(
                PreflightBlocker(
                    "retirement_evidence_revision_mismatch",
                    "signed evidence revision does not match the immutable checked-out workspace revision",
                )
            )
    return PreflightResult(ready=not blockers, blockers=tuple(blockers))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true", help="Print the read-only status; never changes exit code for pending gates.")
    parser.add_argument("--require-ready", action="store_true", help="Return non-zero unless all non-destructive gates are proven.")
    parser.add_argument(
        "--expected-environment",
        help="Required with --require-ready; immutable release environment identifier that must exactly match signed evidence.",
    )
    parser.add_argument(
        "--attestation-verifier",
        metavar="MODULE:FUNCTION",
        help="Trusted public-key/KMS signature verifier; evidence never supplies executable verifier code or trust material.",
    )
    args = parser.parse_args(argv)
    if args.dry_run and args.require_ready:
        parser.error("--dry-run and --require-ready are mutually exclusive")
    if args.require_ready and not (args.expected_environment or "").strip():
        parser.error("--expected-environment is required with --require-ready")
    try:
        verifier = load_attestation_verifier(args.attestation_verifier) if args.attestation_verifier else None
    except (ImportError, AttributeError, ValueError) as exc:
        parser.error(f"invalid --attestation-verifier: {exc}")
    expected_revision = None
    if args.require_ready:
        expected_revision = workspace_git_revision(args.workspace)
        if expected_revision is None:
            parser.error("cannot derive immutable Git workspace revision for --require-ready")
    result = run_preflight(
        args.workspace,
        attestation_verifier=verifier,
        expected_environment=args.expected_environment.strip() if args.require_ready else None,
        expected_revision=expected_revision,
    )
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.require_ready and not result.ready else 0


if __name__ == "__main__":
    raise SystemExit(main())
