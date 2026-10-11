"""Additive per-offering availability; no draft definitions in public catalog."""
from sqlalchemy import select

from app.db.request_scenario_models import RequestStudioCategory, RequestStudioScenario, RequestStudioScenarioVersion


async def enabled_guided_offerings(session):
    scenarios = (await session.scalars(select(RequestStudioScenario).join(
        RequestStudioScenarioVersion, RequestStudioScenario.published_version_id == RequestStudioScenarioVersion.id,
    ).where(RequestStudioScenario.enabled.is_(True), RequestStudioScenario.archived.is_(False),
            RequestStudioScenarioVersion.state == "published"))).all()
    if not scenarios:
        return set()
    categories = {row.id: row for row in (await session.scalars(select(RequestStudioCategory))).all()}
    enabled = set()
    for scenario in scenarios:
        category_id, visited = scenario.category_id, set()
        visible = True
        while category_id:
            category = categories.get(category_id)
            if category_id in visited or len(visited) >= 16 or not category or category.visibility != "public" or category.lifecycle_status != "published":
                visible = False
                break
            visited.add(category_id)
            category_id = category.parent_id
        if visible:
            enabled.add(scenario.offering_full_code)
    return enabled
