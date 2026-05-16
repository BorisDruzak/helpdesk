import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pc_agent.core.orchestrator import AgentOrchestrator
from pc_agent.core.tool_response import ToolMeta
from pc_agent.config.config_loader import ConfigLoader, init_config


def _meta() -> ToolMeta:
    return ToolMeta(
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        command="install_module_package",
        module_versions={},
    )


@pytest.mark.asyncio
async def test_install_builtin_module_package_is_noop(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(
        enabled_modules=["system", "screen"],
        data_root=tmp_path,
    )

    result = await orchestrator._handle_install_module_package(
        name="screen",
        version="1.0.0",
        package_b64=None,
        download_url="http://example.invalid/screen.zip",
        sha256="deadbeef",
        size=123,
        actor_role="admin",
        meta=_meta(),
    )

    assert result.status == "success"
    assert result.data is not None
    assert result.data.observations["skipped"] is True
    assert result.data.observations["reason"] == "builtin_module"
