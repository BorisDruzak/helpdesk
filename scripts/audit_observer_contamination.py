#!/usr/bin/env python3
"""Audit the Observer known-contamination manifest."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = Path("quality/observer_known_contamination.json")
AUDIT_SCHEMA = "pc_client.observer_known_contamination_audit.v1"
MANIFEST_SCHEMA = "pc_client.observer_known_contamination.v1"
ALLOWED_ENTITY_TYPES = {"device_outbox", "operation", "ticket", "device", "command", "dedupe_key"}
ALLOWED_STATUSES = {"active", "retired"}
ALLOWED_REVIEW_STATUSES = {"reviewed"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _issue(
    code: str,
    message: str,
    *,
    path: str | None = None,
    json_path: str | None = None,
    contamination_id: str | None = None,
) -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    if json_path:
        payload["json_path"] = json_path
    if contamination_id:
        payload["contamination_id"] = contamination_id
    return payload


def _load_json(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, [_issue("missing_manifest", f"manifest does not exist: {path}", path=str(path))]
    except (OSError, json.JSONDecodeError) as exc:
        return None, [_issue("invalid_manifest_json", f"{type(exc).__name__}: {exc}", path=str(path))]
    if not isinstance(payload, dict):
        return None, [_issue("invalid_manifest_root", "manifest root must be an object", path=str(path))]
    return payload, []


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _repo_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.replace("\\", "/").strip()
    if normalized.startswith("/") or ":" in normalized.split("/", 1)[0]:
        return None
    return Path(normalized)


def _audit_active_row(
    workspace: Path,
    row: Mapping[str, Any],
    *,
    manifest_path: Path,
    index: int,
    contamination_id: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    row_path = f"$.contaminations[{index}]"
    required_text_codes = {
        "source_phase": "contamination_missing_source_phase",
        "owner_zone": "contamination_missing_owner",
        "linked_issue": "contamination_missing_linked_issue",
        "entity_type": "contamination_missing_entity_type",
        "entity_id": "contamination_missing_entity_id",
        "suppression_scope": "contamination_missing_suppression_scope",
        "reason": "contamination_missing_reason",
        "created_at": "contamination_missing_created_at",
        "expires_at": "contamination_missing_expires_at",
        "review_status": "contamination_missing_review_status",
        "evidence_path": "contamination_missing_evidence_path",
    }
    for field, code in required_text_codes.items():
        if not _non_empty_text(row.get(field)):
            issues.append(
                _issue(
                    code,
                    f"active contamination must define {field}",
                    path=str(manifest_path),
                    json_path=f"{row_path}.{field}",
                    contamination_id=contamination_id,
                )
            )

    entity_type = str(row.get("entity_type") or "").strip()
    entity_id = str(row.get("entity_id") or "").strip()
    if entity_type and entity_type not in ALLOWED_ENTITY_TYPES:
        issues.append(
            _issue(
                "contamination_invalid_entity_type",
                f"entity_type must be one of {', '.join(sorted(ALLOWED_ENTITY_TYPES))}",
                path=str(manifest_path),
                json_path=f"{row_path}.entity_type",
                contamination_id=contamination_id,
            )
        )
    if entity_id in {"*", "all"} or entity_id.endswith(":*"):
        issues.append(
            _issue(
                "contamination_broad_scope",
                "active contamination must use exact entity scope, not wildcards",
                path=str(manifest_path),
                json_path=f"{row_path}.entity_id",
                contamination_id=contamination_id,
            )
        )
    if str(row.get("review_status") or "").strip() not in ALLOWED_REVIEW_STATUSES:
        issues.append(
            _issue(
                "contamination_not_reviewed",
                "active contamination must have review_status=reviewed",
                path=str(manifest_path),
                json_path=f"{row_path}.review_status",
                contamination_id=contamination_id,
            )
        )
    created_at = _parse_datetime(row.get("created_at"))
    if row.get("created_at") and created_at is None:
        issues.append(
            _issue(
                "contamination_invalid_created_at",
                "created_at must be ISO-8601 datetime",
                path=str(manifest_path),
                json_path=f"{row_path}.created_at",
                contamination_id=contamination_id,
            )
        )
    expires_at = _parse_datetime(row.get("expires_at"))
    if row.get("expires_at") and expires_at is None:
        issues.append(
            _issue(
                "contamination_invalid_expires_at",
                "expires_at must be ISO-8601 datetime",
                path=str(manifest_path),
                json_path=f"{row_path}.expires_at",
                contamination_id=contamination_id,
            )
        )
    if expires_at is not None and expires_at <= datetime.now(timezone.utc):
        issues.append(
            _issue(
                "contamination_expired",
                "active contamination is expired and must be reviewed or retired",
                path=str(manifest_path),
                json_path=f"{row_path}.expires_at",
                contamination_id=contamination_id,
            )
        )
    evidence_path = _repo_path(row.get("evidence_path"))
    if evidence_path is None:
        issues.append(
            _issue(
                "invalid_evidence_path",
                "evidence_path must be a relative repository path",
                path=str(manifest_path),
                json_path=f"{row_path}.evidence_path",
                contamination_id=contamination_id,
            )
        )
    elif not (workspace / evidence_path).exists():
        issues.append(
            _issue(
                "missing_evidence_path",
                f"evidence_path does not exist: {evidence_path}",
                path=str(manifest_path),
                json_path=f"{row_path}.evidence_path",
                contamination_id=contamination_id,
            )
        )
    return issues


def audit_observer_contamination(workspace: Path, *, manifest_path: Path | None = None) -> dict[str, Any]:
    workspace = workspace.resolve()
    manifest = manifest_path or workspace / DEFAULT_MANIFEST
    if not manifest.is_absolute():
        manifest = workspace / manifest

    payload, issues = _load_json(manifest)
    contamination_count = 0
    active_count = 0
    seen_ids: set[str] = set()
    seen_scopes: set[tuple[str, str, str, str]] = set()

    if payload is None:
        return {
            "schema": AUDIT_SCHEMA,
            "manifest_path": str(manifest),
            "status": "fail",
            "contamination_count": contamination_count,
            "active_count": active_count,
            "issues": issues,
        }

    if payload.get("schema") != MANIFEST_SCHEMA:
        issues.append(
            _issue(
                "manifest_schema_validation",
                f"manifest schema must be {MANIFEST_SCHEMA}",
                path=str(manifest),
                json_path="$.schema",
            )
        )

    raw_rows = payload.get("contaminations")
    rows = raw_rows if isinstance(raw_rows, list) else []
    if not isinstance(raw_rows, list):
        issues.append(
            _issue(
                "manifest_schema_validation",
                "manifest contaminations must be an array",
                path=str(manifest),
                json_path="$.contaminations",
            )
        )

    for index, raw_row in enumerate(rows):
        if not isinstance(raw_row, Mapping):
            issues.append(
                _issue(
                    "invalid_contamination_record",
                    "contamination record must be an object",
                    path=str(manifest),
                    json_path=f"$.contaminations[{index}]",
                )
            )
            continue
        contamination_count += 1
        row_path = f"$.contaminations[{index}]"
        contamination_id = str(raw_row.get("id") or "").strip()
        if not contamination_id:
            issues.append(
                _issue(
                    "contamination_missing_id",
                    "contamination must define id",
                    path=str(manifest),
                    json_path=f"{row_path}.id",
                )
            )
        elif contamination_id in seen_ids:
            issues.append(
                _issue(
                    "duplicate_contamination_id",
                    f"duplicate contamination id: {contamination_id}",
                    path=str(manifest),
                    json_path=f"{row_path}.id",
                    contamination_id=contamination_id,
                )
            )
        seen_ids.add(contamination_id)

        status = str(raw_row.get("status") or "").strip()
        if status not in ALLOWED_STATUSES:
            issues.append(
                _issue(
                    "contamination_invalid_status",
                    f"status must be one of {', '.join(sorted(ALLOWED_STATUSES))}",
                    path=str(manifest),
                    json_path=f"{row_path}.status",
                    contamination_id=contamination_id or None,
                )
            )
        scope_key = (
            str(raw_row.get("source_phase") or "").strip(),
            str(raw_row.get("entity_type") or "").strip(),
            str(raw_row.get("entity_id") or "").strip(),
            str(raw_row.get("suppression_scope") or "").strip(),
        )
        if all(scope_key):
            if scope_key in seen_scopes:
                issues.append(
                    _issue(
                        "duplicate_contamination_scope",
                        "duplicate source/entity/scope contamination",
                        path=str(manifest),
                        json_path=row_path,
                        contamination_id=contamination_id or None,
                    )
                )
            seen_scopes.add(scope_key)

        if status == "active":
            active_count += 1
            issues.extend(
                _audit_active_row(
                    workspace,
                    raw_row,
                    manifest_path=manifest,
                    index=index,
                    contamination_id=contamination_id,
                )
            )

    return {
        "schema": AUDIT_SCHEMA,
        "manifest_path": str(manifest),
        "status": "ok" if not issues else "fail",
        "contamination_count": contamination_count,
        "active_count": active_count,
        "issues": issues,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = audit_observer_contamination(args.workspace, manifest_path=args.manifest)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict and report["issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
