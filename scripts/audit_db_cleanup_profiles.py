#!/usr/bin/env python3
"""Audit server pytest files for explicit db_cleanup profile coverage."""

from __future__ import annotations

import argparse
import ast
import fnmatch
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TESTS_DIR = REPO_ROOT / "server" / "tests"

KNOWN_PROFILES = {
    "full",
    "knowledge",
    "observer_diagnostics",
    "tickets",
    "agent_runtime",
    "registry_access",
    "policies_config",
    "registration",
    "web_support",
}

LAYER_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "migration_schema",
        (
            "test_migration_schema_contract.py",
        ),
    ),
    (
        "registration",
        (
            "test_account_session_service.py",
            "test_registration_api.py",
        ),
    ),
    (
        "web_support",
        (
            "test_p0_workbench_update_contracts.py",
            "test_requester_workspace_api.py",
            "test_web_support_api.py",
        ),
    ),
    (
        "knowledge",
        (
            "test_knowledge_*.py",
            "test_support_knowledge_provider.py",
        ),
    ),
    (
        "observer_diagnostics",
        (
            "test_admin_tech_api.py",
            "test_control_plane_api.py",
            "test_diagnostic_*.py",
            "test_manual_capability_provider.py",
            "test_observer_*.py",
            "test_trace_overlay_api.py",
            "test_workflow_side_effect_observability.py",
            "test_zabbix_provider_no_db.py",
        ),
    ),
    (
        "registry_access",
        (
            "test_registry_*.py",
            "test_access_*.py",
            "test_*_access_*.py",
            "test_*_audience_*.py",
            "test_*_group_*.py",
            "test_*_permission*.py",
            "test_*_permissions*.py",
        ),
    ),
    (
        "tickets",
        (
            "test_ticket_*.py",
            "test_helpdesk_*.py",
            "test_form_*.py",
            "test_public_queue_privacy.py",
            "test_service_catalog_*.py",
            "test_reports_service_catalog.py",
            "test_requester_timeline_projection.py",
            "test_stage8.py",
            "test_support_playbook_readiness.py",
        ),
    ),
    (
        "policies_config",
        (
            "test_policy_*.py",
            "test_*_policy.py",
            "test_*_policies.py",
            "test_*_config.py",
            "test_*_sla*.py",
            "test_*_ola*.py",
            "test_*_routing*.py",
            "test_*_closure*.py",
            "test_*_visibility*.py",
            "test_*_reporting*.py",
            "test_*_smart_view*.py",
        ),
    ),
    (
        "agent_runtime",
        (
            "test_agent_*.py",
            "test_cancel_operations.py",
            "test_command_result_*.py",
            "test_device_*.py",
            "test_handshake_module_reconcile.py",
            "test_modules_*.py",
            "test_operation_*.py",
            "test_outbox_*.py",
            "test_protocol_*.py",
            "test_remote_assist_*.py",
            "test_state_manager_agent_registry.py",
            "test_subscription_registry.py",
            "test_tool_*.py",
            "test_tools_*.py",
        ),
    ),
)


@dataclass(frozen=True)
class AuditRecord:
    file: Path
    inferred_layer: str
    explicit_profile: str | None
    no_db: bool
    likely_agent_ws: bool
    parse_error: str | None = None

    @property
    def needs_profile(self) -> bool:
        return not self.no_db and not self.likely_agent_ws and self.explicit_profile is None


def infer_layer(path: Path) -> str:
    name = path.name
    for layer, patterns in LAYER_PATTERNS:
        if any(fnmatch.fnmatch(name, pattern) for pattern in patterns):
            return layer
    return "web_api"


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
        return node.attr
    return None


def _marker_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        return _dotted_name(node.func)
    return _dotted_name(node)


def _pytestmark_values(tree: ast.Module) -> list[ast.AST]:
    values: list[ast.AST] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in statement.targets):
                values.extend(_flatten_marker_value(statement.value))
        elif isinstance(statement, ast.AnnAssign):
            target = statement.target
            if isinstance(target, ast.Name) and target.id == "pytestmark" and statement.value is not None:
                values.extend(_flatten_marker_value(statement.value))
    return values


def _flatten_marker_value(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: list[ast.AST] = []
        for element in node.elts:
            values.extend(_flatten_marker_value(element))
        return values
    return [node]


def _module_markers(tree: ast.Module) -> tuple[str | None, bool]:
    explicit_profile: str | None = None
    no_db = False
    for node in _pytestmark_values(tree):
        marker_name = _marker_name(node)
        if marker_name == "pytest.mark.no_db":
            no_db = True
            continue
        if marker_name != "pytest.mark.db_cleanup":
            continue
        if not isinstance(node, ast.Call) or len(node.args) != 1 or node.keywords:
            explicit_profile = "<invalid>"
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            explicit_profile = arg.value
        else:
            explicit_profile = "<invalid>"
    return explicit_profile, no_db


def _decorators_have_marker(decorators: list[ast.expr], expected_name: str) -> bool:
    return any(_marker_name(decorator) == expected_name for decorator in decorators)


def _iter_test_functions(tree: ast.Module) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, bool]]:
    tests: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, bool]] = []
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and statement.name.startswith("test_"):
            tests.append((statement, False))
            continue
        if not isinstance(statement, ast.ClassDef) or not statement.name.startswith("Test"):
            continue
        class_no_db = _decorators_have_marker(statement.decorator_list, "pytest.mark.no_db")
        for child in statement.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                tests.append((child, class_no_db))
    return tests


