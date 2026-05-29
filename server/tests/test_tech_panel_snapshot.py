from __future__ import annotations

from datetime import datetime, timezone

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from auth.context import AuthContext, AuthType
from routes import setup_routes


def _sample_snapshot() -> dict:
    return {
        "generated_at": "2026-05-21T08:00:00+00:00",
        "readiness": {"status": "blocked", "score": 40, "blockers": [], "warnings": [], "gates": []},
        "security": {},
        "runtime": {},
        "database": {},
        "agents": {},
        "operations": {},
        "observer_integrity": {},
        "logs": {},
        "alerts": [],
        "release": {},
        "smoke": {"status": "unknown"},
        "links": {
            "observer": "/app/admin/observer",
            "inventory": "/app/admin/inventory",
            "device_operations": "/app/admin/device-operations",
            "agent_updates": "/app/admin/agent-updates",
            "command_center": "/app/support",
            "approval_center": "/app/support/approvals",
            "logs": "/app/admin/tech?tab=logs",
        },
    }


def _app_with_role(role: str | None):
    middlewares = []
    if role:
        @web.middleware
        async def auth_context_middleware(request, handler):
            request["auth_context"] = AuthContext(
                actor_id=f"{role}-1",
                actor_role=role,
                auth_type=AuthType.UI_TOKEN,
                token="test-token",
            )
            return await handler(request)

        middlewares.append(auth_context_middleware)
    app = web.Application(middlewares=middlewares)
    setup_routes(app)
    return app


@pytest.fixture
def snapshot_handler_patch(monkeypatch):
    from tech import handlers as tech_handlers

    async def fake_overview(_request):
        return {"postgres_health": {"reachable": True}}

    async def fake_snapshot(_request, _overview):
        return _sample_snapshot()

    monkeypatch.setattr(tech_handlers, "_build_overview", fake_overview)
    monkeypatch.setattr(tech_handlers, "build_tech_panel_v2_snapshot", fake_snapshot)


@pytest.mark.no_db
async def test_tech_panel_snapshot_contract(snapshot_handler_patch):
    async with TestClient(TestServer(_app_with_role("admin"))) as client:
        response = await client.get("/api/web/admin/tech/snapshot")
        payload = await response.json()

    assert response.status == 200
    assert {
        "generated_at",
        "readiness",
        "security",
        "runtime",
        "database",
        "agents",
        "operations",
        "observer_integrity",
        "logs",
        "alerts",
        "release",
        "smoke",
        "links",
    }.issubset(payload.keys())


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("role", "expected_status"),
    [
        (None, 401),
        ("requester", 403),
        ("user", 403),
        ("support", 200),
        ("admin", 200),
        ("auditor", 200),
    ],
)
async def test_tech_panel_snapshot_permissions(snapshot_handler_patch, role, expected_status):
    async with TestClient(TestServer(_app_with_role(role))) as client:
        response = await client.get("/api/web/admin/tech/snapshot")
    assert response.status == expected_status


