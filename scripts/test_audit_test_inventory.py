import importlib
from pathlib import Path


def _write_test(tests_dir: Path, name: str, content: str) -> Path:
    path = tests_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _issue_codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_inventory_audit_detects_marker_fixture_and_network_violations(tmp_path):
    audit = importlib.import_module("scripts.audit_test_inventory")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(
        tests_dir,
        "test_bad_inventory.py",
        (
            "import pytest\n"
            "import requests\n\n"
            "pytestmark = pytest.mark.unknown_gate\n\n"
            "@pytest.mark.no_db\n"
            "def test_uses_db_fixture(test_client):\n"
            "    pass\n\n"
            "def test_external_network():\n"
            "    requests.get('https://example.invalid')\n"
        ),
    )

    report = audit.audit_paths([tests_dir], workspace=tmp_path, known_markers=audit.DEFAULT_KNOWN_MARKERS)

    assert _issue_codes(report) == {
        "unknown_marker",
        "no_db_uses_db_fixture",
        "network_access_in_pr_suite",
    }
    assert report.has_failures is True


def test_inventory_audit_accepts_owned_server_db_and_agent_ws_files(tmp_path):
    audit = importlib.import_module("scripts.audit_test_inventory")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(
        tests_dir,
        "test_knowledge_api.py",
        (
            "import pytest\n\n"
            "pytestmark = pytest.mark.db_cleanup('knowledge')\n\n"
            "async def test_knowledge_flow(test_client, test_engine):\n"
            "    pass\n"
        ),
    )
    _write_test(
        tests_dir,
        "test_operation_retry.py",
        "async def test_retry(test_client, test_agent, test_engine):\n    pass\n",
    )

    records = {record.file.name: record for record in audit.audit_paths([tests_dir], workspace=tmp_path).records}

    assert records["test_knowledge_api.py"].suite == "server_pytest_db_knowledge"
    assert records["test_operation_retry.py"].suite == "server_pytest_agent_ws"
    assert records["test_knowledge_api.py"].issues == ()
    assert records["test_operation_retry.py"].issues == ()


def test_inventory_audit_strict_mode_fails_only_for_inventory_issues(tmp_path, capsys):
    audit = importlib.import_module("scripts.audit_test_inventory")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(
        tests_dir,
        "test_contract_no_db.py",
        "import pytest\n\npytestmark = pytest.mark.no_db\n\ndef test_contract():\n    pass\n",
    )

    assert audit.main(["--workspace", str(tmp_path), "--paths", str(tests_dir), "--strict"]) == 0

    _write_test(
        tests_dir,
        "test_contract_no_db.py",
        "import pytest\n\npytestmark = pytest.mark.no_db\n\ndef test_contract(test_engine):\n    pass\n",
    )

    assert audit.main(["--workspace", str(tmp_path), "--paths", str(tests_dir), "--strict"]) == 1
    output = capsys.readouterr().out
    assert "no_db_uses_db_fixture=1" in output
    assert "test_contract_no_db.py" in output
