from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from web_api.support_handlers import _compose_support_inventory_context


def _detail(*, online: bool = True, operation_status: str = "completed"):
    return SimpleNamespace(
        snapshot=SimpleNamespace(
            device=SimpleNamespace(
                device_id="device-1",
                hostname="pc-01",
                agent_version="4.0.1",
                last_seen_at="2026-05-19T05:00:00+00:00",
                online=online,
            ),
            latest_operations=[
                SimpleNamespace(status=operation_status, display_status=operation_status),
            ],
        )
    )


@pytest.mark.no_db
def test_support_inventory_context_marks_fresh_inventory_and_binding() -> None:
    collected_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    context = _compose_support_inventory_context(
        device_id="device-1",
        detail=_detail(online=True),
        latest=SimpleNamespace(
            id="snapshot-1",
            collected_at=collected_at,
            source_tool="inventory.collect",
            normalized=None,
            snapshot={
                "identity": {"hostname": "pc-01", "current_user": "ivanov"},
                "platform": {"os_name": "Windows", "os_version": "11"},
                "network": {"primary_ip": "192.168.100.54"},
                "resources": {"cpu_percent": 11, "memory_percent": 42},
            },
        ),
        binding={
            "department": "Бухгалтерия",
            "building": "Администрация",
            "room": "214",
            "responsible_user": "Иванова И.И.",
            "status": "active",
            "tags": ["office"],
        },
        policy=SimpleNamespace(enabled=True, next_due_at=collected_at + timedelta(days=1)),
        last_refresh_run=SimpleNamespace(id="run-1", status="dispatched", requested_at=collected_at),
    )

    assert context is not None
    assert context.inventory is not None
    assert context.inventory.freshness == "fresh"
    assert context.inventory.source == "inventory.collect"
    assert context.inventory.summary["primary_ip"] == "192.168.100.54"
    assert context.binding is not None
    assert context.binding.department == "Бухгалтерия"
    assert context.binding.room == "214"
    assert context.agent is not None
    assert context.agent.connection_state == "online"
    assert context.signals is not None
    assert context.signals.agent_offline is False
    assert context.signals.stale_inventory is False
    assert context.signals.missing_inventory is False


@pytest.mark.no_db
def test_support_inventory_context_marks_missing_and_offline_signals() -> None:
    context = _compose_support_inventory_context(
        device_id="device-1",
        detail=_detail(online=False, operation_status="failed"),
        latest=None,
        binding={},
        policy=None,
        last_refresh_run=SimpleNamespace(id="run-1", status="failed", requested_at=datetime.now(timezone.utc)),
    )

    assert context is not None
    assert context.inventory is not None
    assert context.inventory.freshness == "missing"
    assert context.agent is not None
    assert context.agent.connection_state == "offline"
    assert context.signals is not None
    assert context.signals.missing_inventory is True
    assert context.signals.agent_offline is True
    assert context.signals.failed_recent_refresh is True
    assert context.signals.failed_recent_operation is True


@pytest.mark.no_db
def test_support_inventory_context_marks_stale_inventory() -> None:
    context = _compose_support_inventory_context(
        device_id="device-1",
        detail=_detail(online=True),
        latest=SimpleNamespace(
            id="snapshot-old",
            collected_at=datetime.now(timezone.utc) - timedelta(days=10),
            source_tool="inventory.collect",
            normalized={"hostname": "pc-01"},
            snapshot={},
        ),
        binding={},
        policy=None,
        last_refresh_run=None,
    )

    assert context is not None
    assert context.inventory is not None
    assert context.inventory.freshness == "stale"
    assert context.signals is not None
    assert context.signals.stale_inventory is True
