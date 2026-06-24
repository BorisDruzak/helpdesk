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
OBSERVER_DELTA_STATUSES = {"pass", "fail", "blocked", "incomplete"}
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
    "observer_delta",
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
REQUIRED_OBSERVER_DELTA_FIELDS = (
    "baseline_run_id",
    "scenario_run_id",
    "before",
    "after",
    "delta",
    "traces",
    "checker_status",
    "writer_status",
    "correlation_status",
    "status",
    "checked_at",
)
REQUIRED_OBSERVER_SNAPSHOT_FIELDS = ("active_refs", "suppressed_refs", "scan_status", "checked_at")
REQUIRED_OBSERVER_DELTA_RESULT_FIELDS = (
    "new_active_critical_high_error_refs",
    "unexpected_suppression_refs",
)
REQUIRED_OBSERVER_TRACE_FIELDS = (
    "required_trace_ids",
    "linked_trace_ids",
    "missing_required_trace_ids",
    "db_outcome",
    "trace_outcome",
    "consistency_status",
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


def _require_string_list(value: Any, *, field: str, errors: list[str]) -> list[str] | None:
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return None
    strings: list[str] = []
    for index, item in enumerate(value):
        if not _non_empty(item):
            errors.append(f"{field}[{index}] must be a non-empty string")
            continue
        strings.append(str(item).strip())
    return strings


def _validate_pass_status(value: Any, *, field: str, errors: list[str]) -> None:
    status = str(value or "")
    if not status:
        return
    if status not in OBSERVER_DELTA_STATUSES:
        errors.append(f"{field} must be one of {sorted(OBSERVER_DELTA_STATUSES)}")
    elif status != "pass":
        errors.append(f"{field} must be pass")


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


def _validate_observer_snapshot(value: Any, *, field: str, errors: list[str]) -> None:
    snapshot = _require_mapping(value, field=field, errors=errors)
    if snapshot is None:
        return
    for snapshot_field in REQUIRED_OBSERVER_SNAPSHOT_FIELDS:
        if snapshot_field not in snapshot:
            errors.append(f"{field}.{snapshot_field} is required")
    if "active_refs" in snapshot:
        _require_string_list(snapshot.get("active_refs"), field=f"{field}.active_refs", errors=errors)
    if "suppressed_refs" in snapshot:
        _require_string_list(snapshot.get("suppressed_refs"), field=f"{field}.suppressed_refs", errors=errors)
    _validate_pass_status(snapshot.get("scan_status"), field=f"{field}.scan_status", errors=errors)
    _parse_timestamp(snapshot.get("checked_at"), field=f"{field}.checked_at", errors=errors)


def _validate_observer_delta_result(value: Any, *, errors: list[str]) -> None:
    delta = _require_mapping(value, field="observer_delta.delta", errors=errors)
    if delta is None:
        return
    for field in REQUIRED_OBSERVER_DELTA_RESULT_FIELDS:
        if field not in delta:
            errors.append(f"observer_delta.delta.{field} is required")
    new_active_refs = None
    if "new_active_critical_high_error_refs" in delta:
        new_active_refs = _require_string_list(
            delta.get("new_active_critical_high_error_refs"),
            field="observer_delta.delta.new_active_critical_high_error_refs",
            errors=errors,
        )
    if new_active_refs:
        errors.append("observer_delta.delta.new_active_critical_high_error_refs must be empty")
    unexpected_suppression_refs = None
    if "unexpected_suppression_refs" in delta:
        unexpected_suppression_refs = _require_string_list(
            delta.get("unexpected_suppression_refs"),
            field="observer_delta.delta.unexpected_suppression_refs",
            errors=errors,
        )
    if unexpected_suppression_refs:
        errors.append("observer_delta.delta.unexpected_suppression_refs must be empty")


def _validate_observer_traces(value: Any, *, errors: list[str]) -> None:
    traces = _require_mapping(value, field="observer_delta.traces", errors=errors)
    if traces is None:
        return
    for field in REQUIRED_OBSERVER_TRACE_FIELDS:
        if field not in traces or (field in {"db_outcome", "trace_outcome"} and not _non_empty(traces[field])):
            errors.append(f"observer_delta.traces.{field} is required")
    required_trace_ids = None
    if "required_trace_ids" in traces:
        required_trace_ids = _require_string_list(
            traces.get("required_trace_ids"),
            field="observer_delta.traces.required_trace_ids",
            errors=errors,
        )
    linked_trace_ids = None
    if "linked_trace_ids" in traces:
        linked_trace_ids = _require_string_list(
            traces.get("linked_trace_ids"),
            field="observer_delta.traces.linked_trace_ids",
            errors=errors,
        )
    missing_required_trace_ids = None
    if "missing_required_trace_ids" in traces:
        missing_required_trace_ids = _require_string_list(
            traces.get("missing_required_trace_ids"),
            field="observer_delta.traces.missing_required_trace_ids",
            errors=errors,
        )
    if missing_required_trace_ids:
        errors.append("observer_delta.traces.missing_required_trace_ids must be empty")
    if required_trace_ids is not None and linked_trace_ids is not None:
        missing_linked = set(required_trace_ids) - set(linked_trace_ids)
        if missing_linked:
            errors.append("observer_delta.traces linked_trace_ids must include every required_trace_ids item")
    _validate_pass_status(
        traces.get("consistency_status"),
        field="observer_delta.traces.consistency_status",
        errors=errors,
    )


def _validate_observer_delta(observer_delta_value: Any, *, manifest: Mapping[str, Any], errors: list[str]) -> None:
    observer_delta = _require_mapping(observer_delta_value, field="observer_delta", errors=errors)
    if observer_delta is None:
        return
    for field in REQUIRED_OBSERVER_DELTA_FIELDS:
        if field not in observer_delta or (
            field
            in {
                "baseline_run_id",
                "scenario_run_id",
                "checker_status",
                "writer_status",
                "correlation_status",
                "status",
            }
            and not _non_empty(observer_delta[field])
        ):
            errors.append(f"observer_delta.{field} is required")

    baseline_run_id = str(observer_delta.get("baseline_run_id") or "").strip()
    scenario_run_id = str(observer_delta.get("scenario_run_id") or "").strip()
    manifest_run_id = str(manifest.get("run_id") or "").strip()
    if scenario_run_id and manifest_run_id and scenario_run_id != manifest_run_id:
        errors.append("observer_delta.scenario_run_id must match run_id")
    if baseline_run_id and scenario_run_id and baseline_run_id == scenario_run_id:
        errors.append("observer_delta.baseline_run_id must differ from scenario_run_id")

    _validate_observer_snapshot(observer_delta.get("before"), field="observer_delta.before", errors=errors)
    _validate_observer_snapshot(observer_delta.get("after"), field="observer_delta.after", errors=errors)
    _validate_observer_delta_result(observer_delta.get("delta"), errors=errors)
    _validate_observer_traces(observer_delta.get("traces"), errors=errors)
    for field in ("checker_status", "writer_status", "correlation_status", "status"):
        _validate_pass_status(observer_delta.get(field), field=f"observer_delta.{field}", errors=errors)
    _parse_timestamp(observer_delta.get("checked_at"), field="observer_delta.checked_at", errors=errors)


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
    _validate_observer_delta(manifest.get("observer_delta"), manifest=manifest, errors=errors)

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
