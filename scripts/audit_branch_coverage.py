#!/usr/bin/env python3
"""Audit targeted branch coverage declarations for critical pure logic."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY = Path("quality/critical_branch_coverage.json")
SCHEMA = "pc_client.critical_branch_coverage.v1"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _issue(code: str, message: str, *, path: str | None = None, branch_id: str | None = None) -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    if branch_id:
        payload["branch_id"] = branch_id
    return payload


def _load_json(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, [_issue("missing_registry", f"registry does not exist: {path}", path=str(path))]
    except (OSError, json.JSONDecodeError) as exc:
        return None, [_issue("invalid_registry_json", f"{type(exc).__name__}: {exc}", path=str(path))]
    if not isinstance(payload, dict):
        return None, [_issue("invalid_registry", "registry root must be an object", path=str(path))]
    return payload, []


def _test_node_exists(test_path: Path, node_parts: list[str]) -> bool:
    if not node_parts:
        return True
    try:
        tree = ast.parse(test_path.read_text(encoding="utf-8-sig"))
    except (OSError, SyntaxError):
        return False

    current_body = tree.body
    for index, raw_part in enumerate(node_parts):
        part = raw_part.split("[", 1)[0]
        if not part:
            return False
        matches = [
            node
            for node in current_body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == part
        ]
        if not matches:
            return False
        node = matches[0]
        if index == len(node_parts) - 1:
            return True
        if not isinstance(node, ast.ClassDef):
            return False
        current_body = node.body
    return True


def _validate_test_ref(workspace: Path, ref: str) -> list[dict[str, str]]:
    parts = [part for part in str(ref or "").split("::") if part]
    if not parts:
        return [_issue("invalid_test_ref", "test ref is empty")]
    test_path_text = parts[0].replace("\\", "/")
    if not test_path_text.endswith(".py"):
        return [_issue("invalid_test_ref", f"test ref must start with a Python test file: {ref}")]
    test_path = workspace / test_path_text
    if not test_path.exists():
        return [_issue("missing_test_file", f"test file does not exist: {test_path_text}", path=test_path_text)]
    if not _test_node_exists(test_path, parts[1:]):
        return [_issue("missing_test_node", f"test node does not exist: {ref}", path=test_path_text)]
    return []


def audit_branch_coverage(workspace: Path, *, registry_path: Path | None = None) -> dict[str, Any]:
    registry = registry_path or workspace / DEFAULT_REGISTRY
    if not registry.is_absolute():
        registry = workspace / registry
    payload, issues = _load_json(registry)
    packages = payload.get("packages") if isinstance(payload, dict) else None
    branch_count = 0
    package_count = 0
    seen_branch_ids: set[str] = set()

    if payload is None:
        packages = []
    else:
        if payload.get("schema") != SCHEMA:
            issues.append(_issue("invalid_schema", f"schema must be {SCHEMA}", path=str(registry)))
        if not isinstance(packages, list):
            issues.append(_issue("invalid_packages", "packages must be a list", path=str(registry)))
            packages = []

    for raw_package in packages:
        package_count += 1
        if not isinstance(raw_package, dict):
            issues.append(_issue("invalid_package", "package entry must be an object"))
            continue
        package_path = str(raw_package.get("path") or "").replace("\\", "/").strip()
        owner = str(raw_package.get("owner") or "").strip()
        branches = raw_package.get("branches")
        if not package_path:
            issues.append(_issue("missing_package_path", "package path is required"))
        elif not (workspace / package_path).exists():
            issues.append(
                _issue("missing_package_file", f"package file does not exist: {package_path}", path=package_path)
            )
        if not owner:
            issues.append(_issue("missing_owner", "package owner is required", path=package_path or None))
        if not isinstance(branches, list) or not branches:
            issues.append(_issue("missing_branches", "package must declare at least one branch", path=package_path))
            continue

        for raw_branch in branches:
            branch_count += 1
            if not isinstance(raw_branch, dict):
                issues.append(_issue("invalid_branch", "branch entry must be an object", path=package_path))
                continue
            branch_id = str(raw_branch.get("id") or "").strip()
            tested_by = raw_branch.get("tested_by")
            if not branch_id:
                issues.append(_issue("missing_branch_id", "branch id is required", path=package_path))
            elif branch_id in seen_branch_ids:
                issues.append(
                    _issue("duplicate_branch_id", f"duplicate branch id: {branch_id}", path=package_path, branch_id=branch_id)
                )
            else:
                seen_branch_ids.add(branch_id)
            if not str(raw_branch.get("description") or "").strip():
                issues.append(_issue("missing_description", "branch description is required", path=package_path, branch_id=branch_id))
            if str(raw_branch.get("criticality") or "").strip() not in {"P0", "P1", "P2"}:
                issues.append(_issue("invalid_criticality", "criticality must be P0, P1 or P2", path=package_path, branch_id=branch_id))
            if not isinstance(tested_by, list) or not tested_by:
                issues.append(_issue("missing_tested_by", "branch must declare tested_by refs", path=package_path, branch_id=branch_id))
                continue
            for ref in tested_by:
                for ref_issue in _validate_test_ref(workspace, str(ref)):
                    ref_issue.setdefault("branch_id", branch_id)
                    issues.append(ref_issue)

    return {
        "schema": "pc_client.critical_branch_coverage_audit.v1",
        "registry_path": str(registry),
        "status": "fail" if issues else "ok",
        "package_count": package_count,
        "branch_count": branch_count,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = audit_branch_coverage(args.workspace, registry_path=args.registry)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "branch coverage audit: "
            f"packages={report['package_count']} branches={report['branch_count']} "
            f"issues={len(report['issues'])}"
        )
        for issue in report["issues"]:
            print(
                f"- {issue['code']}: {issue['message']} "
                f"{issue.get('path', '')} {issue.get('branch_id', '')}".rstrip()
            )
    if args.strict and report["issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
