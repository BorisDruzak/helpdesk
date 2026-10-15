"""Additive per-offering availability; no draft definitions in public catalog."""
from sqlalchemy import select

from app.db.request_scenario_models import RequestStudioCategory, RequestStudioScenario, RequestStudioScenarioVersion
from web_api.dto.request_scenario import ScenarioDefinition


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
    return set(await published_catalog_entries(session))


def project_catalog_entries(definition, categories, version_id):
    """Only public versioned entrances; legacy omission retains its old route."""
    if not definition.entry_points:
        return []
    return [
        {"key": entry.key, "entry_point_key": entry.key, "title": entry.title,
         "description": entry.description, "category_id": entry.category_id,
         "category_title": (categories[entry.category_id].get("title") if isinstance(categories.get(entry.category_id), dict)
                            else getattr(categories.get(entry.category_id), "title", None)),
         "help_mode": "guided",
         "synonyms": list(entry.synonyms), "scenario_key": definition.scenario_key,
         "version_id": version_id, "target_block_id": entry.target_block_id}
        for entry in definition.entry_points if entry.enabled and entry.visibility == "public"
        and category_path_is_public(entry.category_id, categories)
    ]


async def published_catalog_entries(session):
    scenarios = (await session.scalars(select(RequestStudioScenario).join(
        RequestStudioScenarioVersion, RequestStudioScenario.published_version_id == RequestStudioScenarioVersion.id,
    ).where(RequestStudioScenario.enabled.is_(True), RequestStudioScenario.archived.is_(False),
            RequestStudioScenarioVersion.state == "published"))).all()
    if not scenarios:
        return {}
    categories = {row.id: row for row in (await session.scalars(select(RequestStudioCategory))).all()}
    enabled = {}
    for scenario in scenarios:
        if category_path_is_public(scenario.category_id, categories):
            version = await session.get(RequestStudioScenarioVersion, scenario.published_version_id)
            try:
                definition = ScenarioDefinition.model_validate(version.definition)
            except ValueError:
                continue  # Malformed snapshots must not advertise an executable route.
            entries = project_catalog_entries(definition, categories, version.id)
            if entries or not definition.entry_points:
                enabled[scenario.offering_full_code] = entries
    return enabled