@pytest.mark.no_db
def test_readiness_gate_blocks_when_db_persistence_disabled():
    from tech.snapshot import aggregate_readiness, build_readiness_gates

    gates = build_readiness_gates(
        config_values={
            "ENABLE_DB_PERSISTENCE": False,
            "PILOT_STAND_MODE": True,
            "AUTH_UI_CONFIG_FALLBACK_ENABLED": False,
            "AUTH_ALLOW_QUERY_TOKEN": False,
            "REQUIRE_HTTPS": True,
            "REQUIRE_WSS": True,
            "WEB_SESSION_COOKIE_SECURE": True,
            "WEB_SESSION_COOKIE_HTTPONLY": True,
            "WEB_SESSION_COOKIE_SAMESITE": "lax",
            "PILOT_MIN_AGENT_VERSION": "2.0.0",
        },
        database={"reachable": True, "migrations_status": "ok", "last_restore_drill": {"status": "success"}},
        security={"agent_connection_policy": {"mode": "manual", "status": "ok"}},
        runtime={"schedulers": {"inventory_scheduler": "running"}},
        agents={"below_baseline": 0},
        smoke={"status": "ok", "last_business_smoke": {"status": "success"}},
    )

    gate = next(item for item in gates if item["key"] == "db_persistence_enabled")
    assert gate["status"] == "blocked"
    assert aggregate_readiness(gates)["status"] == "blocked"


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("config_key", "expected_gate"),
    [
        ("AUTH_UI_CONFIG_FALLBACK_ENABLED", "auth_no_dev_fallback"),
        ("AUTH_ALLOW_QUERY_TOKEN", "query_token_disabled"),
    ],
)
def test_pilot_auth_policy_gates_block_for_unsafe_fallbacks(config_key, expected_gate):
    from tech.snapshot import build_readiness_gates

    config_values = {
        "ENABLE_DB_PERSISTENCE": True,
        "PILOT_STAND_MODE": True,
        "AUTH_UI_CONFIG_FALLBACK_ENABLED": False,
        "AUTH_ALLOW_QUERY_TOKEN": False,
        "REQUIRE_HTTPS": True,
        "REQUIRE_WSS": True,
        "WEB_SESSION_COOKIE_SECURE": True,
        "WEB_SESSION_COOKIE_HTTPONLY": True,
        "WEB_SESSION_COOKIE_SAMESITE": "lax",
        "PILOT_MIN_AGENT_VERSION": "2.0.0",
    }
    config_values[config_key] = True

    gates = build_readiness_gates(
        config_values=config_values,
        database={"reachable": True, "migrations_status": "ok", "last_restore_drill": {"status": "success"}},
        security={"agent_connection_policy": {"mode": "manual", "status": "ok"}},
        runtime={"schedulers": {"inventory_scheduler": "running"}},
        agents={"below_baseline": 0},
        smoke={"status": "ok", "last_business_smoke": {"status": "success"}},
    )

    gate = next(item for item in gates if item["key"] == expected_gate)
    assert gate["status"] == "blocked"


@pytest.mark.no_db
def test_app_env_pilot_blocks_readiness_without_legacy_pilot_flag():
    from tech.snapshot import build_readiness_gates

    gates = build_readiness_gates(
        config_values={
            "APP_ENV": "pilot",
            "ENABLE_DB_PERSISTENCE": True,
            "PILOT_STAND_MODE": False,
            "AUTH_UI_CONFIG_FALLBACK_ENABLED": False,
            "AUTH_ALLOW_QUERY_TOKEN": False,
            "REQUIRE_HTTPS": False,
            "REQUIRE_WSS": False,
            "WEB_SESSION_COOKIE_SECURE": False,
            "WEB_SESSION_COOKIE_HTTPONLY": True,
            "WEB_SESSION_COOKIE_SAMESITE": "lax",
            "PILOT_MIN_AGENT_VERSION": "2.0.0",
        },
        database={"reachable": True, "migrations_status": "ok", "last_restore_drill": {"status": "success"}},
        security={"agent_connection_policy": {"mode": "manual", "status": "ok"}},
        runtime={"schedulers": {"inventory_scheduler": "disabled"}},
        agents={"below_baseline": 0},
        smoke={"status": "ok", "last_business_smoke": {"status": "success"}},
    )

    assert next(item for item in gates if item["key"] == "https_wss_required")["status"] == "blocked"
    assert next(item for item in gates if item["key"] == "session_cookie_flags")["status"] == "blocked"


