from __future__ import annotations

import json
from pathlib import Path

import scripts.business_smoke as business_smoke


class FakeResponse:
    def __init__(self, status: int, payload: dict, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self.payload = payload
        self.headers = headers or {}


class FakeClient:
    def __init__(self, responses: dict[tuple[str, str], FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict | None]] = []

    def request(self, method: str, path: str, json_body: dict | None = None) -> FakeResponse:
        self.calls.append((method, path, json_body))
        response = self.responses[(method, path)]
        if response.status >= 400:
            raise business_smoke.HttpStepError(response.status, response.payload.get("error", "failed"))
        return response


def test_business_smoke_writes_success_marker_without_secrets(tmp_path: Path) -> None:
    output = tmp_path / "business-smoke.json"
    client = FakeClient(
        {
            ("POST", "/api/web/session/login"): FakeResponse(
                200,
                {"status": "success"},
                {"set-cookie": "pc_client_web_session=secret; Secure; HttpOnly; SameSite=Lax"},
            ),
            ("GET", "/api/web/session/me"): FakeResponse(200, {"status": "success"}),
            ("GET", "/api/web/support/bootstrap"): FakeResponse(200, {"status": "success"}),
            ("GET", "/api/web/support/command-center"): FakeResponse(200, {"status": "success"}),
            ("GET", "/api/web/support/approvals"): FakeResponse(200, {"status": "success"}),
            ("GET", "/api/web/admin/tech/snapshot"): FakeResponse(200, {"status": "success"}),
        }
    )

    marker = business_smoke.run_business_smoke(
        base_url="https://stand.example",
        username="admin",
        password="super-secret",
        output=output,
        client=client,
        require_https=True,
        require_secure_cookie=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert marker["status"] == "success"
    assert payload["status"] == "success"
    assert [step["key"] for step in payload["steps"]] == [
        "web_session_login",
        "secure_cookie_flags",
        "session_me",
        "support_bootstrap",
        "command_center",
        "approval_center",
        "tech_snapshot",
    ]
    assert "super-secret" not in output.read_text(encoding="utf-8")
    assert "pc_client_web_session=secret" not in output.read_text(encoding="utf-8")


def test_url_client_can_allow_self_signed_https(monkeypatch) -> None:
    captured_handlers = []

    def fake_build_opener(*handlers):
        captured_handlers.extend(handlers)

        class FakeOpener:
            pass

        return FakeOpener()

    monkeypatch.setattr(business_smoke.urllib.request, "build_opener", fake_build_opener)

    business_smoke.UrlLibClient("https://stand.example", timeout=5.0, insecure_tls=True)

    assert any(isinstance(handler, business_smoke.urllib.request.HTTPSHandler) for handler in captured_handlers)


def test_url_client_reads_insecure_tls_from_env(monkeypatch) -> None:
    captured_handlers = []

    def fake_build_opener(*handlers):
        captured_handlers.extend(handlers)

        class FakeOpener:
            pass

        return FakeOpener()

    monkeypatch.setenv("BUSINESS_SMOKE_INSECURE_TLS", "true")
    monkeypatch.setattr(business_smoke.urllib.request, "build_opener", fake_build_opener)

    business_smoke.UrlLibClient("https://stand.example", timeout=5.0)

    assert any(isinstance(handler, business_smoke.urllib.request.HTTPSHandler) for handler in captured_handlers)


def test_business_smoke_runs_optional_business_acceptance_steps(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "business-smoke-business.json"
    client = FakeClient(
        {
            ("POST", "/api/web/session/login"): FakeResponse(
                200,
                {"status": "success"},
                {"set-cookie": "pc_client_web_session=secret; Secure; HttpOnly; SameSite=Lax"},
            ),
            ("GET", "/api/web/session/me"): FakeResponse(200, {"status": "success"}),
            ("GET", "/api/web/support/bootstrap"): FakeResponse(200, {"status": "success"}),
            ("GET", "/api/web/support/command-center"): FakeResponse(200, {"status": "success"}),
            ("GET", "/api/web/support/approvals"): FakeResponse(200, {"status": "success"}),
            ("GET", "/api/web/admin/tech/snapshot"): FakeResponse(200, {"status": "success"}),
            ("GET", "/api/web/admin/device-operations/device-1"): FakeResponse(200, {"status": "success"}),
            ("POST", "/api/tickets/create"): FakeResponse(200, {"status": "ok", "ticket": {"ticket_id": "ticket-1"}}),
            ("GET", "/api/web/support/tickets/ticket-1/workspace"): FakeResponse(200, {"status": "success", "data": {}}),
            ("POST", "/api/web/support/tickets/ticket-1/diagnostics/capabilities/endpoint.context.diagnostic.collect/run"): FakeResponse(
                202,
                {"status": "queued", "operation_id": "operation-1"},
            ),
            ("GET", "/api/operations/operation-1"): FakeResponse(
                200,
                {"status": "success", "operation": {"operation_id": "operation-1", "status": "succeeded"}},
            ),
        }
    )
    monkeypatch.setattr(business_smoke, "run_browser_https_wss_check", lambda **_kwargs: [
        {"key": "browser_mixed_content", "status": "success", "duration_ms": 1},
        {"key": "browser_wss", "status": "success", "duration_ms": 1},
    ])

    marker = business_smoke.run_business_smoke(
        base_url="https://stand.example",
        username="admin",
        password="super-secret",
        output=output,
        client=client,
        require_https=True,
        require_secure_cookie=True,
        browser_check=True,
        device_id="device-1",
        create_test_ticket=True,
        run_safe_tool="endpoint.context.diagnostic.collect",
        operation_wait_seconds=1,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    keys = [step["key"] for step in payload["steps"]]
    assert marker["status"] == "success"
    assert "ticket_create_optional" in keys
    assert "support_queue_action" in keys
    assert "safe_tool_endpoint_diagnostic" in keys
    assert "operation_result_check" in keys
    assert "browser_mixed_content" in keys
    assert "browser_wss" in keys
    assert payload["created_ticket_id"] == "ticket-1"
    assert payload["safe_tool_operation_id"] == "operation-1"
    assert "super-secret" not in output.read_text(encoding="utf-8")
    assert "pc_client_web_session=secret" not in output.read_text(encoding="utf-8")


def test_business_smoke_writes_failed_marker_on_failed_step(tmp_path: Path) -> None:
    output = tmp_path / "business-smoke-failed.json"
    client = FakeClient(
        {
            ("POST", "/api/web/session/login"): FakeResponse(
                401,
                {"status": "error", "error": "bad credentials"},
                {"set-cookie": "pc_client_web_session=secret"},
            )
        }
    )

    marker = business_smoke.run_business_smoke(
        base_url="http://stand.example",
        username="admin",
        password="secret",
        output=output,
        client=client,
        require_https=True,
        require_secure_cookie=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert marker["status"] == "failed"
    assert payload["status"] == "failed"
    assert payload["steps"][0]["key"] == "require_https"
    assert payload["steps"][0]["status"] == "failed"
    assert "secret" not in output.read_text(encoding="utf-8")
