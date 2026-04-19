from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pc_agent.config.config_loader import init_config
from core.orchestrator import AgentOrchestrator


class _FakeDbManager:
    async def init_db(self) -> None:
        return None


@pytest.mark.asyncio
async def test_orchestrator_emits_startup_inventory_sync(tmp_path):
    init_config(tmp_path)
    orchestrator = AgentOrchestrator(
        db_manager=_FakeDbManager(),
        enabled_modules=[],
        agent_uuid="device-startup-sync",
        data_root=tmp_path,
    )
    emit_mock = AsyncMock()
    orchestrator._emit_module_state_changed = emit_mock

    await orchestrator.initialize()

    emit_mock.assert_awaited_once()
    assert emit_mock.await_args.kwargs["reason"] == "startup_inventory_sync"
