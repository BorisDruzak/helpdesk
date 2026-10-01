"""Offline SDK/bootstrap policy and real aiohttp integration regressions."""
import importlib
import json
import asyncio
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

pytestmark = pytest.mark.no_db


@pytest.fixture
def bootstrap(monkeypatch):
    module = importlib.import_module("observability.sentry")
    monkeypatch.setattr(module, "_runtime", None)
    yield module
    if module._runtime is not None:
        module._runtime.close()


def settings(**overrides):
    values = dict(SENTRY_DSN="", SENTRY_ENVIRONMENT="", SENTRY_RELEASE="",
                  SENTRY_TRACES_SAMPLE_RATE="0.10", APP_ENV="dev")
    values.update(overrides)
    return SimpleNamespace(**values)


def app():
    application = web.Application()
    async def healthy(request):
        return web.Response()
    application.router.add_get("/api/tickets/{ticket_id}", healthy)
    return application


def test_disabled_does_not_import_or_initialize_sdk(bootstrap, monkeypatch):
    loader = Mock(side_effect=AssertionError("SDK must not load"))
    monkeypatch.setattr(bootstrap, "_load_sdk", loader)
    runtime = bootstrap.configure_sentry(app(), config=settings())
    assert not runtime.enabled
    runtime.close()
    loader.assert_not_called()


def test_configured_once_with_explicit_safe_options(bootstrap, monkeypatch, tmp_path):
    client = Mock()
    sdk = SimpleNamespace(init=Mock(), get_client=Mock(return_value=client))
    integration = Mock()
    monkeypatch.setattr(bootstrap, "_load_sdk", lambda: (sdk, integration))
    cfg = settings(SENTRY_DSN="https://synthetic-key@example.invalid/1", APP_ENV="prod")
    runtime = bootstrap.configure_sentry(app(), config=cfg, identity_path=tmp_path / "missing")
    assert bootstrap.configure_sentry(app(), config=cfg) is runtime
    assert runtime.enabled
    sdk.init.assert_called_once()
    options = sdk.init.call_args.kwargs
    assert options["environment"] == "production"
    assert options["traces_sample_rate"] == 0.10
    assert options["send_default_pii"] is False
    assert options["include_local_variables"] is False
    assert options["include_source_context"] is False
    assert options["max_request_body_size"] == "never"
    assert options["default_integrations"] is False
    assert options["auto_enabling_integrations"] is False
    assert options["enable_logs"] is False
    assert options["enable_metrics"] is False
    assert options["profiles_sample_rate"] == 0
    assert options["profile_session_sample_rate"] == 0
    assert options["auto_session_tracking"] is False
    assert options["max_breadcrumbs"] == 0
    assert options["trace_propagation_targets"] == []
    assert options["release"] == ""  # No SDK auto-detection/Git subprocess.
    assert options["server_name"] == ""
    assert options["spotlight"] is False
    assert options["shutdown_timeout"] == 1.0
    assert options["transport_queue_size"] == 32
    integration.assert_called_once_with(transaction_style="method_and_path_pattern")
    runtime.close()
    runtime.close()
    client.close.assert_called_once_with(timeout=1.0)


@pytest.mark.parametrize("raw,expected", [("0.2", .2), ("-1", 0), ("2", 1),
    ("nan", .1), ("inf", .1), ("", .1), ("private-config-marker", .1)])
def test_rate_handling_has_no_value_leak(bootstrap, raw, expected, capsys):
    parsed = bootstrap.SentrySettings.from_config(settings(SENTRY_TRACES_SAMPLE_RATE=raw))
    assert parsed.traces_sample_rate == expected
    output = capsys.readouterr()
    assert output.out == output.err == ""


