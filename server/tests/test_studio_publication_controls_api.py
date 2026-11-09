"""Isolated PostgreSQL acceptance for independent catalogue visibility."""
import asyncio
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import HelpdeskService, HelpdeskServiceOffering, HelpdeskServiceCatalogAudit
from app.db.request_scenario_models import RequestStudioDraft, RequestStudioScenario, RequestStudioScenarioVersion
from app.repos.request_scenario_repo import serialize
from tests.test_request_scenario_admin_api import ADMIN, AUDITOR, BASE
from tests.test_request_scenario_v3_processing_api import configured, publish
from tests.test_request_scenario_submit_api import OWNER
from tests.test_request_scenario_session_api import BASE as SESSION_BASE

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


@pytest.mark.asyncio
async def test_visibility_compare_and_set_race_preserves_map_and_audits_once(test_client_light, test_engine):
    identifier, definition, _, _ = await configured(test_engine)
    url, _ = await publish(test_client_light, identifier, definition)
    prepared = await test_client_light.post(url + "/publish-preview", headers=ADMIN, json={"revision": 2})
    token = (await prepared.json())["data"]["confirmation_token"]
    async with async_sessionmaker(test_engine)() as session:
        before = (serialize(await session.get(RequestStudioScenario, identifier)), serialize(await session.get(RequestStudioDraft, identifier)))
        versions = await session.scalar(select(func.count()).select_from(RequestStudioScenarioVersion))
    endpoint = url + "/catalog-visibility"
    denied = await test_client_light.post(endpoint, headers=AUDITOR, json={"visibility": "internal", "expected_visibility": "public"})
    assert denied.status == 403
    invalid = await test_client_light.post(endpoint, headers=ADMIN, json={"visibility": "internal", "expected_visibility": "public", "revision": 2})
    assert invalid.status == 400
    responses = await asyncio.gather(*[test_client_light.post(endpoint, headers=ADMIN, json={"visibility": value, "expected_visibility": "public"}) for value in ("internal", "restricted")])
    assert sorted(response.status for response in responses) == [200, 409]
    conflict = next(response for response in responses if response.status == 409)
    assert (await conflict.json())["error_code"] == "VISIBILITY_CONFLICT"
    stale = await test_client_light.post(url + "/publish", headers=ADMIN,
        json={"revision": 2, "confirm": True, "confirmation_token": token})
    assert stale.status == 409
    assert (await stale.json())["error_code"] == "CONFIRMATION_TOKEN_DRAFT_MISMATCH"
    async with async_sessionmaker(test_engine)() as session:
        after = (serialize(await session.get(RequestStudioScenario, identifier)), serialize(await session.get(RequestStudioDraft, identifier)))
        assert after == before
        assert await session.scalar(select(func.count()).select_from(RequestStudioScenarioVersion)) == versions
        audits = (await session.scalars(select(HelpdeskServiceCatalogAudit).where(HelpdeskServiceCatalogAudit.object_code == definition["offering_full_code"], HelpdeskServiceCatalogAudit.action == "visibility_changed"))).all()
        assert len(audits) == 1
        service = await session.scalar(select(HelpdeskService).where(HelpdeskService.code == definition["service_code"]))
        assert service.visibility == "public"


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", ["internal", "restricted"])
async def test_hidden_candidate_publication_keeps_requester_gate(test_client_light, test_engine, visibility):
    identifier, definition, _, _ = await configured(test_engine, draft_offering=True)
    async with async_sessionmaker(test_engine)() as session:
        offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
        offering.visibility = visibility
        await session.commit()
    _, preview = await publish(test_client_light, identifier, definition)
    assert preview["catalog_visibility"] == visibility
    async with async_sessionmaker(test_engine)() as session:
        offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
        assert offering.visibility == visibility and offering.lifecycle_status == "published"
    started = await test_client_light.post(SESSION_BASE, headers=OWNER, json={"offering_full_code": definition["offering_full_code"]})
    assert started.status in {403, 404}, await started.text()


@pytest.mark.asyncio
async def test_public_child_does_not_grant_restricted_parent_access(test_client_light, test_engine):
    identifier, definition, _, _ = await configured(test_engine)
    await publish(test_client_light, identifier, definition)
    async with async_sessionmaker(test_engine)() as session:
        offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
        offering.visibility = "internal"
        service = await session.scalar(select(HelpdeskService).where(HelpdeskService.code == definition["service_code"]))
        service.visibility = "restricted"
        await session.commit()
    response = await test_client_light.post(BASE + "/scenarios/" + identifier + "/catalog-visibility", headers=ADMIN, json={"visibility": "public", "expected_visibility": "internal"})
    assert response.status == 200, await response.text()
    started = await test_client_light.post(SESSION_BASE, headers=OWNER, json={"offering_full_code": definition["offering_full_code"]})
    assert started.status in {403, 404}, await started.text()
    async with async_sessionmaker(test_engine)() as session:
        service = await session.scalar(select(HelpdeskService).where(HelpdeskService.code == definition["service_code"]))
        assert service.visibility == "restricted"
