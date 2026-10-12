"""One offering card, independent of draft/archive history and pagination."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db.request_scenario_models import RequestStudioDraft, RequestStudioScenario
from app.repos.request_scenario_repo import RequestScenarioRepo

pytestmark = pytest.mark.no_db


def repository():
    now = datetime.now(timezone.utc)
    rows = []
    for identifier, archived, enabled in [("archive", True, False), ("draft", False, False)]:
        scenario = RequestStudioScenario(id=identifier, scenario_key=identifier, title=identifier,
            service_code="workplace", offering_full_code="workplace.print", category_id="printers",
            archived=archived, enabled=enabled, updated_at=now)
        draft = RequestStudioDraft(scenario_id=identifier, revision=1, definition={}, updated_at=now)
        rows.append((scenario, draft, None))
    repo = RequestScenarioRepo(SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows))), None)
    repo.categories = AsyncMock(return_value=[{"id": "printers", "service_code": "workplace", "parent_id": None,
        "title": "Принтеры", "visibility": "public", "lifecycle_status": "published"}])
    repo.catalog = SimpleNamespace(list_services=AsyncMock(return_value=[{"code": "workplace", "public_title": "Рабочее место", "visibility": "public", "lifecycle_status": "published"}]),
        list_offerings=AsyncMock(return_value=[{"full_code": "workplace." + code, "service_code": "workplace", "public_title": title,
            "visibility": "public", "lifecycle_status": "published", "request_template_key": "printer"} for code, title in [("print", "Не печатает"), ("vpn", "VPN")]]))
    return repo, rows


@pytest.mark.asyncio
async def test_one_card_per_offering_keeps_archive_inside_history_and_form_active_for_draft():
    repo, _ = repository()
    result = await repo.catalog_view()
    assert result["total"] == 2
    cards = {item["offering"]["full_code"]: item for item in result["entries"]}
    printer = cards["workplace.print"]
    assert printer["active_mode"] == "form"
    assert [item["id"] for item in printer["scenarios"]] == ["draft", "archive"]
    assert (await repo.catalog_view(status="form_only"))["total"] == 2
    assert (await repo.catalog_view(status="archived"))["total"] == 1


@pytest.mark.asyncio
async def test_service_category_includes_plain_forms_and_subcategory_retains_disabled_scenario_offering():
    repo, _ = repository()
    result = await repo.catalog_view(service_code="workplace", limit=1)
    assert result["total"] == 2 and len(result["entries"]) == 1
    assert (await repo.catalog_view(service_code="missing"))["total"] == 0
    result = await repo.catalog_view(category_id="printers", status="form_only")
    assert result["total"] == 1
    assert result["entries"][0]["offering"]["full_code"] == "workplace.print"
    exact = await repo.catalog_view(offering_code="workplace.vpn")
    assert exact["total"] == 1 and exact["entries"][0]["offering"]["full_code"] == "workplace.vpn"
    assert (await repo.catalog_view(offering_code="workplace.missing"))["total"] == 0


@pytest.mark.asyncio
async def test_published_disabled_or_hidden_scenario_does_not_claim_requester_uses_it():
    repo, rows = repository()
    rows[1][0].published_version_id = "version"
    rows[1] = (*rows[1][:2], 3)
    assert (await repo.catalog_view())["entries"][1]["active_mode"] == "form"

    assert (await repo.catalog_view(status="guided"))["total"] == 0
    rows[1][0].enabled = True
    assert (await repo.catalog_view())["entries"][1]["active_mode"] == "scenario"
    assert (await repo.catalog_view(status="guided"))["total"] == 1
    repo.categories.return_value[0]["visibility"] = "internal"
    assert (await repo.catalog_view())["entries"][1]["active_mode"] == "form"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,field,value", [("service", "visibility", "internal"), ("service", "lifecycle_status", "draft"),
    ("offering", "visibility", "restricted"), ("offering", "lifecycle_status", "retired")])
async def test_unavailable_catalog_objects_do_not_claim_a_requester_flow(kind, field, value):
    repo, _ = repository()
    target = repo.catalog.list_services.return_value[0] if kind == "service" else repo.catalog.list_offerings.return_value[0]
    target[field] = value
    card = next(item for item in (await repo.catalog_view())["entries"] if item["offering"]["full_code"] == "workplace.print")
    assert card["requester_available"] is False
