from types import SimpleNamespace

import pytest

from tests import conftest


@pytest.mark.no_db
def test_ci_layer_markers_classify_test_agent_fixture():
    item = SimpleNamespace(fixturenames=["tmp_path", "test_client", "test_agent"], added=[])
    item.add_marker = item.added.append

    conftest._apply_ci_layer_markers(item)

    assert "agent_ws" in item.added
    assert "integration" in item.added


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
