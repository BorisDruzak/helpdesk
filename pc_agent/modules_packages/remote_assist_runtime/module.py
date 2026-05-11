from __future__ import annotations

from typing import Any, TYPE_CHECKING

from core.registry import exposed_tool
from modules.base_module import BaseCollector

if TYPE_CHECKING:
    from PySide6.QtCore import QThread


RUNTIME_CONTRACT_VERSION = "1.0.0"
MODULE_VERSION = "1.0.1"


def create_remote_assist_thread(**kwargs: Any) -> "QThread":
    """Factory used by pc_agent.remote_assist.runtime_host."""

    # Keep this import lazy so server-side module preflight/smoke can validate
    # metadata without importing Qt/aiortc capture dependencies.
    try:
        from remote_assist_runtime_impl.thread import RemoteAssistThread
    except ModuleNotFoundError:
        from pc_agent.remote_assist.thread import RemoteAssistThread

    return RemoteAssistThread(**kwargs)


class RemoteAssistRuntimeModule(BaseCollector):
    @property
    def name(self) -> str:
        return "remote_assist_runtime"

    async def collect(self) -> dict[str, str]:
        return await self.info()

    @exposed_tool(
        name="info",
        description="Return Remote Assist runtime module metadata",
        risk_level="safe_readonly",
        metadata_risk_level="safe_read",
        metadata_scopes=["remote_assist.runtime"],
        metadata_requires_consent=False,
        metadata_allow_roles=["admin", "support", "agent"],
        metadata_domain="remote_assist",
        metadata_platforms=["win32"],
        metadata_idempotent=True,
        metadata_side_effects=False,
        contract_version="1.0.0",
        output_schema={
            "type": "object",
            "properties": {
                "module_version": {"type": "string"},
                "runtime_contract_version": {"type": "string"},
                "runtime_kind": {"type": "string"},
            },
            "required": ["module_version", "runtime_contract_version", "runtime_kind"],
        },
        output_contract={
            "status_path": "runtime_kind",
            "status_values": ["remote_assist"],
            "success_values": ["remote_assist"],
            "error_values": [],
        },
    )
    async def info(self) -> dict[str, str]:
        with self.trace_span("tool.entry", details={"tool_name": "remote_assist_runtime.info"}):
            return {
                "module_version": MODULE_VERSION,
                "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
                "runtime_kind": "remote_assist",
            }


def register() -> RemoteAssistRuntimeModule:
    return RemoteAssistRuntimeModule()