def _all_tests_marked_no_db(tree: ast.Module) -> bool:
    tests = _iter_test_functions(tree)
    if not tests:
        return False
    return all(
        inherited_no_db or _decorators_have_marker(function.decorator_list, "pytest.mark.no_db")
        for function, inherited_no_db in tests
    )


def _uses_test_agent_fixture(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(arg.arg == "test_agent" for arg in node.args.args):
            return True
        if any(arg.arg == "test_agent" for arg in node.args.kwonlyargs):
            return True
    return False


def _has_agent_ws_marker(text: str) -> bool:
    return "pytest.mark.agent_ws" in text or "pytestmark = pytest.mark.agent_ws" in text


def audit_file(path: Path) -> AuditRecord:
    text = path.read_text(encoding="utf-8-sig")
    likely_agent_ws = "agent_ws" in path.name or _has_agent_ws_marker(text)
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return AuditRecord(
            file=path,
            inferred_layer=infer_layer(path),
            explicit_profile=None,
            no_db=False,
            likely_agent_ws=likely_agent_ws,
            parse_error=f"{exc.msg} at line {exc.lineno}",
        )
    explicit_profile, no_db = _module_markers(tree)
    no_db = no_db or _all_tests_marked_no_db(tree)
    likely_agent_ws = likely_agent_ws or _uses_test_agent_fixture(tree)
    return AuditRecord(
        file=path,
        inferred_layer=infer_layer(path),
        explicit_profile=explicit_profile,
        no_db=no_db,
        likely_agent_ws=likely_agent_ws,
    )


def audit_tests(tests_dir: Path = DEFAULT_TESTS_DIR) -> list[AuditRecord]:
    return [audit_file(path) for path in sorted(tests_dir.glob("test_*.py"))]


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _format_profile(record: AuditRecord) -> str:
    if record.explicit_profile:
        return record.explicit_profile
    return "missing"


def _profile_bucket(record: AuditRecord) -> str:
    if record.explicit_profile:
        return record.explicit_profile
    if record.no_db:
        return "skipped:no_db"
    if record.likely_agent_ws:
        return "skipped:agent_ws"
    return "missing"


def print_report(records: list[AuditRecord], *, base_dir: Path) -> None:
    rows: list[tuple[str, str, str, str, str, str]] = []
    for record in records:
        try:
            file_name = record.file.relative_to(base_dir).as_posix()
        except ValueError:
            file_name = record.file.as_posix()
        status = "missing" if record.needs_profile else "ok"
        if record.parse_error:
            status = f"parse_error:{record.parse_error}"
        rows.append(
            (
                file_name,
                record.inferred_layer,
                _format_profile(record),
                _format_bool(record.no_db),
                _format_bool(record.likely_agent_ws),
                status,
            )
        )

    headers = ("file", "inferred_layer", "profile", "no_db", "likely_agent_ws", "status")
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(value)) for width, value in zip(widths, row)]

    def print_row(row: tuple[str, str, str, str, str, str]) -> None:
        print("  ".join(value.ljust(width) for value, width in zip(row, widths)))

    print_row(headers)
    print_row(tuple("-" * width for width in widths))
    for row in rows:
        print_row(row)

    by_profile: dict[str, int] = {}
    by_layer: dict[str, int] = {}
    for record in records:
        by_profile[_profile_bucket(record)] = by_profile.get(_profile_bucket(record), 0) + 1
        by_layer[record.inferred_layer] = by_layer.get(record.inferred_layer, 0) + 1

    missing_count = sum(1 for record in records if record.needs_profile)
    no_db_count = sum(1 for record in records if record.no_db)
    agent_ws_count = sum(1 for record in records if record.likely_agent_ws)
    invalid_profiles = sorted(
        {
            record.explicit_profile
            for record in records
            if record.explicit_profile and record.explicit_profile not in KNOWN_PROFILES
        }
    )

    print()
    print(
        "Summary: "
        f"files={len(records)} "
        f"missing_profiles={missing_count} "
        f"no_db={no_db_count} "
        f"likely_agent_ws={agent_ws_count}"
    )
    print("By layer: " + ", ".join(f"{key}={by_layer[key]}" for key in sorted(by_layer)))
    print("By profile: " + ", ".join(f"{key}={by_profile[key]}" for key in sorted(by_profile)))
    if invalid_profiles:
        print("Invalid profiles: " + ", ".join(invalid_profiles))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests-dir", type=Path, default=DEFAULT_TESTS_DIR)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when a DB-backed, non-agent-ws file has no db_cleanup profile.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    tests_dir = args.tests_dir
    records = audit_tests(tests_dir)
    print_report(records, base_dir=tests_dir)
    if args.strict and any(record.needs_profile or record.parse_error for record in records):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
