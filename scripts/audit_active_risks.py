#!/usr/bin/env python3
"""Audit the machine-readable active-risk registry."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY = Path("quality/active_risks.json")
AUDIT_SCHEMA = "pc_client.active_risk_audit.v1"
REGISTRY_SCHEMA = "pc_client.active_risks.v1"

REQUIRED_ACTIVE_ARCHIVE_SOURCE_IDS = {
    "archive.1.1.outbox_ack",
    "archive.1.2.command_idempotency",
    "archive.1.3.scheduler_rpc",
    "archive.1.4.consent_orchestrator",
    "archive.1.5.module_manager_handshake",
    "archive.2.2.device_outbox_dispatch",
    "archive.2.3.sync_run_tool_wait",
    "archive.2.4.run_tool_entry_paths",
    "archive.3.3.server_public_base_url",
}

ALLOWED_STATUSES = {"active", "mitigated", "accepted", "retired"}
ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3"}
RISK_ID_RE = re.compile(r"^TD-\d{3}$")
TEST_NODE_RE_TEMPLATE = r"(^|\n)(async\s+def|def)\s+{node}\s*\("

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _issue(
    code: str,
    message: str,
    *,
    risk_id: str | None = None,
    path: str | None = None,
    json_path: str | None = None,
) -> dict[str, str]:
    payload = {"code": code, "message": message}
    if risk_id:
        payload["risk_id"] = risk_id
    if path:
        payload["path"] = path
    if json_path:
        payload["json_path"] = json_path
    return payload


def _load_json(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, [_issue("missing_json_file", f"JSON file does not exist: {path}", path=str(path))]
    except (OSError, json.JSONDecodeError) as exc:
        return None, [_issue("invalid_json_file", f"{type(exc).__name__}: {exc}", path=str(path))]
    if not isinstance(payload, dict):
        return None, [_issue("invalid_json_root", "JSON root must be an object", path=str(path))]
    return payload, []


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _repo_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.replace("\\", "/").strip()
    if normalized.startswith("/") or ":" in normalized.split("/", 1)[0]:
        return None
    return Path(normalized)


def _test_ref_path(ref: str) -> Path:
    return Path(ref.split("::", 1)[0].replace("\\", "/"))


def _test_ref_node(ref: str) -> str | None:
    if "::" not in ref:
        return None
    return ref.rsplit("::", 1)[-1].strip() or None


def _node_exists(path: Path, node: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8-sig")
    pattern = TEST_NODE_RE_TEMPLATE.format(node=re.escape(node))
    return bool(re.search(pattern, text))


def _audit_path_ref(
    workspace: Path,
    ref: Any,
    *,
    code: str,
    risk_id: str,
    registry_path: Path,
    json_path: str,
) -> list[dict[str, str]]:
    path = _repo_path(ref)
    if path is None:
        return [
            _issue(
                "invalid_path_ref",
                f"path ref must be a relative repository path: {ref}",
                risk_id=risk_id,
                path=str(registry_path),
                json_path=json_path,
            )
        ]
    if not (workspace / path).exists():
        return [
            _issue(
                code,
                f"path ref does not exist: {path}",
                risk_id=risk_id,
                path=str(registry_path),
                json_path=json_path,
            )
        ]
    return []


def _audit_test_ref(
    workspace: Path,
    ref: str,
    *,
    risk_id: str,
    registry_path: Path,
    json_path: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    ref_path = _test_ref_path(ref)
    absolute = workspace / ref_path
    if not absolute.is_file():
        return [
            _issue(
                "missing_test_ref",
                f"test ref file does not exist: {ref}",
                risk_id=risk_id,
                path=str(registry_path),
                json_path=json_path,
            )
        ]
    node = _test_ref_node(ref)
    if node and not _node_exists(absolute, node):
        issues.append(
            _issue(
                "missing_test_node",
                f"test ref node does not exist: {ref}",
                risk_id=risk_id,
                path=str(registry_path),
                json_path=json_path,
            )
        )
    return issues


def _audit_acceptance(
    criteria: list[Any],
    *,
    risk_id: str,
    registry_path: Path,
    json_path: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not criteria:
        return [
            _issue(
                "active_risk_missing_acceptance",
                "active risk must define measurable acceptance criteria",
                risk_id=risk_id,
                path=str(registry_path),
                json_path=json_path,
            )
        ]
    for index, criterion in enumerate(criteria):
        if not isinstance(criterion, Mapping):
            issues.append(
                _issue(
                    "invalid_acceptance_criterion",
                    "acceptance criterion must be an object",
                    risk_id=risk_id,
                    path=str(registry_path),
                    json_path=f"{json_path}[{index}]",
                )
            )
            continue
        if not _non_empty_text(criterion.get("metric")) or not _non_empty_text(criterion.get("target")):
            issues.append(
                _issue(
                    "invalid_acceptance_criterion",
                    "acceptance criterion must include metric and target",
                    risk_id=risk_id,
                    path=str(registry_path),
                    json_path=f"{json_path}[{index}]",
                )
            )
    return issues


def _audit_linked_tests(
    workspace: Path,
    linked_tests: list[Any],
    *,
    risk_id: str,
    registry_path: Path,
    json_path: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not linked_tests:
        return [
            _issue(
                "active_risk_missing_linked_tests",
                "active risk must link at least one test",
                risk_id=risk_id,
                path=str(registry_path),
                json_path=json_path,
            )
        ]
    for index, test_ref in enumerate(linked_tests):
        if not isinstance(test_ref, Mapping) or not _non_empty_text(test_ref.get("ref")):
            issues.append(
                _issue(
                    "invalid_linked_test",
                    "linked test must be an object with ref",
                    risk_id=risk_id,
                    path=str(registry_path),
                    json_path=f"{json_path}[{index}]",
                )
            )
            continue
        issues.extend(
            _audit_test_ref(
                workspace,
                str(test_ref["ref"]),
                risk_id=risk_id,
                registry_path=registry_path,
                json_path=f"{json_path}[{index}].ref",
            )
        )
    return issues


def _audit_source_refs(
    workspace: Path,
    source_refs: list[Any],
    *,
    risk_id: str,
    registry_path: Path,
    json_path: str,
) -> tuple[set[str], list[dict[str, str]]]:
    source_ids: set[str] = set()
    issues: list[dict[str, str]] = []
    for index, source_ref in enumerate(source_refs):
        if not isinstance(source_ref, Mapping):
            issues.append(
                _issue(
                    "invalid_source_ref",
                    "source ref must be an object",
                    risk_id=risk_id,
                    path=str(registry_path),
                    json_path=f"{json_path}[{index}]",
                )
            )
            continue
        source_id = str(source_ref.get("source_id") or "").strip()
        if source_id:
            source_ids.add(source_id)
        else:
            issues.append(
                _issue(
                    "invalid_source_ref",
                    "source ref must include source_id",
                    risk_id=risk_id,
                    path=str(registry_path),
                    json_path=f"{json_path}[{index}].source_id",
                )
            )
        issues.extend(
            _audit_path_ref(
                workspace,
                source_ref.get("path"),
                code="missing_source_ref",
                risk_id=risk_id,
                registry_path=registry_path,
                json_path=f"{json_path}[{index}].path",
            )
        )
        if not _non_empty_text(source_ref.get("section")):
            issues.append(
                _issue(
                    "invalid_source_ref",
                    "source ref must include section",
                    risk_id=risk_id,
                    path=str(registry_path),
                    json_path=f"{json_path}[{index}].section",
                )
            )
    return source_ids, issues


def _audit_active_gate(
    workspace: Path,
    risk: Mapping[str, Any],
    *,
    risk_id: str,
    registry_path: Path,
    json_path: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    required_text = {
        "owner_zone": "active_risk_missing_owner",
        "risk": "active_risk_missing_risk",
        "escalation_trigger": "active_risk_missing_escalation_trigger",
        "last_reviewed": "active_risk_missing_last_reviewed",
    }
    for field, code in required_text.items():
        if not _non_empty_text(risk.get(field)):
            issues.append(
                _issue(
                    code,
                    f"active risk must define {field}",
                    risk_id=risk_id,
                    path=str(registry_path),
                    json_path=f"{json_path}.{field}",
                )
            )
    for field in ("affected_contracts", "source_refs", "evidence_refs"):
        if not _as_list(risk.get(field)):
            issues.append(
                _issue(
                    f"active_risk_missing_{field}",
                    f"active risk must define {field}",
                    risk_id=risk_id,
                    path=str(registry_path),
                    json_path=f"{json_path}.{field}",
                )
            )
    issues.extend(
        _audit_acceptance(
            _as_list(risk.get("acceptance_criteria")),
            risk_id=risk_id,
            registry_path=registry_path,
            json_path=f"{json_path}.acceptance_criteria",
        )
    )
    issues.extend(
        _audit_linked_tests(
            workspace,
            _as_list(risk.get("linked_tests")),
            risk_id=risk_id,
            registry_path=registry_path,
            json_path=f"{json_path}.linked_tests",
        )
    )
    return issues


def audit_active_risks(workspace: Path, *, registry_path: Path | None = None) -> dict[str, Any]:
    workspace = workspace.resolve()
    registry = registry_path or workspace / DEFAULT_REGISTRY
    if not registry.is_absolute():
        registry = workspace / registry

    payload, issues = _load_json(registry)
    risk_count = 0
    active_count = 0
    registered_source_ids: set[str] = set()

    if payload is None:
        return {
            "schema": AUDIT_SCHEMA,
            "registry_path": str(registry),
            "status": "fail",
            "risk_count": risk_count,
            "active_count": active_count,
            "issues": issues,
        }

    if payload.get("schema") != REGISTRY_SCHEMA:
        issues.append(
            _issue(
                "registry_schema_validation",
                f"registry schema must be {REGISTRY_SCHEMA}",
                path=str(registry),
                json_path="$.schema",
            )
        )

    raw_risks = payload.get("risks")
    risks = raw_risks if isinstance(raw_risks, list) else []
    if not isinstance(raw_risks, list):
        issues.append(
            _issue(
                "registry_schema_validation",
                "registry risks must be an array",
                path=str(registry),
                json_path="$.risks",
            )
        )

    seen_ids: set[str] = set()
    for index, raw_risk in enumerate(risks):
        if not isinstance(raw_risk, Mapping):
            issues.append(
                _issue(
                    "invalid_risk_record",
                    "risk record must be an object",
                    path=str(registry),
                    json_path=f"$.risks[{index}]",
                )
            )
            continue
        risk_count += 1
        risk_id = str(raw_risk.get("id") or "").strip()
        risk_path = f"$.risks[{index}]"
        if not RISK_ID_RE.match(risk_id):
            issues.append(
                _issue(
                    "invalid_risk_id",
                    f"risk id must match TD-###: {risk_id}",
                    risk_id=risk_id,
                    path=str(registry),
                    json_path=f"{risk_path}.id",
                )
            )
        if risk_id in seen_ids:
            issues.append(
                _issue(
                    "duplicate_risk_id",
                    f"duplicate risk id: {risk_id}",
                    risk_id=risk_id,
                    path=str(registry),
                    json_path=f"{risk_path}.id",
                )
            )
        seen_ids.add(risk_id)

        status = str(raw_risk.get("status") or "").strip()
        if status not in ALLOWED_STATUSES:
            issues.append(
                _issue(
                    "invalid_risk_status",
                    f"risk status must be one of {', '.join(sorted(ALLOWED_STATUSES))}: {status}",
                    risk_id=risk_id,
                    path=str(registry),
                    json_path=f"{risk_path}.status",
                )
            )
        if str(raw_risk.get("priority") or "").strip() not in ALLOWED_PRIORITIES:
            issues.append(
                _issue(
                    "invalid_risk_priority",
                    "risk priority must be P0, P1, P2, or P3",
                    risk_id=risk_id,
                    path=str(registry),
                    json_path=f"{risk_path}.priority",
                )
            )

        source_ids, source_issues = _audit_source_refs(
            workspace,
            _as_list(raw_risk.get("source_refs")),
            risk_id=risk_id,
            registry_path=registry,
            json_path=f"{risk_path}.source_refs",
        )
        registered_source_ids.update(source_ids)
        issues.extend(source_issues)

        for ref_index, evidence_ref in enumerate(_as_list(raw_risk.get("evidence_refs"))):
            issues.extend(
                _audit_path_ref(
                    workspace,
                    evidence_ref,
                    code="missing_evidence_ref",
                    risk_id=risk_id,
                    registry_path=registry,
                    json_path=f"{risk_path}.evidence_refs[{ref_index}]",
                )
            )

        if status == "active":
            active_count += 1
            issues.extend(
                _audit_active_gate(
                    workspace,
                    raw_risk,
                    risk_id=risk_id,
                    registry_path=registry,
                    json_path=risk_path,
                )
            )
        elif _as_list(raw_risk.get("linked_tests")):
            issues.extend(
                _audit_linked_tests(
                    workspace,
                    _as_list(raw_risk.get("linked_tests")),
                    risk_id=risk_id,
                    registry_path=registry,
                    json_path=f"{risk_path}.linked_tests",
                )
            )

    for source_id in sorted(REQUIRED_ACTIVE_ARCHIVE_SOURCE_IDS - registered_source_ids):
        issues.append(
            _issue(
                "active_archive_source_not_registered",
                f"archive active risk source is not registered: {source_id}",
                path=str(registry),
                json_path="$.risks[*].source_refs",
            )
        )

    return {
        "schema": AUDIT_SCHEMA,
        "registry_path": str(registry),
        "status": "fail" if issues else "ok",
        "risk_count": risk_count,
        "active_count": active_count,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = audit_active_risks(args.workspace, registry_path=args.registry)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"active risk audit: risks={report['risk_count']} "
            f"active={report['active_count']} issues={len(report['issues'])}"
        )
        for issue in report["issues"]:
            print(
                f"- {issue['code']}: {issue['message']} "
                f"{issue.get('risk_id', '')} {issue.get('path', '')} {issue.get('json_path', '')}".rstrip()
            )
    if args.strict and report["issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
