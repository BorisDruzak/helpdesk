import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pc_agent.core.orchestrator import AgentOrchestrator
from pc_agent.core.registry import exposed_tool
from pc_agent.core.tool_response import ToolMeta
from pc_agent.config.config_loader import ConfigLoader, init_config


def _meta(request_id: str, command: str = "run_tool") -> ToolMeta:
    return ToolMeta(
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        command=command,
        request_id=request_id,
        module_versions={},
    )


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_system_write_run_tool_is_serialized(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    class SerialCollector:
        def __init__(self) -> None:
            self.first_started = asyncio.Event()
            self.first_release = asyncio.Event()
            self.second_started = asyncio.Event()

        @property
        def name(self) -> str:
            return "custom"

        @exposed_tool(
            name="custom.serial_write",
            description="Serialized write lane",
            metadata_risk_level="system_write",
            metadata_allow_roles=["admin"],
            metadata_side_effects=True,
            resources={"max_runtime_sec": 5},
        )
        async def run(self, label: str):
            if label == "first":
                self.first_started.set()
                await self.first_release.wait()
            elif label == "second":
                self.second_started.set()
            return {"label": label}

    collector = SerialCollector()
    orchestrator.loaded_modules.append(collector)
    orchestrator.registry.register(collector)

    first_task = asyncio.create_task(
        orchestrator.handle_command(
            {
                "cmd": "run_tool",
                "tool": "custom.serial_write",
                "params": {"label": "first"},
                "actor_role": "admin",
                "request_id": "op-serial-1",
            }
        )
    )
    await asyncio.wait_for(collector.first_started.wait(), timeout=1.0)

    second_task = asyncio.create_task(
        orchestrator.handle_command(
            {
                "cmd": "run_tool",
                "tool": "custom.serial_write",
                "params": {"label": "second"},
                "actor_role": "admin",
                "request_id": "op-serial-2",
            }
        )
    )

    await asyncio.sleep(0.05)
    assert not collector.second_started.is_set()

    collector.first_release.set()
    first_result, second_result = await asyncio.gather(first_task, second_task)

    assert first_result["status"] == "success"
    assert second_result["status"] == "success"
    assert collector.second_started.is_set()


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_cancel_operation_can_cancel_queued_run_tool_before_execution(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    class SerialCollector:
        def __init__(self) -> None:
            self.first_started = asyncio.Event()
            self.first_release = asyncio.Event()
            self.second_started = asyncio.Event()

        @property
        def name(self) -> str:
            return "custom"

        @exposed_tool(
            name="custom.cancelable_write",
            description="Cancelable queued write lane",
            metadata_risk_level="system_write",
            metadata_allow_roles=["admin"],
            metadata_side_effects=True,
            resources={"max_runtime_sec": 5},
        )
        async def run(self, label: str):
            if label == "first":
                self.first_started.set()
                await self.first_release.wait()
            elif label == "second":
                self.second_started.set()
            return {"label": label}

    collector = SerialCollector()
    orchestrator.loaded_modules.append(collector)
    orchestrator.registry.register(collector)

    first_task = asyncio.create_task(
        orchestrator.handle_command(
            {
                "cmd": "run_tool",
                "tool": "custom.cancelable_write",
                "params": {"label": "first"},
                "actor_role": "admin",
                "request_id": "op-cancel-1",
            }
        )
    )
    await asyncio.wait_for(collector.first_started.wait(), timeout=1.0)

    second_task = asyncio.create_task(
        orchestrator.handle_command(
            {
                "cmd": "run_tool",
                "tool": "custom.cancelable_write",
                "params": {"label": "second"},
                "actor_role": "admin",
                "request_id": "op-cancel-2",
            }
        )
    )
    await asyncio.sleep(0.05)
    assert not collector.second_started.is_set()

    cancel_result = await orchestrator._handle_cancel_operation(
        "op-cancel-2",
        _meta("req-cancel-queued", command="cancel_operation"),
    )

    assert cancel_result.status == "success"
    assert cancel_result.data is not None
    assert cancel_result.data.observations["target_operation_id"] == "op-cancel-2"
    assert cancel_result.data.observations["cancel_status"] == "canceled"

    with pytest.raises(asyncio.CancelledError):
        await second_task

    assert not collector.second_started.is_set()
    collector.first_release.set()
    first_result = await first_task
    assert first_result["status"] == "success"
