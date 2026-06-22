import importlib
from pathlib import Path


def _write_test(tests_dir: Path, name: str, content: str) -> Path:
    path = tests_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_audit_identifies_safe_http_candidate(tmp_path):
    audit = importlib.import_module("scripts.audit_test_app_light_candidates")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(
        tests_dir,
        "test_registration_api.py",
        'import pytest\n\npytestmark = pytest.mark.db_cleanup("registration")\n\ndef test_flow(test_client):\n    pass\n',
    )

    (record,) = audit.audit_tests(tests_dir)

    assert record.file.name == "test_registration_api.py"
    assert record.uses_test_client is True
    assert record.light_opt_in is False
    assert record.unsafe_terms == ()
    assert record.recommendation == "candidate"


def test_audit_marks_outbox_and_agent_runtime_files_unsafe(tmp_path):
    audit = importlib.import_module("scripts.audit_test_app_light_candidates")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(
        tests_dir,
        "test_p0_workbench_update_contracts.py",
        (
            "from websocket.agent_services import CommandResultService\n"
            "from websocket.contexts import AgentConnectionContext\n\n"
            "def test_update(test_client):\n"
            "    pass\n"
        ),
    )
    _write_test(
        tests_dir,
        "test_outbox_runtime.py",
        "from websocket.device_outbox_sender import DeviceOutboxSender\n\n"
        "def test_runtime(test_client):\n"
        "    pass\n",
    )

    records = {record.file.name: record for record in audit.audit_tests(tests_dir)}

    assert "CommandResultService" in records["test_p0_workbench_update_contracts.py"].unsafe_terms
    assert "AgentConnectionContext" in records["test_p0_workbench_update_contracts.py"].unsafe_terms
    assert records["test_p0_workbench_update_contracts.py"].recommendation == "keep_regular"
    assert "DeviceOutboxSender" in records["test_outbox_runtime.py"].unsafe_terms
    assert records["test_outbox_runtime.py"].recommendation == "keep_regular"


def test_audit_detects_module_level_light_opt_in_alias(tmp_path):
    audit = importlib.import_module("scripts.audit_test_app_light_candidates")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(
        tests_dir,
        "test_requester_workspace_api.py",
        (
            "import pytest\n\n"
            "@pytest.fixture\n"
            "def test_client(test_client_light):\n"
            "    return test_client_light\n\n"
            "def test_flow(test_client):\n"
            "    pass\n"
        ),
    )

    (record,) = audit.audit_tests(tests_dir)

    assert record.light_opt_in is True
    assert record.recommendation == "already_light"


def test_main_reports_candidate_counts(tmp_path, capsys):
    audit = importlib.import_module("scripts.audit_test_app_light_candidates")
    tests_dir = tmp_path / "server" / "tests"
    _write_test(tests_dir, "test_registration_api.py", "def test_flow(test_client):\n    pass\n")
    _write_test(tests_dir, "test_ws_flow.py", "def test_flow(test_agent):\n    pass\n")

    exit_code = audit.main(["--tests-dir", str(tests_dir)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "test_registration_api.py" in output
    assert "candidate=1" in output
    assert "keep_regular=1" in output
