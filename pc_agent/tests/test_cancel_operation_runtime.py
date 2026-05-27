import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pc_agent.core.database import DatabaseManager
from pc_agent.core.orchestrator import AgentOrchestrator
from pc_agent.core.tool_response import ToolMeta
from pc_agent.config.config_loader import ConfigLoader, init_config


def _meta() -> ToolMeta:
    return ToolMeta(
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        command="cancel_operation",
        request_id="req-cancel-runtime",
        module_versions={},
    )


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_cancel_operation_returns_success_when_target_already_finished(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    result = await orchestrator._handle_cancel_operation(
        "op-already-finished",
        _meta(),
    )

    assert result.status == "success"
    assert result.data is not None
    assert result.data.observations["cancel_status"] == "already_finished"
    assert result.data.observations["target_operation_id"] == "op-already-finished"


@pytest.mark.asyncio
async def test_cancel_operation_finalizes_pre_running_seen_command(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    db_path = tmp_path / "storage.db"
    DatabaseManager._instance = None
    db = DatabaseManager(str(db_path))
    await db.init_db()

    target_operation_id = "op-pre-running-cancel"
    await db.mark_command_started(target_operation_id, owner_instance_id="test-session")

    orchestrator = AgentOrchestrator(db_manager=db, enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    result = await orchestrator._handle_cancel_operation(
        target_operation_id,
        _meta(),
        ticket_id="ticket-1",
        device_id="device-1",
    )

    assert result.status == "success"
    assert result.data is not None
    assert result.data.observations["cancel_status"] == "canceled"

    seen = await db.get_command_result(target_operation_id)
    assert seen is not None
    assert seen["status"] == "canceled"
    assert seen["result_json"] is not None
