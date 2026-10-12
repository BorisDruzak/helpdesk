"""Additive per-offering availability; no draft definitions in public catalog."""
from sqlalchemy import select

from app.db.request_scenario_models import RequestStudioCategory, RequestStudioScenario, RequestStudioScenarioVersion


def category_path_is_public(category_id, categories):
    visited = set()
    while category_id:
        category = categories.get(category_id)
        if category_id in visited or len(visited) >= 16 or not category:
            return False
        visibility = category.get("visibility") if isinstance(category, dict) else category.visibility
        lifecycle = category.get("lifecycle_status") if isinstance(category, dict) else category.lifecycle_status
        if visibility != "public" or lifecycle != "published":
            return False
        visited.add(category_id)
        category_id = category.get("parent_id") if isinstance(category, dict) else category.parent_id
    return True


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
        if category_path_is_public(scenario.category_id, categories):
            enabled.add(scenario.offering_full_code)
    return enabled
