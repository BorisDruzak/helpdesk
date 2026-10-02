"""Permanent production-source and real route guard for the device cutover."""
from pathlib import Path
import re
import pytest
from aiohttp import web
from routes import setup_routes

pytestmark = pytest.mark.no_db
ROOT = Path(__file__).resolve().parents[2]


def test_browser_production_sources_cannot_call_retired_device_apis():
    forbidden = ("connection_requests", "connection_policy", "device-tokens", "inventory/bulk-refresh",
        "/inventory/collect", "/presence/collect", "/api/web/admin/modules", "/api/web/admin/devices", "/api/web/admin/inventory")
    failures = []
    sources = list((ROOT / "webapp/src").rglob("*.ts")) + list((ROOT / "webapp/src").rglob("*.tsx"))
    assert sources
    for path in sources:
        if ".test." in path.name:
            continue
        text = path.read_text(encoding="utf-8")
        failures.extend(f"{path.relative_to(ROOT)}: {pattern}" for pattern in forbidden if pattern in text)
    assert not failures, "\n".join(failures)


def test_production_runtime_does_not_read_or_write_retired_telemetry_models():
    names = ("DeviceInventorySnapshot", "DeviceInventoryBinding", "DeviceInventoryBindingHistory", "DeviceInventoryRefreshPolicy",
        "DeviceInventoryRefreshRun", "DeviceInventoryBulkOperation", "DeviceInventoryBulkOperationItem", "DeviceBindingSuggestion",
        "DevicePresenceSnapshot", "DevicePresenceDailySummary")
    retired_tables = ("device_inventory_snapshots", "device_inventory_bindings", "device_inventory_binding_history",
        "device_inventory_refresh_policies", "device_inventory_refresh_runs", "device_inventory_bulk_operations",
        "device_inventory_bulk_operation_items", "device_binding_suggestions", "device_presence_snapshots", "device_presence_daily_summaries")
    names = names + retired_tables
    pattern = re.compile(r"\b(?:" + "|".join(names) + r")\b")
    failures = []
    for path in (ROOT / "server").rglob("*.py"):
        relative = path.relative_to(ROOT / "server")
        if "tests" in relative.parts or "alembic" in relative.parts or "migrations" in relative.parts or relative.as_posix() == "app/db/models.py":
            continue
        if pattern.search(path.read_text(encoding="utf-8")) or any(value in path.read_text(encoding="utf-8") for value in ("from inventory.service", "from presence.service", "from web_api.admin_inventory_handlers")):
            failures.append(relative.as_posix())
    assert not failures, "Runtime legacy models: " + ", ".join(failures)


def test_retired_inventory_routes_are_absent_from_the_real_app():
    app = web.Application()
    setup_routes(app)
    paths = {resource.canonical for resource in app.router.resources()}
    assert not any(path.startswith("/api/web/admin/inventory") or path.startswith("/api/web/admin/devices") for path in paths)
    assert "/api/web/admin/endpoint/devices/{device_id}" in paths
    assert "/api/web/admin/endpoint/devices" in paths
    assert {
        "/api/web/admin/endpoint/devices/{device_id}/context/refresh",
        "/api/web/admin/endpoint/context/collections/{collection_id}",
        "/api/web/admin/endpoint/devices/{device_id}/context/history",
        "/api/web/admin/endpoint/devices/{device_id}/context/compare",
    } <= paths


def test_observer_connection_guidance_does_not_read_local_technical_state():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from web_api.admin_handlers import _observer_next_actions

    device = SimpleNamespace(last_handshake_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    actions = _observer_next_actions(error_code="AGENT_NOT_CONNECTED", device=device)
    assert "Проверить подключение агента" in actions
    assert not any("handshake" in action.lower() or "2026-01-01" in action for action in actions)


def test_approval_device_links_do_not_treat_local_operation_ids_as_endpoint_ids():
    source = (ROOT / "server/approvals/service.py").read_text(encoding="utf-8")
    assert "device={operation.device_id}" not in source


def test_retired_agent_and_scheduler_configuration_cannot_be_reintroduced():
    names = ("AGENT_BUILTIN_MODULES", "INVENTORY_REFRESH_SCHEDULER_ENABLED",
             "INVENTORY_REFRESH_SCHEDULER_INTERVAL_SEC", "INVENTORY_REFRESH_SCHEDULER_INTERVAL_SECONDS")
    sources = [ROOT / "server/.env.example"]
    sources += [path for path in (ROOT / "server").rglob("*.py")
                if not {"tests", "migrations", "alembic"}.intersection(path.relative_to(ROOT / "server").parts)]
    failures = [f"{path.relative_to(ROOT)}: {name}" for path in sources
                for name in names if name in path.read_text(encoding="utf-8")]
    assert not failures, "\n".join(failures)


def test_retired_collection_descriptors_have_no_production_registration_or_dispatch():
    # Historical schema defaults remain inert; tests, migrations and evidence
    # are deliberately outside the runtime source boundary.
    forbidden = ("builtin_tool_descriptors", "inventory.collect", "presence.collect")
    sources = []
    for directory in ("server", "shared"):
        for path in (ROOT / directory).rglob("*.py"):
            relative = path.relative_to(ROOT)
            if {"tests", "migrations", "alembic", "__pycache__"}.intersection(relative.parts):
                continue
            if relative.as_posix() == "server/app/db/models.py":
                continue
            sources.append(path)
    failures = [f"{path.relative_to(ROOT)}: {name}" for path in sources
                for name in forbidden if name in path.read_text(encoding="utf-8")]
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("age_days", [0, 365])
def test_tech_locator_never_derives_presence_from_local_timestamps(age_days):
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from tech.locator import _device_match

    timestamp = datetime.now(timezone.utc) - timedelta(days=age_days)
    device = SimpleNamespace(device_id="historical-device", hostname="Historical host",
                             last_seen_at=timestamp, last_handshake_at=timestamp)
    match = _device_match(None, device, failed_count=0, stuck_count=0)
    assert match["status"] == "unknown"
    assert match["context"]["agent_online"] is None
    assert not match["signals"].get("agent_offline")
    assert not match["signals"].get("stale_agent")


@pytest.mark.parametrize("age_days", [0, 365])
def test_command_center_never_derives_presence_from_local_telemetry(age_days):
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from support.operator_command_center import _agent_state

    now = datetime.now(timezone.utc)
    device = SimpleNamespace(last_seen_at=now - timedelta(days=age_days))
    ticket = {"device_id": "historical-device", "custom_fields": {
        "inventory_context": {"signals": {"agent_offline": True}}}}
    state = _agent_state(ticket, device, now)
    assert state.connection_state == "unknown"
    assert state.last_seen_at is None
