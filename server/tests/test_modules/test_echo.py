"""Test tool: echo(message) -> {"echo": message}"""
import sys
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel

# Add pc_agent to path if not already there
# server/tests/test_modules/test_echo.py -> server/tests -> server -> root -> pc_agent
pc_agent_dir = Path(__file__).resolve().parent.parent.parent.parent / "pc_agent"
if not pc_agent_dir.exists():
    # Try alternative path: might be running from different location
    pc_agent_dir = Path(__file__).resolve().parent.parent.parent / "pc_agent"
if pc_agent_dir.exists() and str(pc_agent_dir) not in sys.path:
    sys.path.insert(0, str(pc_agent_dir))

from modules.base_module import BaseCollector
from core.registry import exposed_tool


class EchoParams(BaseModel):
    message: str = ""


class TestEchoModule(BaseCollector):
    """Тестовый модуль для echo tool."""
    
    @property
    def name(self) -> str:
        return "test_echo"
    
    @exposed_tool(
        name="echo",
        description="Echo test tool - returns input message",
        risk_level="safe_readonly",
        params_model=EchoParams,
        metadata_risk_level="safe_read",
        metadata_requires_consent=False
    )
    async def collect(self, message: str = "") -> Dict[str, Any]:
        """Echo tool - возвращает переданное сообщение."""
        return {"echo": message}

