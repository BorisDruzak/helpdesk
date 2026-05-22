from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repos.registry_repo import RegistryRepo
from registry.registration_service import RegistrationService


def default_registration_form() -> dict[str, Any]:
    return {
        "key": "agent_device_registration",
        "title": "Регистрация рабочего места",
        "description": "Подтвердите, кто работает за этим ПК. Данные создают заявку на регистрацию и не создают обращение.",
        "surface": "agent_registration",
        "pack_key": "registration_forms",
        "fields": [
            {"key": "full_name", "label": "ФИО", "type": "text", "required": True},
            {"key": "display_name", "label": "Отображаемое имя", "type": "text", "required": False},
            {"key": "login", "label": "Логин", "type": "text", "required": True},
            {"key": "email", "label": "Email", "type": "text", "required": False},
            {"key": "phone", "label": "Телефон", "type": "text", "required": False},
            {"key": "department", "label": "Подразделение", "type": "text", "required": False},
            {"key": "building", "label": "Здание", "type": "text", "required": False},
            {"key": "floor", "label": "Этаж", "type": "text", "required": False},
            {"key": "room", "label": "Кабинет", "type": "text", "required": False},
            {
                "key": "relationship_type",
                "label": "Тип ПК",
                "type": "select",
                "required": True,
                "options": [
                    {"value": "primary_user", "label": "Мой основной ПК"},
                    {"value": "shared_user", "label": "Общий ПК"},
                    {"value": "temporary_user", "label": "Временное рабочее место"},
                ],
            },
            {
                "key": "is_shared_device",
                "label": "Это общий ПК",
                "type": "checkbox",
                "required": False,
                "placeholder": "Да",
                "visible_when": {"field": "relationship_type", "equals": "shared_user"},
            },
        ],
    }


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


async def build_registration_form_payload(session: AsyncSession, device_id: str) -> dict[str, Any]:
    return {
        "form": default_registration_form(),
        "registration": await RegistrationService(session).get_device_registration_status(device_id),
        "registry_options": await build_lightweight_registry_options(session),
    }
