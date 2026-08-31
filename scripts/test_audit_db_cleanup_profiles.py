import importlib
from pathlib import Path


def _write_test(tests_dir: Path, name: str, content: str) -> Path:
    path = tests_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_audit_tests_detects_profiles_no_db_agent_ws_and_missing(tmp_path):
    audit = importlib.import_module("scripts.audit_db_cleanup_profiles")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(
        tests_dir,
        "test_knowledge_api.py",
        'import pytest\n\npytestmark = pytest.mark.db_cleanup("knowledge")\n',
    )
    _write_test(
        tests_dir,
        "test_policy_math.py",
        "import pytest\n\npytestmark = [pytest.mark.no_db]\n",
    )
    _write_test(tests_dir, "test_agent_ws_flow.py", "def test_agent_flow(test_agent):\n    pass\n")
    _write_test(tests_dir, "test_ticket_api.py", "def test_ticket_flow(test_client):\n    pass\n")

    records = {record.file.name: record for record in audit.audit_tests(tests_dir)}

    assert records["test_knowledge_api.py"].explicit_profile == "knowledge"
    assert records["test_knowledge_api.py"].inferred_layer == "knowledge"
    assert records["test_policy_math.py"].no_db is True
    assert records["test_policy_math.py"].needs_profile is False
    assert records["test_agent_ws_flow.py"].likely_agent_ws is True
    assert records["test_agent_ws_flow.py"].needs_profile is False
    assert records["test_ticket_api.py"].explicit_profile is None
    assert records["test_ticket_api.py"].inferred_layer == "tickets"
    assert records["test_ticket_api.py"].needs_profile is True


def test_main_normal_mode_reports_missing_without_failing(tmp_path, capsys):
    audit = importlib.import_module("scripts.audit_db_cleanup_profiles")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(tests_dir, "test_ticket_api.py", "def test_ticket_flow(test_client):\n    pass\n")

    exit_code = audit.main(["--tests-dir", str(tests_dir)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "test_ticket_api.py" in output
    assert "tickets" in output
    assert "missing" in output
    assert "missing_profiles=1" in output


def test_report_profile_buckets_separate_skipped_files(tmp_path, capsys):
    audit = importlib.import_module("scripts.audit_db_cleanup_profiles")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(tests_dir, "test_ticket_api.py", "def test_ticket_flow(test_client):\n    pass\n")
    _write_test(tests_dir, "test_no_db_rules.py", "import pytest\n\npytestmark = pytest.mark.no_db\n")
    _write_test(tests_dir, "test_agent_ws_flow.py", "def test_agent_flow(test_agent):\n    pass\n")

    audit.main(["--tests-dir", str(tests_dir)])

    output = capsys.readouterr().out
    assert "missing=1" in output
    assert "skipped:no_db=1" in output
    assert "skipped:agent_ws=1" in output


def test_main_strict_mode_fails_only_for_missing_db_cleanup_candidates(tmp_path):
    audit = importlib.import_module("scripts.audit_db_cleanup_profiles")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(tests_dir, "test_agent_ws_flow.py", "def test_agent_flow(test_agent):\n    pass\n")
    _write_test(tests_dir, "test_no_db_rules.py", "import pytest\n\npytestmark = pytest.mark.no_db\n")

    assert audit.main(["--tests-dir", str(tests_dir), "--strict"]) == 0

    _write_test(tests_dir, "test_inventory_v3_service.py", "def test_inventory(test_engine):\n    pass\n")

    assert audit.main(["--tests-dir", str(tests_dir), "--strict"]) == 1


def test_pytestmark_list_preserves_explicit_profile_and_infers_registry_layer(tmp_path):
    audit = importlib.import_module("scripts.audit_db_cleanup_profiles")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(
        tests_dir,
        "test_registry_audience_groups.py",
        (
            "import pytest\n\n"
            "pytestmark = [\n"
            "    pytest.mark.integration,\n"
            "    pytest.mark.db_cleanup(\"registry_access\"),\n"
            "]\n"
        ),
    )

    (record,) = audit.audit_tests(tests_dir)

    assert record.explicit_profile == "registry_access"
    assert record.inferred_layer == "registry_access"
    assert record.needs_profile is False


def test_audit_file_accepts_utf8_bom(tmp_path):
    audit = importlib.import_module("scripts.audit_db_cleanup_profiles")
    tests_dir = tmp_path / "server" / "tests"
    path = tests_dir / "test_support_knowledge_provider.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\ufeffimport pytest\n\npytestmark = pytest.mark.db_cleanup(\"knowledge\")\n",
        encoding="utf-8",
    )

    (record,) = audit.audit_tests(tests_dir)

    assert record.parse_error is None
    assert record.explicit_profile == "knowledge"


def test_audit_treats_all_function_level_no_db_tests_as_no_db(tmp_path):
    audit = importlib.import_module("scripts.audit_db_cleanup_profiles")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(
        tests_dir,
        "test_access_control.py",
        (
            "import pytest\n\n"
            "@pytest.mark.no_db\n"
            "def test_rule_one():\n"
            "    pass\n\n"
            "@pytest.mark.no_db\n"
            "async def test_rule_two():\n"
            "    pass\n"
        ),
    )

    (record,) = audit.audit_tests(tests_dir)

    assert record.no_db is True
    assert record.needs_profile is False


def test_audit_infers_mixed_web_api_cleanup_profile_hints(tmp_path):
    audit = importlib.import_module("scripts.audit_db_cleanup_profiles")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(tests_dir, "test_web_support_api.py", "def test_support(test_client):\n    pass\n")
    _write_test(tests_dir, "test_requester_workspace_api.py", "def test_requester(test_client):\n    pass\n")
    _write_test(tests_dir, "test_p0_workbench_update_contracts.py", "def test_update(test_client):\n    pass\n")
    _write_test(tests_dir, "test_registration_api.py", "def test_registration(test_client):\n    pass\n")
    _write_test(tests_dir, "test_account_session_service.py", "def test_account(test_engine):\n    pass\n")

    records = {record.file.name: record for record in audit.audit_tests(tests_dir)}

    assert records["test_web_support_api.py"].inferred_layer == "web_support"
    assert records["test_requester_workspace_api.py"].inferred_layer == "web_support"
    assert records["test_p0_workbench_update_contracts.py"].inferred_layer == "web_support"
    assert records["test_registration_api.py"].inferred_layer == "registration"
    assert records["test_account_session_service.py"].inferred_layer == "registration"


def test_audit_accepts_new_web_api_cleanup_profiles(tmp_path, capsys):
    audit = importlib.import_module("scripts.audit_db_cleanup_profiles")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(
        tests_dir,
        "test_web_support_api.py",
        'import pytest\n\npytestmark = pytest.mark.db_cleanup("web_support")\n',
    )
    _write_test(
        tests_dir,
        "test_registration_api.py",
        'import pytest\n\npytestmark = pytest.mark.db_cleanup("registration")\n',
    )

    exit_code = audit.main(["--tests-dir", str(tests_dir)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Invalid profiles" not in output
    assert "web_support=1" in output
    assert "registration=1" in output