def test_release_identity_and_override_without_checkout(bootstrap, tmp_path, monkeypatch):
    identity = tmp_path / "release-identity.json"
    sha = "a" * 40
    identity.write_text(json.dumps({"helpdesk_git_sha": sha}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert bootstrap.resolve_release("", identity) == sha
    assert bootstrap.resolve_release("b" * 40, identity) == "b" * 40
    assert bootstrap.resolve_release("invalid-private-override", identity) == sha
    assert bootstrap.DEFAULT_IDENTITY_PATH == Path(bootstrap.__file__).resolve().parents[2] / "release-identity.json"


@pytest.mark.parametrize("content", ["{bad", "[]", "null", '{"helpdesk_git_sha":"bad"}', "{}"])
def test_bad_identity_is_optional(bootstrap, tmp_path, content):
    path = tmp_path / "release-identity.json"
    path.write_text(content, encoding="utf-8")
    assert bootstrap.resolve_release("", path) is None
    assert bootstrap.resolve_release("", tmp_path / "absent") is None


def test_sdk_failure_does_not_expose_exception_or_retry(bootstrap, monkeypatch):
    sdk = SimpleNamespace(init=Mock(side_effect=ValueError("private-DSN-marker")))
    monkeypatch.setattr(bootstrap, "_load_sdk", lambda: (sdk, Mock()))
    warning = Mock()
    monkeypatch.setattr(bootstrap.logger, "warning", warning)
    runtime = bootstrap.configure_sentry(app(), config=settings(SENTRY_DSN="malformed-private-value"))
    assert not runtime.enabled
    assert bootstrap.configure_sentry(app(), config=settings()) is runtime
    sdk.init.assert_called_once()
    assert warning.call_args.args == ("Sentry observability unavailable; Helpdesk continues without it",)
    assert not warning.call_args.kwargs


def test_close_failure_isolated(bootstrap):
    client = Mock(close=Mock(side_effect=RuntimeError("private-transport-error")))
    runtime = bootstrap.SentryRuntime(client)
    runtime.close()
    assert not runtime.enabled


def test_defensive_projection_preserves_signal_but_discards_private_data():
    from observability.privacy import EventSanitizer
    sanitizer = EventSanitizer({"/api/tickets/{ticket_id}"}, "a" * 40, "production")
    event = {
        "event_id": "b" * 32, "level": "error", "transaction": "GET /api/tickets/{ticket_id}",
        "request": {"method": "GET", "url": "https://user:secret@example.invalid/api/tickets/123?token=secret",
            "headers": {"Authorization": "Bearer private-auth", "Cookie": "private-cookie", "Set-Cookie": "private-set-cookie"},
            "cookies": {"session": "private-session"}, "data": {"password": "private-password", "token": "private-token"},
            "query_string": "consent_token=private-consent", "env": {"PASSWORD": "private-env"}},
        "user": {"email": "private-email"}, "extra": {"ticket_description": "private-description"},
        "tags": {"chat": "private-chat"}, "breadcrumbs": {"values": [{"message": "private-log"}]},
        "contexts": {"trace": {"trace_id": "c" * 32, "span_id": "d" * 16, "data": {"token": "private-trace"}}, "device": {"credential": "private-device"}},
        "exception": {"values": [{"type": "ZeroDivisionError", "value": "division by zero", "stacktrace": {"frames": [{
            "filename": "server/tickets/service.py", "abs_path": "C:/Users/private-user/service.py", "function": "create_ticket", "lineno": 12,
            "vars": {"password": "private-local"}, "pre_context": ["private-source"], "context_line": "private-source"}]}}]},
        "password": "private-top", "token": "private-top-token", "release": "private-wrong-release"}
    hint = {"attachments": [object()]}
    result = sanitizer(event, hint)
    assert result["exception"]["values"][0]["value"] == "division by zero"
    frame = result["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert frame["filename"] == "server/tickets/service.py" and frame["lineno"] == 12
    assert result["transaction"] == "GET /api/tickets/{ticket_id}"
    assert result["release"] == "a" * 40 and result["environment"] == "production"
    assert "private-" not in json.dumps(result)
    assert "attachments" not in hint
    assert result["request"] == {"method": "GET", "url": "/api/tickets/{ticket_id}"}


def test_transaction_policy_drops_span_payloads_and_arbitrary_error_text():
    from observability.privacy import EventSanitizer
    sanitizer = EventSanitizer({"/api/tickets/{ticket_id}"}, None, "dev")
    result = sanitizer({"type": "transaction", "transaction": "GET /api/tickets/{ticket_id}",
        "start_timestamp": 1.0, "timestamp": 2.0,
        "spans": [{"op": "http.client", "span_id": "a" * 16, "trace_id": "b" * 32,
            "start_timestamp": 1.1, "timestamp": 1.5, "description": "private-url-token",
            "data": {"http.request.headers.authorization": "private-auth", "db.params": "private-sql"}}],
        "exception": {"values": [{"type": "ValueError", "value": "private-ticket-description"}]}}, {})
    assert result["spans"][0]["op"] == "http.client"
    assert result["start_timestamp"] == 1.0
    assert "private-" not in json.dumps(result)
    assert sanitizer({"transaction": "GET /api/tickets/private-token", "request": {"url": "private-url"}}, {})["transaction"] == "[unresolved route]"


def test_malformed_late_scope_data_drops_event_without_raising():
    from observability.privacy import EventSanitizer
    class BadEvent(dict):
        def get(self, *args):
            raise RuntimeError("private-malformed-value")
    sanitizer = EventSanitizer(set(), None, "dev")
    assert sanitizer(BadEvent(), {"attachments": [object()]}) is None


@pytest.mark.asyncio
async def test_real_sdk_aiohttp_error_and_trace_use_only_in_memory_transport(bootstrap, monkeypatch, tmp_path):
    import sentry_sdk
    from sentry_sdk.transport import Transport
    sdk_init = sentry_sdk.init
    envelopes = []

    class MemoryTransport(Transport):
        def capture_envelope(self, envelope):
            envelopes.append(envelope)

    def offline_init(**options):
        options["transport"] = MemoryTransport
        return sdk_init(**options)

    monkeypatch.setattr(sentry_sdk, "init", offline_init)
    monkeypatch.setenv("SENTRY_SPOTLIGHT", "http://synthetic-sidecar.invalid/stream")
    application = web.Application()

    async def broken(request):
        await request.json()
        sentry_sdk.get_current_scope().add_attachment(bytes=b"private-file-contents", filename="private-file.txt")
        raise ValueError("private-ticket-body")

    application.router.add_post("/api/tickets/{ticket_id}", broken)
    runtime = bootstrap.configure_sentry(application, config=settings(
        SENTRY_DSN="https://synthetic-key@example.invalid/1", SENTRY_TRACES_SAMPLE_RATE="0.10"), identity_path=tmp_path / "missing")
    # Force one synthetic test trace; production config remains0.10.
    client = sentry_sdk.get_client()
    assert client.spotlight is None
    client.options["traces_sampler"] = lambda ctx: 1.0
    async with TestClient(TestServer(application)) as browser:
        response = await browser.post("/api/tickets/123?token=private-query", json={"description": "private-ticket-body"},
            headers={"Authorization": "Bearer private-auth", "Cookie": "session=private-cookie",
                "sentry-trace": "cccccccccccccccccccccccccccccccc-dddddddddddddddd-1",
                "baggage": "sentry-user_segment=private-user,sentry-release=private-incoming-release"})
        assert response.status == 500
    items = [item for e in envelopes for item in e.items]
    assert any(item.type == "event" for item in items)
    assert any(item.type == "transaction" for item in items)
    assert all(item.type in {"event", "transaction"} for item in items)
    payloads = [item.payload.json for item in items]
    assert "private-" not in json.dumps(payloads)
    assert all(b"private-" not in envelope.serialize() for envelope in envelopes)
    assert all(p["transaction"] == "POST /api/tickets/{ticket_id}" for p in payloads)
    assert payloads[0]["exception"]["values"][0]["type"] == "ValueError"
    runtime.close()
    sentry_sdk.get_global_scope().set_client(None)


@pytest.mark.asyncio
async def test_unreachable_transport_cannot_break_requests_or_unbounded_shutdown(bootstrap, monkeypatch, tmp_path):
    import sentry_sdk
    from sentry_sdk.transport import HttpTransport
    entered = threading.Event()
    release = threading.Event()

    def stalled_submission(*args, **kwargs):
        entered.set()
        release.wait(timeout=5)
        raise OSError("private-network-error")

    # Real SDK worker/queue/flush; replace the network boundary, never use DNS,
    # the real Sentry instance or a local HTTP ingestion endpoint.
    monkeypatch.setattr(HttpTransport, "_send_request", stalled_submission)
    application = web.Application()
    async def healthy(request):
        return web.Response(text="ok")
    async def broken(request):
        raise ZeroDivisionError("division by zero")
    application.router.add_get("/health", healthy)
    application.router.add_get("/broken", broken)
    runtime = bootstrap.configure_sentry(application, config=settings(
        SENTRY_DSN="https://synthetic-key@example.invalid/1", SENTRY_TRACES_SAMPLE_RATE="0"), identity_path=tmp_path / "missing")
    assert runtime.enabled and not entered.is_set()  # No startup network probe.
    try:
        async with TestClient(TestServer(application)) as browser:
            assert (await browser.get("/broken")).status == 500
            assert await asyncio.to_thread(entered.wait, 2)
            started = time.monotonic()
            assert (await browser.get("/health")).status == 200
            assert time.monotonic() - started < 1
        started = time.monotonic()
        runtime.close()
        assert time.monotonic() - started < 1.5
    finally:
        release.set()
        runtime.close()
        sentry_sdk.get_global_scope().set_client(None)


@pytest.mark.parametrize("environment,app_env,expected", [
    ("staging", "prod", "staging"), ("", "prod", "production"),
    ("bad private value", "prod", "production"), ("", "dev", "dev")])
def test_environment_defaults_and_invalid_optional_config(bootstrap, environment, app_env, expected):
    assert bootstrap.SentrySettings.from_config(settings(SENTRY_ENVIRONMENT=environment, APP_ENV=app_env)).environment == expected


def test_server_main_calls_bootstrap_before_serving_and_closes(bootstrap, monkeypatch):
    import server as server_module
    sequence = []
    application = web.Application()
    runtime = SimpleNamespace(close=lambda: sequence.append("close"))
    monkeypatch.setattr(server_module, "create_app", lambda: application)
    monkeypatch.setattr(server_module, "configure_sentry", lambda app: sequence.append("configure") or runtime)
    monkeypatch.setattr(server_module.web, "run_app", lambda app, **kwargs: sequence.append("serve"))
    monkeypatch.setattr(server_module.logger, "add", lambda *a, **kw: None)
    monkeypatch.setattr(server_module.logger, "remove", lambda *a, **kw: None)
    server_module.main()
    assert sequence == ["configure", "serve", "close"]


def test_create_app_preserves_existing_hooks_and_auth_without_sdk_init(bootstrap, monkeypatch):
    import server as server_module
    configure = Mock(side_effect=AssertionError("factory is not process startup"))
    monkeypatch.setattr(server_module, "configure_sentry", configure)
    application = server_module.create_app()
    assert server_module.on_startup in application.on_startup
    assert server_module.on_cleanup in application.on_cleanup
    assert len(application.middlewares) == 2
    assert any(route.resource.canonical == "/api/health" for route in application.router.routes())
    configure.assert_not_called()