@pytest.mark.no_db
def test_restore_drill_is_not_blocking_until_required():
    from tech.snapshot import build_readiness_gates

    gates = build_readiness_gates(
        config_values={
            "APP_ENV": "pilot",
            "ENABLE_DB_PERSISTENCE": True,
            "PILOT_STAND_MODE": False,
            "AUTH_UI_CONFIG_FALLBACK_ENABLED": False,
            "AUTH_ALLOW_QUERY_TOKEN": False,
            "REQUIRE_HTTPS": True,
            "REQUIRE_WSS": True,
            "WEB_SESSION_COOKIE_SECURE": True,
            "WEB_SESSION_COOKIE_HTTPONLY": True,
            "WEB_SESSION_COOKIE_SAMESITE": "lax",
            "PILOT_MIN_AGENT_VERSION": "2.0.0",
            "REQUIRE_BACKUP_RESTORE_EVIDENCE": False,
        },
        database={"reachable": True, "migrations_status": "ok", "last_restore_drill": None},
        security={"agent_connection_policy": {"mode": "manual", "status": "ok"}},
        runtime={"schedulers": {"inventory_scheduler": "disabled"}},
        agents={"below_baseline": 0},
        smoke={"status": "ok", "last_business_smoke": {"status": "success"}},
    )

    gate = next(item for item in gates if item["key"] == "backup_restore_drill")
    assert gate["status"] == "ok"
    assert "required=false" in gate["evidence"]


@pytest.mark.no_db
def test_postgres_unreachable_becomes_controlled_blocker():
    from tech.snapshot import build_database_snapshot_from_overview, build_readiness_gates

    database = build_database_snapshot_from_overview(
        {
            "postgres_health": {
                "reachable": False,
                "latency_ms": None,
                "database": "pc_client",
                "pool_status": None,
                "error": "password secret-value failed",
            }
        }
    )
    gates = build_readiness_gates(
        config_values={"ENABLE_DB_PERSISTENCE": True, "PILOT_STAND_MODE": True},
        database=database,
        security={"agent_connection_policy": {"mode": "manual", "status": "ok"}},
        runtime={"schedulers": {"inventory_scheduler": "unknown"}},
        agents={"below_baseline": None},
        smoke={"status": "unknown", "last_business_smoke": None},
    )

    assert database["reachable"] is False
    assert "secret-value" not in str(database)
    assert next(item for item in gates if item["key"] == "postgres_reachable")["status"] == "blocked"


@pytest.mark.no_db
def test_missing_marker_files_are_unknown_without_crash(tmp_path):
    from tech.snapshot import build_release_snapshot, build_smoke_snapshot

    missing = str(tmp_path / "missing.json")
    release = build_release_snapshot({"TECH_RELEASE_STATUS_PATH": missing})
    smoke = build_smoke_snapshot({"TECH_BUSINESS_SMOKE_STATUS_PATH": missing})

    assert release["gate"] == "unknown"
    assert smoke["status"] == "unknown"
    assert smoke["last_business_smoke"] is None


@pytest.mark.no_db
def test_marker_and_snapshot_payloads_do_not_expose_raw_secrets(tmp_path):
    from tech.snapshot import build_release_snapshot

    marker = tmp_path / "release.json"
    marker.write_text(
        '{"branch":"main","commit":"abc","database_url":"postgresql://user:password@host/db","token":"raw-token"}',
        encoding="utf-8",
    )

    payload = build_release_snapshot({"TECH_RELEASE_STATUS_PATH": str(marker)})
    dumped = str(payload)
    assert "password" not in dumped
    assert "raw-token" not in dumped
    assert "database_url" not in dumped


@pytest.mark.no_db
def test_readiness_aggregation_warning_only_is_degraded_and_all_ok_is_ready():
    from tech.snapshot import aggregate_readiness

    warning = [
        {"key": "a", "status": "ok", "severity": "info"},
        {"key": "b", "status": "warning", "severity": "warning"},
    ]
    ok = [{"key": "a", "status": "ok", "severity": "info"}]

    assert aggregate_readiness(warning)["status"] == "degraded"
    assert aggregate_readiness(ok)["status"] == "ready"


