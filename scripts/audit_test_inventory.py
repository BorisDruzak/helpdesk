#!/usr/bin/env python3
"""Audit pytest inventory ownership, markers, and CI-suite safety rules."""

from __future__ import annotations

import argparse
import ast
import configparser
import fnmatch
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACE = REPO_ROOT
DEFAULT_PYTEST_INI = REPO_ROOT / "pytest.ini"
DEFAULT_PATHS = (
    REPO_ROOT / "server" / "tests",
    REPO_ROOT / "pc_agent" / "tests",
    REPO_ROOT / "scripts",
)

DEFAULT_KNOWN_MARKERS = {
    "agent_ws",
    "asyncio",
    "db_cleanup",
    "filterwarnings",
    "integration",
    "light_app",
    "manual",
    "no_db",
    "parametrize",
    "skip",
    "skipif",
    "unit",
    "usefixtures",
    "xfail",
}

DB_FIXTURES = {
    "patched_get_session",
    "run_migrations",
    "test_agent",
    "test_app",
    "test_client",
    "test_database_admin_url",
    "test_database_url",
    "test_engine",
}

NETWORK_CALLS = {
    "httpx.get",
    "httpx.post",
    "httpx.request",
    "requests.delete",
    "requests.get",
    "requests.patch",
    "requests.post",
    "requests.put",
    "requests.request",
    "websocket.create_connection",
    "websockets.connect",
}


@dataclass(frozen=True)
class InventoryIssue:
    file: Path
    line: int
    code: str
    message: str


@dataclass(frozen=True)
class TestFunction:
    name: str
    line: int
    fixtures: tuple[str, ...]
    markers: frozenset[str]


@dataclass(frozen=True)
class InventoryRecord:
    file: Path
    suite: str
    markers: tuple[str, ...]
    fixtures: tuple[str, ...]
    issues: tuple[InventoryIssue, ...]


@dataclass(frozen=True)
class InventoryReport:
    records: tuple[InventoryRecord, ...]
    issues: tuple[InventoryIssue, ...]

    @property
    def has_failures(self) -> bool:
        return bool(self.issues)


def load_known_markers(pytest_ini: Path = DEFAULT_PYTEST_INI) -> set[str]:
    markers = set(DEFAULT_KNOWN_MARKERS)
    if not pytest_ini.exists():
        return markers

    parser = configparser.ConfigParser()
    parser.read(pytest_ini, encoding="utf-8-sig")
    if not parser.has_section("pytest"):
        return markers

    raw = parser.get("pytest", "markers", fallback="")
    for line in raw.splitlines():
        marker = line.strip().split(":", 1)[0].split("(", 1)[0].strip()
        if marker:
            markers.add(marker)
    return markers


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
        return _marker_name(node.func)
    name = _dotted_name(node)
    if not name or not name.startswith("pytest.mark."):
        return None
    return name.removeprefix("pytest.mark.")


def _flatten_marker_value(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: list[ast.AST] = []
        for element in node.elts:
            values.extend(_flatten_marker_value(element))
        return values
    return [node]


def _module_markers(tree: ast.Module) -> frozenset[str]:
    markers: set[str] = set()
    for statement in tree.body:
        value: ast.AST | None = None
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in statement.targets
        ):
            value = statement.value
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "pytestmark"
        ):
            value = statement.value
        if value is None:
            continue
        for marker_node in _flatten_marker_value(value):
            marker = _marker_name(marker_node)
            if marker:
                markers.add(marker)
    return frozenset(markers)


def _decorator_markers(decorators: Sequence[ast.expr]) -> frozenset[str]:
    markers: set[str] = set()
    for decorator in decorators:
        marker = _marker_name(decorator)
        if marker:
            markers.add(marker)
    return frozenset(markers)


