"""Test tool: slow_echo(message, delay) -> {"echo": message} with delay"""
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel

# Add pc_agent to path if not already there
pc_agent_dir = Path(__file__).resolve().parent.parent.parent.parent / "pc_agent"
if not pc_agent_dir.exists():
    pc_agent_dir = Path(__file__).resolve().parent.parent.parent / "pc_agent"
if pc_agent_dir.exists() and str(pc_agent_dir) not in sys.path:
    sys.path.insert(0, str(pc_agent_dir))

from modules.base_module import BaseCollector
from core.registry import exposed_tool


class SlowEchoParams(BaseModel):
    message: str = ""
    delay: float = 1.0


class TestSlowEchoModule(BaseCollector):
    """Тестовый модуль для slow_echo tool с задержкой."""
    
    @property
    def name(self) -> str:
        return "test_slow_echo"
    
    @exposed_tool(
        name="slow_echo",
        description="Slow echo test tool - returns input message after delay",
        risk_level="safe_readonly",
        params_model=SlowEchoParams,
        metadata_risk_level="safe_read",
        metadata_requires_consent=False
    )
    async def collect(self, message: str = "", delay: float = 1.0) -> Dict[str, Any]:
        """Slow echo tool - возвращает переданное сообщение после задержки."""
        await asyncio.sleep(delay)
        return {"echo": message}


