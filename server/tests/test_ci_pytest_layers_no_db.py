from types import SimpleNamespace
from pathlib import Path
import ast

import pytest

from tests import conftest


@pytest.mark.no_db
def test_ci_layer_markers_leave_pure_no_db_tests_unmarked():
    item = SimpleNamespace(fixturenames=["tmp_path"], added=[])
    item.add_marker = item.added.append

    conftest._apply_ci_layer_markers(item)

    assert item.added == []


@pytest.mark.no_db
def test_pytest_watchdog_seconds_parses_positive_env(monkeypatch):
    monkeypatch.setenv("PC_CLIENT_PYTEST_WATCHDOG_SECONDS", "15")

    assert conftest._pytest_watchdog_seconds() == 15.0


@pytest.mark.no_db
def test_pytest_watchdog_seconds_ignores_disabled_or_invalid_env(monkeypatch):
    monkeypatch.setenv("PC_CLIENT_PYTEST_WATCHDOG_SECONDS", "0")
    assert conftest._pytest_watchdog_seconds() is None

    monkeypatch.setenv("PC_CLIENT_PYTEST_WATCHDOG_SECONDS", "not-a-number")
    assert conftest._pytest_watchdog_seconds() is None


@pytest.mark.no_db
@pytest.mark.parametrize(
    "path",
    [
        "server/tests/test_tech_alert_rules_unit.py",
        "server/tests/test_ticket_notification_policy.py",
        "server/tests/test_requester_timeline_projection.py",
        "server/tests/test_runtime_control.py",
        "server/tests/test_support_knowledge_provider.py",
        "server/tests/test_segmentation_docs.py",
    ],
)
def test_pure_server_test_modules_are_marked_no_db(path: str) -> None:
    tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"))
    marker_assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets)
    ]

    assert marker_assignments, f"{path} should set module-level pytestmark = pytest.mark.no_db"
    assert any("no_db" in ast.unparse(node.value) for node in marker_assignments)
