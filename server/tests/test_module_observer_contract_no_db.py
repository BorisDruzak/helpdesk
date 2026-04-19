import pytest

from utils.module_observer_contract import validate_observer_contract_sources


VALID_MODULE_SOURCE = """
from typing import Dict, Any
from pc_agent.modules.base_module import BaseCollector
from pc_agent.core.registry import exposed_tool


class ExampleCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "example"

    async def collect(self) -> Dict[str, Any]:
        return {}

    @exposed_tool(name="example.run", description="Run example", risk_level="safe_readonly")
    async def run(self, **kwargs) -> Dict[str, Any]:
        with self.trace_span("tool.entry", details={"tool_name": "example.run"}):
            self.trace_event("params.normalized", details={"tool_name": "example.run"})
            return {"ok": True}
"""


INVALID_MODULE_SOURCE = """
from typing import Dict, Any
from pc_agent.modules.base_module import BaseCollector
from pc_agent.core.registry import exposed_tool


class ExampleCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "example"

    async def collect(self) -> Dict[str, Any]:
        return {}

    @exposed_tool(name="example.run", description="Run example", risk_level="safe_readonly")
    async def run(self, **kwargs) -> Dict[str, Any]:
        return {"ok": True}
"""


@pytest.mark.no_db
def test_validate_observer_contract_accepts_tool_entry_trace_span() -> None:
    errors = validate_observer_contract_sources({"module.py": VALID_MODULE_SOURCE})
    assert errors == []


@pytest.mark.no_db
def test_validate_observer_contract_rejects_missing_tool_entry_trace_span() -> None:
    errors = validate_observer_contract_sources({"module.py": INVALID_MODULE_SOURCE})
    assert errors
    assert "tool.entry" in errors[0]
    assert "example.run" in errors[0]
