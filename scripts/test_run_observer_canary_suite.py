from __future__ import annotations

import sys
from pathlib import Path

import scripts.run_observer_canary_suite as suite


def test_build_canary_module_payload_contains_expected_tools() -> None:
    payload = suite.build_canary_module_payload("observer_canary_demo", "1.1.0")

    assert payload["module_name"] == "observer_canary_demo"
    assert payload["version"] == "1.1.0"
    tool_names = [tool["tool_name"] for tool in payload["tools"]]
    assert tool_names == [
        "observer_canary_demo.echo",
        "observer_canary_demo.sleep",
        "observer_canary_demo.consent_probe",
    ]
    assert all(tool["metadata"]["origin"] == "managed" for tool in payload["tools"])
    consent_tool = next(tool for tool in payload["tools"] if tool["tool_name"].endswith(".consent_probe"))
    assert consent_tool["metadata"]["requires_consent"] is True


def test_build_remote_python_command_uses_remote_shell() -> None:
    command, input_text = suite.build_remote_python_command(
        remote="altserver@192.168.100.17",
        code="print('hello')",
    )

    assert command[0] == "ssh"
    assert command[-2:] == ["altserver@192.168.100.17", suite.build_remote_python_shell()]
    assert input_text == "print('hello')"
    assert "PYTHONPATH=" in suite.build_remote_python_shell()


def test_run_subprocess_supports_positional_cwd_argument(tmp_path: Path) -> None:
    completed = suite.run_subprocess(
        [sys.executable, "-c", "print('observer-canary-ok')"],
        tmp_path,
        None,
    )

    assert completed.stdout.strip() == "observer-canary-ok"


def test_remote_force_operation_timeout_code_varies_by_mode() -> None:
    consent_code = suite.remote_force_operation_timeout_code("op-consent", mode="consent")
    execution_code = suite.remote_force_operation_timeout_code("op-execution", mode="execution")

    assert "1900" in consent_code
    assert "240" in execution_code
    assert "op-consent" in consent_code
    assert "op-execution" in execution_code


def test_remote_create_waiting_consent_operation_code_contains_expected_contract() -> None:
    code = suite.remote_create_waiting_consent_operation_code(
        device_id="device-1",
        ticket_id="ticket-1",
        tool_name="observer_canary_demo.consent_probe",
    )

    assert "initial_status=\"waiting_consent\"" in code
    assert "tool_call_started" in code
    assert "observer_canary_demo.consent_probe" in code
