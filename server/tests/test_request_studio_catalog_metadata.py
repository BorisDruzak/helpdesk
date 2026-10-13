"""Ordinary form grouping must never bind to another service's folder."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest
from app.repos.service_catalog_repo import ServiceCatalogRepo
from app.repos.request_scenario_repo import RequestScenarioRepo, ScenarioAdminError

pytestmark = pytest.mark.no_db
@pytest.mark.asyncio
async def test_valid_grouping_is_saved_with_other_metadata_and_audit():
    category_id="10000000-0000-0000-0000-000000000001"
    session=SimpleNamespace(execute=AsyncMock(),get=AsyncMock(return_value=SimpleNamespace(service_code="network",lifecycle_status="published")),add=Mock(),flush=AsyncMock())
    repo=ServiceCatalogRepo(session)
    repo.get_service_row_by_code=AsyncMock(return_value=SimpleNamespace(code="network",service_id="service"))
    repo.get_offering_row_by_full_code=AsyncMock(return_value=None)
    repo.append_audit=AsyncMock()
    metadata={"existing_setting":"keep","studio_catalog":{"category_id":category_id,"synonyms":["туннель"]}}
    saved=await repo.upsert_offering_draft({"service_code":"network","code":"vpn","public_title":"VPN","metadata":metadata},actor_id="admin",actor_role="admin")
    assert saved["metadata"]==metadata and saved["full_code"]=="network.vpn"
    repo.append_audit.assert_awaited_once()

@pytest.mark.asyncio
@pytest.mark.parametrize("category", [None, SimpleNamespace(service_code="other",lifecycle_status="published"),SimpleNamespace(service_code="network",lifecycle_status="archived")])
async def test_rejects_unavailable_category_before_changing_offering(category):
    session=SimpleNamespace(execute=AsyncMock(),get=AsyncMock(return_value=category))
    repo=ServiceCatalogRepo(session)
    repo.get_service_row_by_code=AsyncMock(return_value=SimpleNamespace(code="network"))
    repo.get_offering_row_by_full_code=AsyncMock()
    with pytest.raises(ValueError,match="invalid catalog category"):
        await repo.upsert_offering_draft({"service_code":"network","code":"vpn","metadata":{"studio_catalog":{"category_id":"10000000-0000-0000-0000-000000000001"}}},actor_id="admin",actor_role="admin")
    repo.get_offering_row_by_full_code.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize("settings", [{"category_id":5},{"category_id":"bad"},{"synonyms":"unsafe"},{"synonyms":["x"]*21},{"synonyms":["x"*101]}])
async def test_rejects_malformed_grouping_without_database_mutation(settings):
    repo=ServiceCatalogRepo(SimpleNamespace(execute=AsyncMock(),get=AsyncMock()))
    repo.get_service_row_by_code=AsyncMock(return_value=SimpleNamespace(code="network"))
    repo.get_offering_row_by_full_code=AsyncMock()
    with pytest.raises(ValueError):
        await repo.upsert_offering_draft({"service_code":"network","code":"vpn","metadata":{"studio_catalog":settings}},actor_id="admin",actor_role="admin")
    repo.get_offering_row_by_full_code.assert_not_awaited()

@pytest.mark.asyncio
async def test_category_with_ordinary_service_cannot_be_archived():
    repo=RequestScenarioRepo(SimpleNamespace(scalar=AsyncMock(side_effect=[None,None,"offering"])),None)
    with pytest.raises(ScenarioAdminError) as failure:
        await repo._archive_category_check(SimpleNamespace(id="10000000-0000-0000-0000-000000000001"))
    assert failure.value.code=="CATEGORY_NOT_EMPTY"
