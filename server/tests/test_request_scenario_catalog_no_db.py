"""Catalog search must include offering types before combined pagination."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db.request_scenario_models import RequestStudioDraft, RequestStudioScenario
from app.repos.request_scenario_repo import RequestScenarioRepo

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
@pytest.mark.parametrize("request_type,profile,queries", [
    ("incident", "incident", ["incident", "ИНЦИДЕНТ"]),
    ("request", "request", ["request", "Общий запрос"]),
    ("service_request", "service_request", ["service_request", "Запрос услуги"]),
    ("access", "access", ["access", "Запрос доступа"]),
    ("service_request", "software_install", ["software_install", "Установка ПО"]),
    ("consultation", "consultation", ["consultation", "Консультация"]),
    ("custom_type", "custom_profile", ["custom_type", "custom_profile"]),
    ("incident", {}, ["incident", "Инцидент"]),
    ("incident", [], ["incident", "Инцидент"]),
    ("incident", None, ["incident", "Инцидент"]),
])
async def test_catalog_type_search_includes_scenarios_and_legacy_before_pagination(request_type, profile, queries):
    now = datetime.now(timezone.utc)
    row = RequestStudioScenario(id="scenario-one", scenario_key="one", title="Alpha",
        offering_full_code="svc.one", archived=False, updated_at=now)
    draft = RequestStudioDraft(scenario_id=row.id, revision=1, definition={}, updated_at=now)
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [(row, draft, None)])))
    repo = RequestScenarioRepo(session, None)
    repo.categories = AsyncMock(return_value=[])
    offerings = [{"full_code": "svc." + code, "public_title": title,
        "request_type": request_type, "metadata": {"studio_profile": profile, "private_note": "excluded_signal"}}
        for code, title in [("one", "Alpha"), ("two", "Bravo")]]
    repo.catalog = SimpleNamespace(list_offerings=AsyncMock(return_value=offerings), list_services=AsyncMock(return_value=[]))
    assert (await repo.catalog_view())["total"] == 2
    for query in queries:
        result = await repo.catalog_view(query=query)
        assert result["total"] == 2
        assert [item["id"] for item in result["scenarios"]] == [row.id]
        assert [item["full_code"] for item in result["legacy_offerings"]] == ["svc.two"]
        page = await repo.catalog_view(query=query, offset=1, limit=1)
        assert page["total"] == 2 and page["scenarios"] == []
        assert [item["full_code"] for item in page["legacy_offerings"]] == ["svc.two"]
        legacy = await repo.catalog_view(query=query, status="form_only")
        assert legacy["total"] == 1 and legacy["scenarios"] == []
    assert (await repo.catalog_view(query="excluded_signal"))["total"] == 0
