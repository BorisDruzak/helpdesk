import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.orchestrator import AgentOrchestrator
from core.registry import exposed_tool
from core.tool_response import ToolMeta
from pc_agent.core.action_trace import configure_action_trace, search_action_trace
from pc_agent.config.config_loader import ConfigLoader, init_config
from modules.base_module import BaseCollector


def _meta(command: str = "run_tool", trace_id: str | None = None) -> ToolMeta:
    meta = ToolMeta(
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        command=command,
        request_id="req-runtime-envelope",
        module_versions={},
    )
    if trace_id:
        meta.__dict__["trace_id"] = trace_id
    return meta


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_run_tool_returns_canonical_execution_envelope(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(
        enabled_modules=["system"],
        data_root=tmp_path,
    )
    await orchestrator.initialize()

    result = await orchestrator._handle_run_tool(
        tool="system.collect",
        params={"tool": "system.collect", "params": {"preset": "minimal"}},
        actor_role="admin",
        meta=_meta(),
    )

    assert result.status == "success"
    assert result.data is not None
    assert isinstance(result.data.result, dict)
    envelope = result.data.result
    assert envelope["status"] == "ok"
    assert envelope["output"]["preset"] == "minimal"
    assert envelope["metrics"]["request_id"] == "req-runtime-envelope"
    assert envelope["changed"] is False


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_builtin_specs_expose_contract_fields(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(
        enabled_modules=["system", "screen"],
        data_root=tmp_path,
    )
    await orchestrator.initialize()

    screen_tool = orchestrator.registry.get_tool("screen.collect")
    system_tool = orchestrator.registry.get_tool("system.collect")

    assert screen_tool is not None
    assert system_tool is not None
    assert screen_tool["spec"]["artifact_types"][0]["kind"] == "screenshot"
    assert screen_tool["spec"]["resources"]["max_artifact_count"] == 1
    assert system_tool["spec"]["contract_version"] == "1.0.0"
    assert system_tool["spec"]["lifecycle"] == "stable"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_run_tool_redacts_sensitive_output_fields(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    class RedactionCollector:
        @property
        def name(self) -> str:
            return "custom"

        @exposed_tool(
            name="custom.inspect",
            description="Inspect and redact",
            metadata_risk_level="safe_read",
            metadata_allow_roles=["admin"],
            redaction={"redact_fields": ["proxy_authorization", "token"]},
            resources={"max_runtime_sec": 5},
        )
        async def run(self):
            return {
                "ok": True,
                "proxy_authorization": "Basic secret",
                "nested": {"token": "top-secret"},
            }

    collector = RedactionCollector()
    orchestrator.loaded_modules.append(collector)
    orchestrator.registry.register(collector)

    result = await orchestrator._handle_run_tool(
        tool="custom.inspect",
        params={"tool": "custom.inspect", "params": {}},
        actor_role="admin",
        meta=_meta(),
    )

    assert result.status == "success"
    envelope = result.data.result
    assert envelope["status"] == "ok"
    assert envelope["output"]["proxy_authorization"] == "***REDACTED***"
    assert envelope["output"]["nested"]["token"] == "***REDACTED***"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_run_tool_blocks_when_required_binary_is_missing(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    class DependencyCollector:
        @property
        def name(self) -> str:
            return "custom"

        @exposed_tool(
            name="custom.inspect",
            description="Inspect dependencies",
            metadata_risk_level="safe_read",
            metadata_allow_roles=["admin"],
            dependencies={"required_binaries": ["definitely_missing_binary_for_test"]},
            resources={"max_runtime_sec": 5},
        )
        async def run(self):
            return {"ok": True}  # pragma: no cover - blocked by dependency gate

    collector = DependencyCollector()
    orchestrator.loaded_modules.append(collector)
    orchestrator.registry.register(collector)

    result = await orchestrator._handle_run_tool(
        tool="custom.inspect",
        params={"tool": "custom.inspect", "params": {}},
        actor_role="admin",
        meta=_meta(),
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error.code == "DEPENDENCY_MISSING"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_run_tool_normalizes_partial_metadata_before_policy(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    class PartialMetadataCollector:
        @property
        def name(self) -> str:
            return "custom"

        @exposed_tool(
            name="custom.partial_metadata",
            description="Tool with partially populated metadata",
            metadata_risk_level="safe_read",
            metadata_allow_roles=["agent"],
        )
        async def run(self):
            return {"ok": True, "path": "normalized"}

    collector = PartialMetadataCollector()
    orchestrator.loaded_modules.append(collector)
    orchestrator.registry.register(collector)
    tool_spec = orchestrator.registry.get_tool("custom.partial_metadata")
    assert tool_spec is not None
    tool_spec["spec"]["metadata"]["origin"] = None

    result = await orchestrator._handle_run_tool(
        tool="custom.partial_metadata",
        params={"tool": "custom.partial_metadata", "params": {}},
        actor_role="agent",
        meta=_meta(),
    )

    assert result.status == "success"
    envelope = result.data.result
    assert envelope["status"] == "ok"
    assert envelope["output"]["path"] == "normalized"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_run_tool_emits_module_level_action_trace_breakdown(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)
    configure_action_trace(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    class TraceCollector:
        @property
        def name(self) -> str:
            return "custom"

        @exposed_tool(
            name="custom.traceable",
            description="Traceable custom tool",
            metadata_risk_level="safe_read",
            metadata_allow_roles=["admin"],
            resources={"max_runtime_sec": 5},
        )
        async def run(self, value: int = 1):
            return {"ok": True, "value": value}

    collector = TraceCollector()
    orchestrator.loaded_modules.append(collector)
    orchestrator.registry.register(collector)

    result = await orchestrator._handle_run_tool(
        tool="custom.traceable",
        params={"tool": "custom.traceable", "ticket_id": "ticket-traceable", "params": {"value": 7}},
        actor_role="admin",
        meta=_meta(trace_id="trace-runtime-envelope"),
    )

    assert result.status == "success"
    rows = search_action_trace(limit=20, operation_id="req-runtime-envelope", ticket_id="ticket-traceable")
    assert rows
    trace_rows = search_action_trace(limit=20, trace_id="trace-runtime-envelope")
    assert trace_rows
    assert all(row["trace_id"] == "trace-runtime-envelope" for row in trace_rows)
    assert any(
        row["stage"] == "module.resolve"
        and row.get("details", {}).get("module_name") == "custom"
        and row.get("details", {}).get("method_name") == "run"
        for row in rows
    )
    assert any(
        row["action"] == "module.execute"
        and row["stage"] == "finish"
        and row["status"] == "ok"
        and row.get("details", {}).get("module_name") == "custom"
        for row in rows
    )


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_run_tool_emits_nested_module_sdk_steps(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)
    configure_action_trace(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    class InstrumentedCollector(BaseCollector):
        @property
        def name(self) -> str:
            return "custom"

        @exposed_tool(
            name="custom.instrumented",
            description="Tool with nested module trace steps",
            metadata_risk_level="safe_read",
            metadata_allow_roles=["admin"],
            resources={"max_runtime_sec": 5},
        )
        async def collect(self):
            with self.trace_span("resolve", details={"phase": "resolve"}):
                pass
            self.trace_event("emit", summary="post-resolve event", details={"phase": "emit"})
            return {"ok": True}

    collector = InstrumentedCollector()
    orchestrator.loaded_modules.append(collector)
    orchestrator.registry.register(collector)

    result = await orchestrator._handle_run_tool(
        tool="custom.instrumented",
        params={"tool": "custom.instrumented", "ticket_id": "ticket-module-sdk", "params": {}},
        actor_role="admin",
        meta=_meta(),
    )

    assert result.status == "success"
    rows = search_action_trace(limit=30, operation_id="req-runtime-envelope", ticket_id="ticket-module-sdk")
    nested_rows = [row for row in rows if row["action"] == "module.step"]
    assert nested_rows
    assert any(
        row["stage"] == "finish"
        and row["status"] == "ok"
        and row.get("details", {}).get("step") == "resolve"
        and row.get("details", {}).get("module_name") == "custom"
        for row in nested_rows
    )
    assert any(
        row["stage"] == "event"
        and row.get("details", {}).get("step") == "emit"
        for row in nested_rows
    )
