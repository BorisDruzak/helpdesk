"""Explicit draft offering publication shares scenario confirmation and transaction."""
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.models import HelpdeskServiceOffering, HelpdeskService
from app.db.request_scenario_models import RequestStudioScenarioVersion
from app.repos.request_scenario_repo import RequestScenarioRepo
from tests.test_request_scenario_publication_api import ready
from tests.test_request_scenario_admin_api import ADMIN, BASE

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


@pytest.mark.asyncio
async def test_candidate_cannot_publish_private_offering_unpublished_parent_or_invalid_catalog(test_client_light, test_engine):
    identifier, definition = await ready(test_engine)
    url = BASE + "/scenarios/" + identifier
    response = await test_client_light.put(url + "/draft", headers=ADMIN, json={"revision": 1, "definition": dict(definition, publish_offering=True)})
    assert response.status == 200, await response.text()
    for problem, code in (("private", "offering_unavailable"), ("parent", "service_unavailable"), ("type", "offering_not_ready")):
        async with async_sessionmaker(test_engine)() as session:
            offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
            service = await session.scalar(select(HelpdeskService).where(HelpdeskService.code == definition["service_code"]))
            offering.lifecycle_status = "draft"
            offering.visibility = "internal" if problem == "private" else "public"
            offering.request_type = None if problem == "type" else "incident"
            service.lifecycle_status = "draft" if problem == "parent" else "published"
            await session.commit()
        response = await test_client_light.post(url + "/publish-preview", headers=ADMIN, json={"revision": 2})
        assert response.status == 200, await response.text()
        data = (await response.json())["data"]
        assert not data["readiness"]["can_publish"] and data["confirmation_token"] is None
        assert any(issue["code"] == code for issue in data["readiness"]["issues"]), data["readiness"]

@pytest.mark.asyncio
@pytest.mark.parametrize("audit_failure", [False, True])
async def test_explicit_draft_offering_publication_is_atomic(test_client_light, test_engine, monkeypatch, audit_failure):
    identifier, definition = await ready(test_engine)
    async with async_sessionmaker(test_engine)() as session:
        offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
        offering.lifecycle_status = "draft"
        offering.published_at = None
        offering.request_type = "incident"
        await session.commit()
        from tickets.service_catalog_publication import ServiceCatalogPublicationService
        validation = await ServiceCatalogPublicationService(session).validate_offering(definition["offering_full_code"])
        assert not validation["blocking"], validation
    url = BASE + "/scenarios/" + identifier
    response = await test_client_light.post(url + "/publish-preview", headers=ADMIN, json={"revision": 1})
    assert response.status == 200, await response.text()
    without_intent = (await response.json())["data"]
    assert not without_intent["readiness"]["can_publish"] and without_intent["confirmation_token"] is None
    assert any(issue["code"] == "offering_unavailable" for issue in without_intent["readiness"]["issues"])
    definition["publish_offering"] = True
    response = await test_client_light.put(url + "/draft", headers=ADMIN, json={"revision": 1, "definition": definition})
    assert response.status == 200, await response.text()
    response = await test_client_light.post(url + "/publish-preview", headers=ADMIN, json={"revision": 2})
    assert response.status == 200, await response.text()
    preview = (await response.json())["data"]
    assert preview["readiness"]["can_publish"], preview["readiness"]
    assert {"path": "offering.lifecycle_status", "before": "draft", "after": "published"} in preview["diff"]
    async with async_sessionmaker(test_engine)() as session:
        offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
        assert offering.lifecycle_status == "draft" and offering.published_at is None
        before = await session.scalar(select(func.count()).select_from(RequestStudioScenarioVersion).where(RequestStudioScenarioVersion.scenario_id == identifier))
    body = {"revision": 2, "confirm": True, "confirmation_token": preview["confirmation_token"]}
    if audit_failure:
        monkeypatch.setattr(RequestScenarioRepo, "_audit", AsyncMock(side_effect=RuntimeError("audit unavailable")))
    response = await test_client_light.post(url + "/publish", headers=ADMIN, json=body)
    assert response.status == (500 if audit_failure else 200), await response.text()
    async with async_sessionmaker(test_engine)() as session:
        offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
        assert offering.lifecycle_status == ("draft" if audit_failure else "published")
        assert (offering.published_at is None) == audit_failure
        assert await session.scalar(select(func.count()).select_from(RequestStudioScenarioVersion).where(RequestStudioScenarioVersion.scenario_id == identifier)) == before + (0 if audit_failure else 1)
    if not audit_failure:
        result = (await response.json())["data"]
        assert result["version"]["source_snapshot"]["offering"]["lifecycle_status"] == "published"
        assert (await test_client_light.post(url + "/publish", headers=ADMIN, json=body)).status == 409