@pytest.mark.no_db
def test_query_token_attempt_counter_tracks_rejected_attempts_without_token(monkeypatch):
    from types import SimpleNamespace

    import config
    import auth.middleware as middleware

    middleware.reset_query_token_auth_attempts()
    monkeypatch.setattr(config, "AUTH_ALLOW_QUERY_TOKEN", False)

    request = SimpleNamespace(query={"token": "raw-secret-token"}, headers={}, path="/api/web/admin/tech/snapshot")
    assert middleware.extract_token_from_header(request) is None

    assert middleware.get_query_token_auth_attempts(window_seconds=3600) == 1
    paths = middleware.get_recent_query_token_auth_paths(limit=5)
    assert paths == [
        {
            "path": "/api/web/admin/tech/snapshot",
            "rejected": True,
            "ts": paths[0]["ts"],
        }
    ]
    assert "raw-secret-token" not in str(paths)


@pytest.mark.no_db
async def test_security_snapshot_includes_query_token_attempt_count(monkeypatch):
    import auth.middleware as middleware
    from tech.snapshot import build_security_snapshot

    middleware.reset_query_token_auth_attempts()
    monkeypatch.setattr(middleware, "get_query_token_auth_attempts", lambda window_seconds=3600: 3)

    snapshot = await build_security_snapshot(
        {"audit_counters": {}, "agent_health": {}},
        {
            "AUTH_UI_DB_USERS_ENABLED": True,
            "AUTH_UI_CONFIG_FALLBACK_ENABLED": False,
            "AUTH_ALLOW_QUERY_TOKEN": False,
            "WEB_SESSION_COOKIE_SECURE": True,
            "WEB_SESSION_COOKIE_HTTPONLY": True,
            "WEB_SESSION_COOKIE_SAMESITE": "lax",
        },
        database_reachable=False,
    )

    assert snapshot["token_channels"]["query_token_attempts_recent"] == 3


@pytest.mark.no_db
def test_inventory_scheduler_duplicate_status_affects_gate():
    from tech.snapshot import build_readiness_gates

    gates = build_readiness_gates(
        config_values={
            "ENABLE_DB_PERSISTENCE": True,
            "PILOT_STAND_MODE": True,
            "AUTH_UI_CONFIG_FALLBACK_ENABLED": False,
            "AUTH_ALLOW_QUERY_TOKEN": False,
            "REQUIRE_HTTPS": True,
            "REQUIRE_WSS": True,
            "WEB_SESSION_COOKIE_SECURE": True,
            "WEB_SESSION_COOKIE_HTTPONLY": True,
            "WEB_SESSION_COOKIE_SAMESITE": "lax",
            "PILOT_MIN_AGENT_VERSION": "3.1.50",
        },
        database={"reachable": True, "migrations_status": "ok", "last_restore_drill": {"status": "success"}},
        security={"agent_connection_policy": {"mode": "manual", "status": "ok"}},
        runtime={
            "schedulers": {"inventory_scheduler": "running"},
            "scheduler_details": {
                "inventory_scheduler": {
                    "enabled": True,
                    "running": True,
                    "active_task_count": 2,
                    "duplicate_task_detected": True,
                }
            },
        },
        agents={"below_baseline": 0},
        smoke={"status": "ok", "last_business_smoke": {"status": "success"}},
    )

    gate = next(item for item in gates if item["key"] == "inventory_scheduler_health")
    assert gate["status"] == "blocked"
    assert "duplicate" in (gate["evidence"] or "")


@pytest.mark.no_db
def test_agent_baseline_excludes_pending_stubs_and_non_numeric_canaries():
    from tech.snapshot import _is_agent_baseline_candidate

    assert _is_agent_baseline_candidate(protocol_version="pending", agent_version="") is False
    assert _is_agent_baseline_candidate(protocol_version="ws_ticket_v3", agent_version="observer-canary") is False
    assert _is_agent_baseline_candidate(protocol_version="ws_ticket_v3", agent_version="3.1.19") is True
