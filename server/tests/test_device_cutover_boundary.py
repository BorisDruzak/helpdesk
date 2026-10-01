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
