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
