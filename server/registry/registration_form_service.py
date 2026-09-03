from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repos.registry_repo import RegistryRepo


def _option(value: object, label: object) -> dict[str, str]:
    return {"value": str(value or "").strip(), "label": str(label or value or "").strip()}


def _compact_options(items: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        value = str(item.get("value") or "").strip()
        label = str(item.get("label") or value).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append({"value": value, "label": label})
    return result


async def build_lightweight_registry_options(session: AsyncSession) -> dict[str, list[dict[str, str]]]:
    repo = RegistryRepo(session)
    assets = await repo.list_assets(limit=500)
    people = await repo.list_people(limit=500)
    locations = await repo.list_locations(limit=500)
    departments = await repo.list_departments()
    services = await repo.list_services()

    return {
        "devices": _compact_options(
            [
                _option(
                    asset.device_id or asset.asset_id,
                    asset.hostname or asset.name or asset.device_id or asset.asset_id,
                )
                for asset in assets
            ]
        ),
        "users": _compact_options(
            [
                _option(
                    person.person_id,
                    person.display_name or person.full_name or person.person_id,
                )
                for person in people
            ]
        ),
        "locations": _compact_options(
            [
                _option(
                    location.location_id,
                    " / ".join(
                        str(part).strip()
                        for part in (location.building, location.room)
                        if str(part or "").strip()
                    )
                    or location.display_name
                    or location.location_id,
                )
                for location in locations
            ]
        ),
        "departments": _compact_options(
            [
                _option(department.department_id, department.name or department.code)
                for department in departments
            ]
        ),
        "services": _compact_options(
            [
                _option(service.service_id, service.name or service.code)
                for service in services
            ]
        ),
    }
