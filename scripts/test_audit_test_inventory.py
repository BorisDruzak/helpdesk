import importlib
from pathlib import Path


def test_historical_clone_contract_is_owned_by_the_no_template_migration_schema_layer():
    """The 133->134 lifecycle must run in CI's direct-Alembic layer only."""

    audit = importlib.import_module("scripts.audit_test_inventory")
    ci = importlib.import_module("scripts.run_ci_suite")
    catalog_module = importlib.import_module("scripts.suite_catalog")
    workspace = Path(__file__).resolve().parents[1]
    contract_path = workspace / "server" / "tests" / "test_migration_schema_contract.py"
    legacy_path = workspace / "server" / "tests" / "test_knowledge_schema_retirement.py"

    assert "test_clone_upgrade_from_133_retires_only_historical_knowledge_ai_schema" in contract_path.read_text(
        encoding="utf-8"
    )
    assert "pytest.mark.migration_clone" in contract_path.read_text(encoding="utf-8")
    assert not legacy_path.exists()

    migration_suite = next(
        suite for suite in catalog_module.load_suite_catalog(workspace).suites if suite.name == "migration_schema"
    )
    assert migration_suite.paths == ("server/tests/test_migration_schema_contract.py",)
    assert migration_suite.database == "isolated-postgres-no-template"
    assert str(Path("server/tests/test_migration_schema_contract.py")) in ci._migration_schema_command(
        workspace, workspace / "artifacts" / "junit.xml"
    )
    assert ci._server_pytest_env(layer_name="migration_schema", use_template=False)[
        "PC_CLIENT_TEST_DB_TEMPLATE"
    ] == "0"

    record = audit.audit_paths([contract_path], workspace=workspace).records[0]
    assert record.suite == "migration_schema"
    assert record.issues == ()


def test_inventory_keeps_mixed_no_db_and_migration_clone_contracts_in_migration_schema(tmp_path):
    audit = importlib.import_module("scripts.audit_test_inventory")
    tests_dir = tmp_path / "server" / "tests"
    contract_path = _write_test(
        tests_dir,
        "test_migration_schema_contract.py",
        (
            "import pytest\n\n"
            "@pytest.mark.no_db\n"
            "def test_static_contract():\n"
            "    pass\n\n"
            "@pytest.mark.migration_clone\n"
            "def test_private_clone(migration_clone_database_url):\n"
            "    pass\n"
        ),
    )

    record = audit.audit_paths([contract_path], workspace=tmp_path).records[0]

    assert record.suite == "migration_schema"
    assert record.issues == ()


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
    _write_test(
        tests_dir,
        "test_migration_schema_contract.py",
        (
            "import pytest\n\n"
            "pytestmark = pytest.mark.db_cleanup('full')\n\n"
            "async def test_migrations(test_engine):\n"
            "    pass\n"
        ),
    )

    records = {record.file.name: record for record in audit.audit_paths([tests_dir], workspace=tmp_path).records}

    assert records["test_knowledge_api.py"].suite == "server_pytest_db_knowledge"
    assert records["test_operation_retry.py"].suite == "server_pytest_agent_ws"
    assert records["test_migration_schema_contract.py"].suite == "migration_schema"
    assert records["test_knowledge_api.py"].issues == ()
    assert records["test_operation_retry.py"].issues == ()
    assert records["test_migration_schema_contract.py"].issues == ()


def test_inventory_audit_allows_the_explicit_manual_cross_repo_wss_suites():
    audit = importlib.import_module("scripts.audit_test_inventory")
    workspace = Path(__file__).resolve().parents[1]
    acceptance_dir = workspace / "server" / "tests" / "acceptance"

    report = audit.audit_paths(
        [
            acceptance_dir / "test_endpoint_module_platform_v1.py",
            acceptance_dir / "test_endpoint_operations_v1_acceptance.py",
        ],
        workspace=workspace,
    )

    assert report.issues == ()


def test_inventory_audit_uses_workspace_suite_catalog_for_server_db_ownership(tmp_path):
    audit = importlib.import_module("scripts.audit_test_inventory")
    tests_dir = tmp_path / "server" / "tests"
    (tmp_path / "quality").mkdir()
    (tmp_path / "quality" / "test_suites.toml").write_text(
        """
[[suites]]
name = "server_pytest_db_knowledge"
runner = "pytest"
server_db_api_patterns = ["test_custom_knowledge_*.py"]

[[suites]]
name = "server_pytest_db_web_api"
runner = "pytest"
server_db_api_catch_all = true
""".strip()
        + "\n",
        encoding="utf-8",
    )
    _write_test(
        tests_dir,
        "test_custom_knowledge_contract.py",
        (
            "import pytest\n\n"
            "pytestmark = pytest.mark.db_cleanup('knowledge')\n\n"
            "async def test_custom_contract(test_client, test_engine):\n"
            "    pass\n"
        ),
    )

    records = {record.file.name: record for record in audit.audit_paths([tests_dir], workspace=tmp_path).records}

    assert records["test_custom_knowledge_contract.py"].suite == "server_pytest_db_knowledge"
    assert records["test_custom_knowledge_contract.py"].issues == ()


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