def _all_pytest_markers(tree: ast.Module) -> tuple[tuple[str, int], ...]:
    markers: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        parent_name = _dotted_name(node.value)
        if parent_name == "pytest.mark":
            markers.append((node.attr, getattr(node, "lineno", 1)))
    return tuple(markers)


def _function_fixtures(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    args = [
        *node.args.posonlyargs,
        *node.args.args,
        *node.args.kwonlyargs,
    ]
    return tuple(arg.arg for arg in args if arg.arg not in {"self", "cls"})


def _iter_test_functions(tree: ast.Module, module_markers: frozenset[str]) -> tuple[TestFunction, ...]:
    tests: list[TestFunction] = []
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and statement.name.startswith("test_"):
            markers = module_markers | _decorator_markers(statement.decorator_list)
            tests.append(
                TestFunction(
                    name=statement.name,
                    line=statement.lineno,
                    fixtures=_function_fixtures(statement),
                    markers=markers,
                )
            )
            continue
        if not isinstance(statement, ast.ClassDef) or not statement.name.startswith("Test"):
            continue
        class_markers = module_markers | _decorator_markers(statement.decorator_list)
        for child in statement.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                markers = class_markers | _decorator_markers(child.decorator_list)
                tests.append(
                    TestFunction(
                        name=f"{statement.name}.{child.name}",
                        line=child.lineno,
                        fixtures=_function_fixtures(child),
                        markers=markers,
                    )
                )
    return tuple(tests)


def _network_call_lines(tree: ast.Module) -> tuple[tuple[str, int], ...]:
    calls: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted_name(node.func)
        if name in NETWORK_CALLS:
            calls.append((name, getattr(node, "lineno", 1)))
    return tuple(calls)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _classify_server_db_api_file(filename: str) -> str:
    try:
        from scripts import run_ci_suite

        return run_ci_suite._classify_server_db_api_test_file(filename)
    except Exception:
        if filename == "test_migration_schema_contract.py":
            return "migration_schema"
        layer_rules: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("server_pytest_db_knowledge", ("test_knowledge_*.py", "test_support_knowledge_provider.py")),
            (
                "server_pytest_db_tickets",
                (
                    "test_ticket_*.py",
                    "test_helpdesk_*.py",
                    "test_form_*.py",
                    "test_policy_health*.py",
                    "test_public_queue_privacy.py",
                    "test_service_catalog_*.py",
                    "test_reports_service_catalog.py",
                    "test_requester_timeline_projection.py",
                    "test_stage8.py",
                    "test_support_playbook_readiness.py",
                    "test_registry_*.py",
                ),
            ),
            (
                "server_pytest_db_observer_diagnostics",
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
                "server_pytest_db_agent_runtime",
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
        for layer_name, patterns in layer_rules:
            if any(fnmatch.fnmatch(filename, pattern) for pattern in patterns):
                return layer_name
        return "server_pytest_db_web_api"


def _classify_suite(path: Path, workspace: Path, markers: frozenset[str], fixtures: set[str]) -> str:
    resolved = path.resolve()
    workspace = workspace.resolve()
    server_tests = workspace / "server" / "tests"
    pc_agent_tests = workspace / "pc_agent" / "tests"
    scripts_dir = workspace / "scripts"

    if _is_relative_to(resolved, server_tests):
        if "no_db" in markers:
            return "server_pytest_no_db"
        if "agent_ws" in markers or "test_agent" in fixtures:
            return "server_pytest_agent_ws"
        return _classify_server_db_api_file(path.name)
    if _is_relative_to(resolved, pc_agent_tests):
        return "pc_agent_pytest"
    if _is_relative_to(resolved, scripts_dir):
        return "scripts_pytest_no_db"
    return "unowned"


def _iter_test_files(paths: Iterable[Path]) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            if path.name.startswith("test_") and path.suffix == ".py":
                files.append(path)
            continue
        if path.exists():
            files.extend(sorted(path.rglob("test_*.py")))
    return tuple(sorted(set(files)))


def audit_file(path: Path, *, workspace: Path, known_markers: set[str]) -> InventoryRecord:
    issues: list[InventoryIssue] = []
    try:
        text = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        issue = InventoryIssue(path, int(exc.lineno or 1), "parse_error", f"{exc.msg}")
        return InventoryRecord(path, "parse_error", (), (), (issue,))

    module_markers = _module_markers(tree)
    tests = _iter_test_functions(tree, module_markers)
    markers = {marker for marker, _line in _all_pytest_markers(tree)}
    markers.update(module_markers)
    for test in tests:
        markers.update(test.markers)

    for marker, line in _all_pytest_markers(tree):
        if marker not in known_markers:
            issues.append(InventoryIssue(path, line, "unknown_marker", f"unknown pytest marker {marker!r}"))

    fixture_names = {fixture for test in tests for fixture in test.fixtures}
    suite = _classify_suite(path, workspace, frozenset(markers), fixture_names)
    for test in tests:
        db_fixtures = sorted(set(test.fixtures) & DB_FIXTURES)
        if "no_db" in test.markers and db_fixtures:
            issues.append(
                InventoryIssue(
                    path,
                    test.line,
                    "no_db_uses_db_fixture",
                    f"{test.name} is marked no_db but requests DB/app fixture(s): {', '.join(db_fixtures)}",
                )
            )
        if db_fixtures and suite == "unowned":
            issues.append(
                InventoryIssue(
                    path,
                    test.line,
                    "db_test_unowned",
                    f"{test.name} requests DB/app fixture(s) but is not owned by a canonical CI suite",
                )
            )

    if "manual" not in markers:
        for call_name, line in _network_call_lines(tree):
            issues.append(
                InventoryIssue(
                    path,
                    line,
                    "network_access_in_pr_suite",
                    f"direct network call {call_name} requires manual marker or a live-only harness",
                )
            )

    return InventoryRecord(
        file=path,
        suite=suite,
        markers=tuple(sorted(markers)),
        fixtures=tuple(sorted(fixture_names)),
        issues=tuple(issues),
    )


def audit_paths(
    paths: Iterable[Path],
    *,
    workspace: Path = DEFAULT_WORKSPACE,
    known_markers: set[str] | None = None,
) -> InventoryReport:
    marker_set = set(known_markers or load_known_markers(workspace / "pytest.ini"))
    records = tuple(
        audit_file(path, workspace=workspace, known_markers=marker_set) for path in _iter_test_files(paths)
    )
    issues = tuple(issue for record in records for issue in record.issues)
    return InventoryReport(records=records, issues=issues)


def _rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def print_report(report: InventoryReport, *, workspace: Path) -> None:
    by_suite = Counter(record.suite for record in report.records)
    by_issue = Counter(issue.code for issue in report.issues)
    print(f"test inventory audit: workspace={workspace}")
    print(f"summary: files={len(report.records)} issues={len(report.issues)}")
    if by_suite:
        print("by suite: " + ", ".join(f"{key}={by_suite[key]}" for key in sorted(by_suite)))
    if by_issue:
        print("by issue: " + ", ".join(f"{key}={by_issue[key]}" for key in sorted(by_issue)))
    else:
        print("by issue: none")

    if not report.issues:
        return
    print("file | line | code | message")
    for issue in report.issues:
        print(f"{_rel(issue.file, workspace)} | {issue.line} | {issue.code} | {issue.message}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--pytest-ini", type=Path)
    parser.add_argument("--paths", nargs="+", type=Path)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = args.workspace.resolve()
    paths = args.paths or [workspace / "server" / "tests", workspace / "pc_agent" / "tests", workspace / "scripts"]
    pytest_ini = args.pytest_ini or workspace / "pytest.ini"
    report = audit_paths(paths, workspace=workspace, known_markers=load_known_markers(pytest_ini))
    print_report(report, workspace=workspace)
    if args.strict and report.has_failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
