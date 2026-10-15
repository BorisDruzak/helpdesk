from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repos.request_scenario_repo import RequestScenarioRepo
from tests.test_request_scenario_submission import definition
from web_api.dto.request_scenario_admin import SimulationInput
from tickets.service_catalog_preview import ServiceCatalogPreviewError

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_template_requirements_do_not_hide_the_successful_route(monkeypatch):
    from tickets import service_catalog_preview
    monkeypatch.setattr(service_catalog_preview, "simulate_service_catalog_processing", AsyncMock(side_effect=ServiceCatalogPreviewError({"form_payload": {"impact_scope": "required"}})))
    session = SimpleNamespace(add=AsyncMock(), flush=AsyncMock(), commit=AsyncMock())
    repo = RequestScenarioRepo(session, None)
    repo.detail = AsyncMock(return_value=(SimpleNamespace(archived=False), SimpleNamespace(revision=1, definition=definition().model_dump(mode="json"))))
    result = await repo.simulate("owned", SimulationInput.model_validate({"revision": 1, "steps": [{"expected_block_id": "questions", "revision": 1, "answers": {"summary": "VPN", "urgent": False}}]}))
    assert result["current_step"]["kind"] == "submit_ticket"
    assert result["processing"] is None
    assert result["processing_error"] == {"code": "PROCESSING_INPUT_INVALID"}
    session.add.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_self_service_v3_simulation_explains_selected_rules_without_ticket_policies(monkeypatch):
    from pathlib import Path
    from tickets.request_scenario_document import parse_scenario_document
    path = Path(__file__).resolve().parents[2] / "docs/examples/guided-request-v3-equipment.yaml"
    value = parse_scenario_document(path.read_text(encoding="utf-8"), "yaml")
    session = SimpleNamespace(add=AsyncMock(), flush=AsyncMock(), commit=AsyncMock())
    repo = RequestScenarioRepo(session, None)
    repo.detail = AsyncMock(return_value=(SimpleNamespace(archived=False), SimpleNamespace(revision=1, definition=value.model_dump(mode="json"))))
    result = await repo.simulate("owned", SimulationInput.model_validate({"revision": 1, "steps": [
        {"expected_block_id": "problem", "revision": 1, "answers": {"problem_type": "printer"}},
        {"expected_block_id": "scope", "revision": 2, "answers": {"affected_scope": "department"}},
        {"expected_block_id": "ability", "revision": 3, "answers": {"can_continue": "no"}},
        {"expected_block_id": "printer_help", "revision": 4, "current_result": "acknowledged"},
        {"expected_block_id": "check", "revision": 5, "current_result": "yes"},
    ]}))
    assert result["state"]["state"] == "completed_self_service"
    assert result["processing"] is None
    assert result["map_processing"]["sla_profile"]["key"] == "urgent"
    assert any(item["block_id"] == "choose" and item["selected"] for item in result["map_processing"]["condition_trace"])
    session.add.assert_not_called()
    session.commit.assert_not_called()
