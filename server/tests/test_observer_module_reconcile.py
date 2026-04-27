from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from app.db import get_session
from app.db.models import AgentRuntimeAudit, Device, DeviceDesiredModule
from modules.reconcile import reconcile_device
from observer.service import ObserverOverlayService, TraceOverlayFilters


@pytest.mark.asyncio
async def test_module_reconcile_missing_registry_writes_searchable_observer_audit() -> None:
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000aa01"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.16",
                hostname="reconcile-observer-host",
                os="linux",
                capabilities=[],
                tools_version="observer-reconcile",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now,
            )
        )
        session.add(
            DeviceDesiredModule(
                device_id=device_id,
                module_name="missing.registry.module",
                desired_version="1.2.3",
                desired_sha256=None,
                state="installed",
                reason="test",
                updated_by="pytest",
            )
        )
        await session.commit()

    async with get_session() as session:
        stats = await reconcile_device(device_id, state=SimpleNamespace(), session=session, reason="pytest")
        await session.commit()

    assert stats["skipped"] == 1

    async with get_session() as session:
        audit = (
            await session.execute(
                sa.select(AgentRuntimeAudit)
                .where(AgentRuntimeAudit.device_id == device_id)
                .order_by(AgentRuntimeAudit.id.desc())
            )
        ).scalar_one()
        assert audit.event_type == "module_reconcile_failed"
        assert audit.severity == "warning"
        assert audit.details_json["stage"] == "reconcile"
        assert audit.details_json["module_name"] == "missing.registry.module"
        assert audit.details_json["error_kind"] == "MODULE_REGISTRY_MISSING"

        trace_ids = await ObserverOverlayService(session)._candidate_trace_ids(
            TraceOverlayFilters(query="reconcile", root_kind="module_reconcile", device_id=device_id),
            limit=10,
        )
        assert trace_ids
        trace = await ObserverOverlayService(session).project_trace(trace_ids[0], force=True)
        await session.commit()

    assert trace is not None
    assert trace.root_kind == "module_reconcile"
