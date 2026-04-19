from __future__ import annotations

import sys
from pathlib import Path

import scripts.run_observer_canary_suite as suite


def test_build_canary_module_payload_contains_expected_tools() -> None:
    payload = suite.build_canary_module_payload("observer_canary_demo", "1.1.0")

    assert payload["module_name"] == "observer_canary_demo"
    assert payload["version"] == "1.1.0"
    tool_names = [tool["tool_name"] for tool in payload["tools"]]
    assert tool_names == ["observer_canary_demo.echo", "observer_canary_demo.sleep"]
    assert all(tool["metadata"]["origin"] == "managed" for tool in payload["tools"])


def test_build_remote_python_command_uses_remote_shell() -> None:
    command, input_text = suite.build_remote_python_command(
        remote="altserver@192.168.100.17",
        code="print('hello')",
    )

    assert command[0] == "ssh"
    assert command[-2:] == ["altserver@192.168.100.17", suite.build_remote_python_shell()]
    assert input_text == "print('hello')"


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
