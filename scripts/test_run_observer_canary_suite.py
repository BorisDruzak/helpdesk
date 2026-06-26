from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
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
        "base_url": "https://192.168.100.17:9443",
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
    assert "capability_run_succeeded" in code
    assert "diagnostic_server_connector" in code
    assert "diagnostic_observer_query" in code
    assert "diagnostic_manual" in code
    assert "diagnostic_remote_assist" in code
    assert "PlaybookRun" in code
    assert "ObserverOverlayService" in code


def test_default_observer_coverage_root_kinds_include_diagnostic_capabilities() -> None:
    assert "capability_run" in suite.DEFAULT_COVERAGE_ROOT_KINDS
    assert "server_connector_query" in suite.DEFAULT_COVERAGE_ROOT_KINDS
    assert "observer_query" in suite.DEFAULT_COVERAGE_ROOT_KINDS
    assert "manual_evidence" in suite.DEFAULT_COVERAGE_ROOT_KINDS
    assert "remote_assist" in suite.DEFAULT_COVERAGE_ROOT_KINDS


def test_source_coverage_root_kinds_are_subset_of_default_coverage() -> None:
    assert set(suite.SOURCE_COVERAGE_ROOT_KINDS).issubset(set(suite.DEFAULT_COVERAGE_ROOT_KINDS))
    assert suite.SOURCE_COVERAGE_ROOT_KINDS == (
        "module_reconcile",
        "playbook_run",
        "web_auth",
        "observer_runtime",
        "capability_run",
        "server_connector_query",
        "observer_query",
        "manual_evidence",
        "remote_assist",
    )


@pytest.mark.asyncio
async def test_api_client_login_uses_web_session_cookie_not_legacy_ui_login():
    seen: list[tuple[str, object]] = []

    async def web_login(request: web.Request) -> web.StreamResponse:
        payload = await request.json()
        seen.append(("/api/web/session/login", payload))
        response = web.json_response({"status": "success", "data": {"actor_role": "admin"}})
        response.set_cookie("pc_client_web_session", "issued-ui-token", path="/", httponly=True)
        return response

    async def legacy_login(request: web.Request) -> web.StreamResponse:
        payload = await request.json()
        seen.append(("/api/ui_login", payload))
        return web.json_response({"error_code": "LEGACY_AUTH_DISABLED"}, status=410)

    async def protected_trace(request: web.Request) -> web.StreamResponse:
        seen.append(("protected", request.headers.get("Authorization")))
        return web.json_response({"status": "success", "data": {"trace_id": "trace-1"}})

    app = web.Application()
    app.router.add_post("/api/web/session/login", web_login)
    app.router.add_post("/api/ui_login", legacy_login)
    app.router.add_get("/api/admin/tech/traces/trace-1", protected_trace)
    server = TestServer(app)
    await server.start_server()
    try:
        async with suite.ApiClient(str(server.make_url("/")).rstrip("/")) as api:
            token = await api.login_ui("admin", "admin123", expected_role="admin")
            _, payload = await api.request_json(
                "GET",
                "/api/admin/tech/traces/trace-1",
                token=token,
            )
    finally:
        await server.close()

    assert token == "issued-ui-token"
    assert payload["data"]["trace_id"] == "trace-1"
    assert seen == [
        (
            "/api/web/session/login",
            {"login": "admin", "password": "admin123", "expected_role": "admin"},
        ),
        ("protected", "Bearer issued-ui-token"),
    ]


def test_resolve_agent_build_expectations_defaults_local_version_to_windows_only() -> None:
    expectations = suite.resolve_agent_build_expectations(
        expected_agent_version="3.1.56",
        expected_agent_version_by_target=None,
    )

    assert expectations == {"windows_amd64": "3.1.56"}


def test_resolve_agent_build_expectations_accepts_target_specific_overrides() -> None:
    expectations = suite.resolve_agent_build_expectations(
        expected_agent_version="3.1.56",
        expected_agent_version_by_target="windows_amd64=3.1.57,linux_alt_x86_64=3.1.26",
    )

    assert expectations == {"windows_amd64": "3.1.57", "linux_alt_x86_64": "3.1.26"}


def test_parse_expected_agent_versions_by_target_rejects_invalid_items() -> None:
    with pytest.raises(ValueError):
        suite.parse_expected_agent_versions_by_target("windows_amd64")


class _FakeApi:
    def __init__(self, builds_by_target: dict[str, list[dict[str, str]]]) -> None:
        self.builds_by_target = builds_by_target

    async def request_json(self, method: str, path: str, **kwargs: object) -> tuple[int, dict[str, object]]:
        assert method == "GET"
        query = parse_qs(urlsplit(path).query)
        target = query["target"][0]
        return 200, {"builds": self.builds_by_target.get(target, [])}


@pytest.mark.asyncio
async def test_agent_build_registry_checks_exact_windows_and_any_unpinned_target() -> None:
    results = await suite.scenario_agent_build_registry(
        _FakeApi(
            {
                "windows_amd64": [
                    {"target": "windows_amd64", "version": "3.1.56", "sha256": "sha-win"},
                ],
                "linux_alt_x86_64": [
                    {"target": "linux_alt_x86_64", "version": "3.1.26", "sha256": "sha-linux"},
                ],
            }
        ),
        admin_token="admin-token",
        expected_versions_by_target={"windows_amd64": "3.1.56"},
        targets=("windows_amd64", "linux_alt_x86_64"),
    )

    assert [item.ok for item in results] == [True, True]
    assert results[0].details["expected_version"] == "3.1.56"
    assert results[1].details["expected_version"] is None
    assert results[1].details["available_versions"] == ["3.1.26"]
