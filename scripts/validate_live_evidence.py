#!/usr/bin/env python3
"""Validate pc_client live evidence manifest v2 files."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "pc_client.live_evidence.v2"
RUN_STATUSES = {"pass", "fail", "blocked"}
CHECK_STATUSES = {"pass", "fail", "blocked", "skipped"}
REDACTION_STATUSES = {"redacted", "not_applicable", "none"}
PREFLIGHT_STATUSES = {"pass", "fail", "blocked"}
REQUIRED_TOP_LEVEL = (
    "schema",
    "run_id",
    "scenario",
    "status",
    "commit",
    "deployed_commit",
    "environment",
    "started_at",
    "finished_at",
    "entities",
    "preflight",
    "checks",
    "artifacts",
    "contamination",
    "cleanup",
)
REQUIRED_CHECK_FIELDS = (
    "layer",
    "surface",
    "expected",
    "actual",
    "status",
    "artifact_path",
    "query_request_digest",
    "timestamp",
    "redaction_status",
)
REQUIRED_ARTIFACT_FIELDS = ("kind", "path", "description", "redaction_status")
REQUIRED_PREFLIGHT_FIELDS = (
    "branch",
    "local_commit",
    "deployed_commit",
    "expected_schema_head",
    "actual_schema_head",
    "schema_status",
    "service_health",
    "checked_at",
)


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_timestamp(value: Any, *, field: str, errors: list[str]) -> datetime | None:
    if not _non_empty(value):
        errors.append(f"{field} is required")
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} must be ISO-8601")
        return None


def _require_mapping(value: Any, *, field: str, errors: list[str]) -> Mapping[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return None
    return value


def _validate_check(item: Any, *, index: int, manifest_dir: Path, errors: list[str]) -> None:
    check = _require_mapping(item, field=f"checks[{index}]", errors=errors)
    if check is None:
        return
    for field in REQUIRED_CHECK_FIELDS:
        if field not in check or not _non_empty(check[field]):
            errors.append(f"checks[{index}].{field} is required")
    status = str(check.get("status") or "")
    if status and status not in CHECK_STATUSES:
        errors.append(f"checks[{index}].status must be one of {sorted(CHECK_STATUSES)}")
    redaction_status = str(check.get("redaction_status") or "")
    if redaction_status and redaction_status not in REDACTION_STATUSES:
        errors.append(f"checks[{index}].redaction_status must be one of {sorted(REDACTION_STATUSES)}")
    _parse_timestamp(check.get("timestamp"), field=f"checks[{index}].timestamp", errors=errors)
    artifact_path = check.get("artifact_path")
    if _non_empty(artifact_path) and not (manifest_dir / str(artifact_path)).exists():
        errors.append(f"checks[{index}].artifact_path does not exist: {artifact_path}")


def _validate_artifact(item: Any, *, index: int, manifest_dir: Path, errors: list[str]) -> None:
    artifact = _require_mapping(item, field=f"artifacts[{index}]", errors=errors)
    if artifact is None:
        return
    for field in REQUIRED_ARTIFACT_FIELDS:
        if field not in artifact or not _non_empty(artifact[field]):
            errors.append(f"artifacts[{index}].{field} is required")
    redaction_status = str(artifact.get("redaction_status") or "")
    if redaction_status and redaction_status not in REDACTION_STATUSES:
        errors.append(f"artifacts[{index}].redaction_status must be one of {sorted(REDACTION_STATUSES)}")
    artifact_path = artifact.get("path")
    if _non_empty(artifact_path) and not (manifest_dir / str(artifact_path)).exists():
        errors.append(f"artifacts[{index}].path does not exist: {artifact_path}")


def _validate_preflight(preflight_value: Any, *, manifest: Mapping[str, Any], errors: list[str]) -> None:
    preflight = _require_mapping(preflight_value, field="preflight", errors=errors)
    if preflight is None:
        return
    for field in REQUIRED_PREFLIGHT_FIELDS:
        if field not in preflight or not _non_empty(preflight[field]):
            errors.append(f"preflight.{field} is required")
    local_commit = str(preflight.get("local_commit") or "").strip()
    deployed_commit = str(preflight.get("deployed_commit") or "").strip()
    manifest_commit = str(manifest.get("commit") or "").strip()
    manifest_deployed_commit = str(manifest.get("deployed_commit") or "").strip()
    if local_commit and manifest_commit and local_commit != manifest_commit:
        errors.append("preflight.local_commit must match commit")
    if deployed_commit and manifest_deployed_commit and deployed_commit != manifest_deployed_commit:
        errors.append("preflight.deployed_commit must match deployed_commit")
    if local_commit and deployed_commit and local_commit != deployed_commit:
        errors.append("commit and deployed_commit must match")
    expected_schema_head = str(preflight.get("expected_schema_head") or "").strip()
    actual_schema_head = str(preflight.get("actual_schema_head") or "").strip()
    if expected_schema_head and actual_schema_head and actual_schema_head != expected_schema_head:
        errors.append("preflight actual_schema_head must match expected_schema_head")
    schema_status = str(preflight.get("schema_status") or "")
    if schema_status and schema_status not in PREFLIGHT_STATUSES:
        errors.append(f"preflight.schema_status must be one of {sorted(PREFLIGHT_STATUSES)}")
    elif schema_status and schema_status != "pass":
        errors.append("preflight.schema_status must be pass")
    service_health = str(preflight.get("service_health") or "")
    if service_health and service_health not in PREFLIGHT_STATUSES:
        errors.append(f"preflight.service_health must be one of {sorted(PREFLIGHT_STATUSES)}")
    elif service_health and service_health != "pass":
        errors.append("preflight.service_health must be pass")
    _parse_timestamp(preflight.get("checked_at"), field="preflight.checked_at", errors=errors)


def validate_manifest(manifest: Mapping[str, Any], *, manifest_dir: Path) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_TOP_LEVEL:
        if field not in manifest:
            errors.append(f"{field} is required")
    if manifest.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    for field in ("run_id", "scenario", "commit", "deployed_commit", "environment"):
        if not _non_empty(manifest.get(field)):
            errors.append(f"{field} is required")
    if _non_empty(manifest.get("commit")) and _non_empty(manifest.get("deployed_commit")):
        if str(manifest.get("commit")).strip() != str(manifest.get("deployed_commit")).strip():
            errors.append("commit and deployed_commit must match")
    status = str(manifest.get("status") or "")
    if status not in RUN_STATUSES:
        errors.append(f"status must be one of {sorted(RUN_STATUSES)}")
    started_at = _parse_timestamp(manifest.get("started_at"), field="started_at", errors=errors)
    finished_at = _parse_timestamp(manifest.get("finished_at"), field="finished_at", errors=errors)
    if started_at and finished_at and finished_at < started_at:
        errors.append("finished_at must not be earlier than started_at")

    entities = _require_mapping(manifest.get("entities"), field="entities", errors=errors)
    if entities is not None:
        trace_ids = entities.get("trace_ids")
        if not isinstance(trace_ids, list):
            errors.append("entities.trace_ids must be a list")

    _validate_preflight(manifest.get("preflight"), manifest=manifest, errors=errors)

    checks = manifest.get("checks")
    if not isinstance(checks, list):
        errors.append("checks must be a list")
    elif not checks:
        errors.append("checks must contain at least one item")
    else:
        for index, item in enumerate(checks):
            _validate_check(item, index=index, manifest_dir=manifest_dir, errors=errors)

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("artifacts must be a list")
    elif not artifacts:
        errors.append("artifacts must contain at least one item")
    else:
        for index, item in enumerate(artifacts):
            _validate_artifact(item, index=index, manifest_dir=manifest_dir, errors=errors)

    contamination = _require_mapping(manifest.get("contamination"), field="contamination", errors=errors)
    if contamination is not None and contamination.get("status") not in {"clean", "contaminated", "not_applicable"}:
        errors.append("contamination.status must be clean, contaminated, or not_applicable")
    cleanup = _require_mapping(manifest.get("cleanup"), field="cleanup", errors=errors)
    if cleanup is not None and cleanup.get("status") not in {"completed", "not_applicable"}:
        errors.append("cleanup.status must be completed or not_applicable")
    return errors


def load_manifest(path: Path) -> Mapping[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("manifest root must be an object")
    return data


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = load_manifest(args.manifest)
    errors = validate_manifest(manifest, manifest_dir=args.manifest.parent)
    status = "pass" if not errors else "fail"
    print(f"live evidence manifest validation: status={status} errors={len(errors)}")
    for error in errors:
        print(f"- {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
