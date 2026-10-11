"""Admin simulation outcomes stay isolated from requester commands and writes."""
from copy import deepcopy
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.models import Ticket, TicketEvent, TicketApproval, Operation, TicketNotification, ConsentDecision, UserConsentRequest
from app.db.request_scenario_models import RequestStudioSession
from tests.test_request_scenario_admin_api import seed, create, BASE, ADMIN, AUDITOR
from tests.test_request_scenario_runtime import pilot
from tests.test_request_scenario_session_api import OWNER

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


@pytest.mark.asyncio
async def test_admin_failure_outcomes_and_attachments_do_not_create_runtime_side_effects(test_client_light, test_engine):
    definition = await seed(test_engine)
    graph = deepcopy(pilot())
    definition["blocks"], definition["entry_block_id"] = graph["blocks"], graph["entry_block_id"]
    detail = await create(test_client_light, definition)
    identifier = detail["scenario"]["id"]
    path = BASE + "/scenarios/" + identifier + "/simulate"
    models = [Ticket, TicketEvent, TicketApproval, Operation, TicketNotification, ConsentDecision, UserConsentRequest, RequestStudioSession]
    async with async_sessionmaker(test_engine)() as session:
        before = [await session.scalar(select(func.count()).select_from(model)) for model in models]
    steps = [{"expected_block_id": "questions", "revision": 1, "answers": {"summary": "No print", "impact": "me"}},
             {"expected_block_id": "instruction", "revision": 2, "current_result": "acknowledged"},
             {"expected_block_id": "helped", "revision": 3, "current_result": "no"}]
    for status in ("unavailable", "denied", "timeout", "capability_absent"):
        response = await test_client_light.post(path, headers=AUDITOR, json={"revision": 1, "steps": steps, "diagnostic_outcomes": {"diagnostic": status}})
        assert response.status == 200, await response.text()
        result = (await response.json())["data"]
        assert result["current_step"]["id"] == "review"
        assert result["state"]["results"]["diagnostic"] == {"status": status, "reason": "simulated_" + status, "simulated": True, "operation_created": False, "consent_required": True}
    assert (await test_client_light.post(path, headers=OWNER, json={"revision": 1})).status == 403
    for outcomes in ({"diagnostic": "success"}, {"review": "timeout"}, {"absent": "denied"}):
        assert (await test_client_light.post(path, headers=ADMIN, json={"revision": 1, "diagnostic_outcomes": outcomes})).status == 400
    definition["blocks"][0]["fields"][0]["type"] = "file"
    response = await test_client_light.put(BASE + "/scenarios/" + identifier + "/draft", headers=ADMIN, json={"revision": 1, "definition": definition})
    assert response.status == 400
    async with async_sessionmaker(test_engine)() as session:
        assert [await session.scalar(select(func.count()).select_from(model)) for model in models] == before
