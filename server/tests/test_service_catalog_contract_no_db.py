from __future__ import annotations

from typing import Any

import pytest

from tickets.service_catalog_contract import (
    CATALOG_BUSINESS_CRITICALITIES,
    CATALOG_LIFECYCLE_STATUSES,
    CATALOG_VISIBILITIES,
    SERVICE_CATALOG_POLICY_INHERITANCE_ORDER,
    ServiceCatalogValidationError,
    normalize_catalog_code,
    serialize_offering_for_requester,
    serialize_service_for_requester,
)


pytestmark = pytest.mark.no_db


FORBIDDEN_REQUESTER_KEYS = {
    "queue_id",
    "default_queue_id",
    "owner_queue_id",
    "assignee_id",
    "requester_id",
    "device_id",
    "registry_service_id",
    "raw_policy_json",
    "policy_refs",
    "effective_policy_refs",
    "approver_ids",
    "custom_fields",
    "trace_id",
    "operation_id",
}


def _collect_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_REQUESTER_KEYS:
                found.append(child_path)
            found.extend(_collect_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_collect_forbidden_keys(child, f"{path}[{index}]"))
    return found


def test_service_catalog_contract_enums_and_inheritance_order() -> None:
    assert CATALOG_LIFECYCLE_STATUSES == ("draft", "published", "retired")
    assert CATALOG_VISIBILITIES == ("public", "internal", "restricted")
    assert CATALOG_BUSINESS_CRITICALITIES == ("low", "medium", "high", "critical")
    assert SERVICE_CATALOG_POLICY_INHERITANCE_ORDER == (
        "system",
        "ticket_type",
        "category",
        "service",
        "offering",
        "request_template",
    )


def test_normalize_catalog_code_rejects_unsafe_values() -> None:
    assert normalize_catalog_code(" Workplace ") == "workplace"
    assert normalize_catalog_code("laptop-broken") == "laptop-broken"
    assert normalize_catalog_code("laptop_broken") == "laptop_broken"

    with pytest.raises(ServiceCatalogValidationError):
        normalize_catalog_code("Laptop Broken!")
    with pytest.raises(ServiceCatalogValidationError):
        normalize_catalog_code("")


def test_requester_service_serializer_omits_internal_fields_recursively() -> None:
    service = {
        "service_id": "svc-1",
        "code": "workplace",
        "public_title": "Рабочее место",
        "short_description": "Ноутбук, ПК, монитор",
        "description": "Рабочее место сотрудника",
        "icon": "laptop",
        "visibility": "public",
        "lifecycle_status": "published",
        "registry_service_id": "cmdb-secret",
        "default_queue_id": 10,
        "owner_queue_id": 10,
        "policy_refs": {"routing": "internal-route"},
        "metadata_json": {"trace_id": "trace-secret"},
    }
    offering = {
        "offering_id": "off-1",
        "service_code": "workplace",
        "code": "laptop_broken",
        "full_code": "workplace.laptop_broken",
        "public_title": "Сломался ноутбук",
        "short_description": "Не включается или поврежден",
        "request_type": "incident",
        "request_type_label": "Инцидент",
        "request_template_key": "laptop_incident",
        "form_schema_version": "1",
        "visibility": "public",
        "lifecycle_status": "published",
        "approval_required": False,
        "diagnostic_consent_required": True,
        "expected_response": "до 30 минут",
        "default_queue_id": 10,
        "approver_ids": ["boss"],
        "effective_policy_refs": {"sla": "fast"},
    }

    payload = serialize_service_for_requester(service, offerings=[offering])

    assert _collect_forbidden_keys(payload) == []
    assert payload["service_code"] == "workplace"
    assert payload["title"] == "Рабочее место"
    assert payload["offerings"][0]["full_code"] == "workplace.laptop_broken"
    assert payload["offerings"][0]["diagnostic_consent_required"] is True


def test_requester_offering_serializer_is_safe_and_stable() -> None:
    payload = serialize_offering_for_requester(
        {
            "code": "unknown",
            "full_code": "other.unknown",
            "public_title": "Другое / Не знаю",
            "description": "Опишите ситуацию свободно",
            "request_type": "request",
            "request_template_key": "other_request",
            "default_queue_id": 99,
            "raw_policy_json": {"routing": {"queue_id": 99}},
            "approval_required": True,
            "diagnostic_consent_required": False,
        }
    )

    assert _collect_forbidden_keys(payload) == []
    assert payload == {
        "offering_code": "unknown",
        "full_code": "other.unknown",
        "title": "Другое / Не знаю",
        "description": "Опишите ситуацию свободно",
        "request_type": "request",
        "request_type_label": "Запрос",
        "request_template_key": "other_request",
        "form_schema_version": None,
        "approval_required": True,
        "approval_hint": "Потребуется согласование",
        "diagnostic_consent_required": False,
        "diagnostic_hint": None,
        "expected_response": None,
        "expected_resolution": None,
        "requires_attachment": False,
    }
