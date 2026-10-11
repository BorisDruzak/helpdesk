"""Approved requester entity sources; never list other users' devices."""
from app.repos.registry_repo import RegistryRepo
from requester.identity_service import RequesterIdentityResolver
from tickets.request_scenario_runtime import ScenarioInputError
from tickets.service_catalog_runtime import ServiceCatalogRuntimeResolver

PICKERS = {"department_picker", "location_picker", "device_picker", "service_picker", "user_picker"}


async def picker_options(session, owner, types):
    result = {}
    repo = RegistryRepo(session)
    if "department_picker" in types:
        result["department_picker"] = [{"value": row.department_id, "label": row.name or row.code} for row in await repo.list_departments()]
    if "location_picker" in types:
        result["location_picker"] = [{"value": row.location_id, "label": row.display_name or " / ".join(filter(None, [row.building, row.room])) or row.location_id} for row in await repo.list_locations(limit=500)]
    if types & {"user_picker", "device_picker"}:
        resolver = RequesterIdentityResolver(session)
        person = await resolver.resolve_person_for_web_user(owner)
        if "user_picker" in types:
            result["user_picker"] = [{"value": person.person_id, "label": person.display_name or person.full_name or "Ваш профиль"}] if person else []
        if "device_picker" in types:
            result["device_picker"] = [{"value": row["device_id"], "label": row.get("hostname") or "Ваш компьютер"} for row in await resolver.list_allowed_devices(person.person_id if person else None)]
    if "service_picker" in types:
        catalog = await ServiceCatalogRuntimeResolver(session).current_catalog_for_requester()
        result["service_picker"] = [{"value": row["service_code"], "label": row["title"]} for row in catalog["services"]]
    return result


def validate_picker_answers(fields, answers, options):
    errors = {}
    for item in fields:
        value = answers.get(item.key)
        if item.type in PICKERS and value not in (None, "") and value not in {option["value"] for option in options.get(item.type, [])}:
            errors[item.key] = "Выберите доступное значение из списка"
    if errors:
        raise ScenarioInputError(errors)
