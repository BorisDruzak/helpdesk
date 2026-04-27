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


def test_extract_tool_result_version_reads_nested_observations_and_output() -> None:
    tool_result = {
        "observations": {"version": "1.2.3"},
        "result": {"output": {"version": "9.9.9"}},
    }
    assert suite.extract_tool_result_version(tool_result) == "1.2.3"

    nested_only = {"result": {"output": {"version": "2.0.0"}}}
    assert suite.extract_tool_result_version(nested_only) == "2.0.0"


def test_build_ws_chat_outbox_item_embeds_ticket_id_inside_event() -> None:
    payload = suite.build_ws_chat_outbox_item(
        device_id="device-1",
        ticket_id="ticket-1",
        outbox_id="ob-1",
        agent_seq=12,
        trace_id="trace-1",
        text="hello",
    )

    assert payload["type"] == "outbox_item"
    assert payload["payload"]["agent_seq"] == 12
    assert payload["payload"]["event"]["ticket_id"] == "ticket-1"
    assert payload["payload"]["event"]["text"] == "hello"


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
    assert "await init_db()" in consent_code


def test_remote_create_waiting_consent_operation_code_contains_expected_contract() -> None:
    code = suite.remote_create_waiting_consent_operation_code(
        device_id="device-1",
        ticket_id="ticket-1",
        tool_name="observer_canary_demo.consent_probe",
    )

    assert "initial_status=\"waiting_consent\"" in code
    assert "tool_call_started" in code
    assert "observer_canary_demo.consent_probe" in code
    assert "await init_db()" in code


def test_remote_trigger_ws_rate_limit_code_contains_expected_contract() -> None:
    code = suite.remote_trigger_ws_rate_limit_code(
        device_id="device-1",
        agent_token="agent-token-1",
        ticket_id="ticket-1",
    )

    assert "\"type\": \"handshake\"" in code
    assert "\"type\": \"outbox_item\"" in code
    assert "ticket-1" in code
    assert "observer-rate-remote" in code
    assert "\"nack\": payload" in code


def test_build_observer_coverage_summary_tracks_required_root_kinds() -> None:
    results = [
        suite.ScenarioResult(
            name="module_install",
            ok=True,
            summary="ok",
            details={"root_kind": "module_install", "trace_id": "trace-module"},
        ),
        suite.ScenarioResult(
            name="coverage_playbook_run",
            ok=True,
            summary="ok",
            details={"root_kind": "playbook_run", "trace_id": "trace-playbook", "span_count": 2},
        ),
        suite.ScenarioResult(
            name="coverage_web_auth",
            ok=False,
            summary="failed",
            details={"root_kind": "web_auth", "trace_id": "trace-web-auth"},
        ),
    ]

    summary = suite.build_observer_coverage_summary(
        results,
        required_root_kinds=["module_install", "playbook_run", "web_auth", "observer_runtime"],
    )

    assert summary["ok"] is False
    assert summary["observed_root_kinds"] == ["module_install", "playbook_run"]
    assert summary["missing_root_kinds"] == ["web_auth", "observer_runtime"]
    assert summary["trace_refs"] == [
        {"scenario": "module_install", "root_kind": "module_install", "trace_id": "trace-module"},
        {"scenario": "coverage_playbook_run", "root_kind": "playbook_run", "trace_id": "trace-playbook"},
    ]


def test_render_markdown_report_includes_coverage_and_results() -> None:
    report = {
        "generated_at": "2026-04-28T10:00:00+00:00",
        "base_url": "http://192.168.100.17:8666",
        "device_id": "device-1",
        "coverage": {
            "ok": False,
            "required_root_kinds": ["module_install", "web_auth"],
            "observed_root_kinds": ["module_install"],
            "missing_root_kinds": ["web_auth"],
        },
        "results": [
            {"name": "module_install", "ok": True, "summary": "Installed canary module."},
            {"name": "coverage_web_auth", "ok": False, "summary": "No web auth trace."},
        ],
    }

    markdown = suite.render_markdown_report(report)

    assert "# Observer Canary Report" in markdown
    assert "Coverage: **failed**" in markdown
    assert "`web_auth`" in markdown
    assert "| FAIL | coverage_web_auth | No web auth trace. |" in markdown


def test_remote_seed_observer_source_coverage_code_contains_projection_sources() -> None:
    code = suite.remote_seed_observer_source_coverage_code("device-1")

    assert "module_reconcile_failed" in code
    assert "observer_runtime_degraded" in code
    assert "web_auth_failed" in code
    assert "PlaybookRun" in code
    assert "ObserverOverlayService" in code
