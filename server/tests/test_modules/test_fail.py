"""Test tool: fail(error_code) -> raises Exception"""
import sys
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel

# Add pc_agent to path if not already there
# server/tests/test_modules/test_fail.py -> server/tests -> server -> root -> pc_agent
pc_agent_dir = Path(__file__).resolve().parent.parent.parent.parent / "pc_agent"
if not pc_agent_dir.exists():
    # Try alternative path: might be running from different location
    pc_agent_dir = Path(__file__).resolve().parent.parent.parent / "pc_agent"
if pc_agent_dir.exists() and str(pc_agent_dir) not in sys.path:
    sys.path.insert(0, str(pc_agent_dir))

from modules.base_module import BaseCollector
from core.registry import exposed_tool


class FailParams(BaseModel):
    error_code: str = "TEST_ERROR"


class TestFailModule(BaseCollector):
    """Тестовый модуль для fail tool."""
    
    @property
    def name(self) -> str:
        return "test_fail"
    
    @exposed_tool(
        name="fail",
        description="Fail test tool - raises exception",
        risk_level="safe_readonly",
        params_model=FailParams,
        metadata_risk_level="safe_read",
        metadata_requires_consent=False
    )
    async def collect(self, error_code: str = "TEST_ERROR") -> Dict[str, Any]:
        """Fail tool - выбрасывает исключение для тестирования error handling."""
        raise Exception(f"Test error: {error_code}")

