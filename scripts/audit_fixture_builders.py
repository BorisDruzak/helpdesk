#!/usr/bin/env python3
"""Audit schema-validated fixture builders and their data-pack references."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.fixture_schema_builders import fixture_registry_schema, schema_builders


DEFAULT_REGISTRY = Path("quality/fixture_builders.json")
AUDIT_SCHEMA = "pc_client.fixture_builder_audit.v1"

FORBIDDEN_SECRET_KEYS = {"password", "token", "secret", "cookie", "auth_header", "authorization"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _issue(
    code: str,
    message: str,
    *,
    fixture_id: str | None = None,
    path: str | None = None,
    json_path: str | None = None,
) -> dict[str, str]:
    payload = {"code": code, "message": message}
    if fixture_id:
        payload["fixture_id"] = fixture_id
    if path:
        payload["path"] = path
    if json_path:
        payload["json_path"] = json_path
    return payload


def _load_json(path: Path, *, fixture_id: str | None = None) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, [_issue("missing_json_file", f"JSON file does not exist: {path}", fixture_id=fixture_id, path=str(path))]
    except (OSError, json.JSONDecodeError) as exc:
        return None, [
            _issue(
                "invalid_json_file",
                f"{type(exc).__name__}: {exc}",
                fixture_id=fixture_id,
                path=str(path),
            )
        ]
    if not isinstance(payload, dict):
        return None, [_issue("invalid_json_root", "JSON root must be an object", fixture_id=fixture_id, path=str(path))]
    return payload, []


def _format_json_path(parts: Iterable[object]) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


def _validate_schema(
    *,
    schema: dict[str, Any],
    payload: dict[str, Any],
    code: str,
    fixture_id: str | None,
    path: Path,
) -> list[dict[str, str]]:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    return [
        _issue(
            code,
            error.message,
            fixture_id=fixture_id,
            path=str(path),
            json_path=_format_json_path(error.absolute_path),
        )
        for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    ]


def _walk_dicts(value: Any, *, path: str = "$") -> Iterator[tuple[str, str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), child
            yield from _walk_dicts(child, path=child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_dicts(child, path=f"{path}[{index}]")


def _audit_secret_free(payload: dict[str, Any], *, fixture_id: str, path: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for json_path, key, value in _walk_dicts(payload):
        if key.lower() in FORBIDDEN_SECRET_KEYS:
            issues.append(
                _issue(
                    "forbidden_secret_key",
                    f"fixture contains forbidden secret key: {key}",
                    fixture_id=fixture_id,
                    path=str(path),
                    json_path=json_path,
                )
            )
        if isinstance(value, str):
            lowered = value.lower()
            if "bearer " in lowered or "begin private key" in lowered:
                issues.append(
                    _issue(
                        "forbidden_secret_value",
                        "fixture contains a token/private-key marker",
                        fixture_id=fixture_id,
                        path=str(path),
                        json_path=json_path,
                    )
                )
    return issues


def _records_by_key(records: Any, key_field: str) -> dict[str, dict[str, Any]]:
    if not isinstance(records, list):
        return {}
    return {
        str(record.get(key_field)): record
        for record in records
        if isinstance(record, dict) and str(record.get(key_field) or "").strip()
    }


def _audit_unique_keys(
    records: Any,
    key_field: str,
    *,
    fixture_id: str,
    path: Path,
    json_path: str,
) -> list[dict[str, str]]:
    if not isinstance(records, list):
        return []
    issues: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        key = str(record.get(key_field) or "").strip()
        if not key:
            continue
        if key in seen:
            issues.append(
                _issue(
                    "duplicate_fixture_key",
                    f"duplicate {key_field}: {key}",
                    fixture_id=fixture_id,
                    path=str(path),
                    json_path=f"{json_path}[{index}].{key_field}",
                )
            )
        seen.add(key)
    return issues


def _phase_e_refs(payload: dict[str, Any]) -> dict[str, set[str]]:
    return {
        "users": set(_records_by_key(payload.get("users"), "key")),
        "agents": set(_records_by_key(payload.get("vm_agents"), "key")),
        "forms": set(_records_by_key(payload.get("forms"), "scenario")),
        "knowledge": set(_records_by_key(payload.get("knowledge"), "scenario")),
    }


def _audit_phase_e_references(payload: dict[str, Any], *, fixture_id: str, path: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    issues.extend(_audit_unique_keys(payload.get("users"), "key", fixture_id=fixture_id, path=path, json_path="$.users"))
    issues.extend(
        _audit_unique_keys(payload.get("vm_agents"), "key", fixture_id=fixture_id, path=path, json_path="$.vm_agents")
    )
    issues.extend(_audit_unique_keys(payload.get("forms"), "scenario", fixture_id=fixture_id, path=path, json_path="$.forms"))
    issues.extend(
        _audit_unique_keys(payload.get("knowledge"), "scenario", fixture_id=fixture_id, path=path, json_path="$.knowledge")
    )
    issues.extend(
        _audit_unique_keys(
            payload.get("validation_matrix"),
            "gate",
            fixture_id=fixture_id,
            path=path,
            json_path="$.validation_matrix",
        )
    )

    refs = _phase_e_refs(payload)
    users = refs["users"]
    agents = refs["agents"]
    for index, agent in enumerate(payload.get("vm_agents") or []):
        if not isinstance(agent, dict):
            continue
        requester = str(agent.get("bound_requester") or "")
        if requester and requester not in users:
            issues.append(
                _issue(
                    "unknown_data_ref",
                    f"vm agent references unknown requester: {requester}",
                    fixture_id=fixture_id,
                    path=str(path),
                    json_path=f"$.vm_agents[{index}].bound_requester",
                )
            )
    for index, user in enumerate(payload.get("users") or []):
        if not isinstance(user, dict):
            continue
        expected_agent = user.get("expected_primary_agent")
        if isinstance(expected_agent, str) and expected_agent not in agents:
            issues.append(
                _issue(
                    "unknown_data_ref",
                    f"user references unknown expected primary agent: {expected_agent}",
                    fixture_id=fixture_id,
                    path=str(path),
                    json_path=f"$.users[{index}].expected_primary_agent",
                )
            )
    return issues


def audit_fixture_builders(workspace: Path, *, registry_path: Path | None = None) -> dict[str, Any]:
    workspace = workspace.resolve()
    registry = registry_path or workspace / DEFAULT_REGISTRY
    if not registry.is_absolute():
        registry = workspace / registry

    registry_payload, issues = _load_json(registry)
    fixture_count = 0
    builders = schema_builders()
    fixtures: list[Any] = []
    if registry_payload is not None:
        issues.extend(
            _validate_schema(
                schema=fixture_registry_schema(),
                payload=registry_payload,
                code="registry_schema_validation",
                fixture_id=None,
                path=registry,
            )
        )
        raw_fixtures = registry_payload.get("fixtures")
        fixtures = raw_fixtures if isinstance(raw_fixtures, list) else []

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, raw_fixture in enumerate(fixtures):
        if not isinstance(raw_fixture, dict):
            continue
        fixture_count += 1
        fixture_id = str(raw_fixture.get("id") or "").strip()
        fixture_path_text = str(raw_fixture.get("path") or "").replace("\\", "/").strip()
        builder_name = str(raw_fixture.get("schema_builder") or "").strip()
        fixture_path = workspace / fixture_path_text

        if fixture_id in seen_ids:
            issues.append(
                _issue(
                    "duplicate_fixture_id",
                    f"duplicate fixture id: {fixture_id}",
                    fixture_id=fixture_id,
                    path=str(registry),
                    json_path=f"$.fixtures[{index}].id",
                )
            )
        seen_ids.add(fixture_id)
        if fixture_path_text in seen_paths:
            issues.append(
                _issue(
                    "duplicate_fixture_path",
                    f"duplicate fixture path: {fixture_path_text}",
                    fixture_id=fixture_id,
                    path=str(registry),
                    json_path=f"$.fixtures[{index}].path",
                )
            )
        seen_paths.add(fixture_path_text)

        schema = builders.get(builder_name)
        if schema is None:
            issues.append(
                _issue(
                    "unknown_schema_builder",
                    f"unknown schema builder: {builder_name}",
                    fixture_id=fixture_id,
                    path=str(registry),
                    json_path=f"$.fixtures[{index}].schema_builder",
                )
            )
            continue

        payload, load_issues = _load_json(fixture_path, fixture_id=fixture_id)
        issues.extend(load_issues)
        if payload is None:
            continue
        issues.extend(
            _validate_schema(
                schema=schema,
                payload=payload,
                code="fixture_schema_validation",
                fixture_id=fixture_id,
                path=fixture_path,
            )
        )
        if bool(raw_fixture.get("secret_free", True)):
            issues.extend(_audit_secret_free(payload, fixture_id=fixture_id, path=fixture_path))
        if builder_name == "web_first_phase_e_test_data_pack_v1":
            issues.extend(_audit_phase_e_references(payload, fixture_id=fixture_id, path=fixture_path))

    return {
        "schema": AUDIT_SCHEMA,
        "registry_path": str(registry),
        "status": "fail" if issues else "ok",
        "fixture_count": fixture_count,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = audit_fixture_builders(args.workspace, registry_path=args.registry)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"fixture builder audit: fixtures={report['fixture_count']} issues={len(report['issues'])}")
        for issue in report["issues"]:
            print(
                f"- {issue['code']}: {issue['message']} "
                f"{issue.get('fixture_id', '')} {issue.get('path', '')} {issue.get('json_path', '')}".rstrip()
            )
    if args.strict and report["issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
