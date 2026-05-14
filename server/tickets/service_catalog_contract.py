"""Service Catalog contract helpers and safe projections."""

from __future__ import annotations

import re
from typing import Any


CATALOG_LIFECYCLE_STATUSES = ("draft", "published", "retired")
CATALOG_VISIBILITIES = ("public", "internal", "restricted")
CATALOG_BUSINESS_CRITICALITIES = ("low", "medium", "high", "critical")

SERVICE_CATALOG_POLICY_INHERITANCE_ORDER = (
    "system",
    "ticket_type",
    "category",
    "service",
    "offering",
    "request_template",
)

CATALOG_POLICY_KINDS = (
    "priority",
    "routing",
    "sla",
    "ola",
    "approval",
    "diagnostic",
    "closure",
    "visibility",
    "notification",
    "reporting",
)

REQUEST_TYPE_LABELS_RU = {
    "incident": "Инцидент",
    "request": "Запрос",
    "service_request": "Запрос услуги",
    "access": "Доступ",
    "consultation": "Консультация",
}

_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,98}[a-z0-9]$|^[a-z0-9]$")


class ServiceCatalogValidationError(ValueError):
    """Raised when catalog input violates the public contract."""


def normalize_catalog_code(value: Any, *, field_name: str = "code") -> str:
    code = str(value or "").strip().lower()
    if not code:
        raise ServiceCatalogValidationError(f"{field_name} is required")
    if not _CODE_RE.match(code):
        raise ServiceCatalogValidationError(
            f"{field_name} must use lowercase latin letters, digits, hyphen or underscore"
        )
    return code


def normalize_lifecycle_status(value: Any, *, default: str = "draft") -> str:
    status = str(value or default).strip().lower()
    if status not in CATALOG_LIFECYCLE_STATUSES:
        raise ServiceCatalogValidationError(f"unsupported lifecycle_status: {status}")
    return status


def normalize_visibility(value: Any, *, default: str = "internal") -> str:
    visibility = str(value or default).strip().lower()
    if visibility not in CATALOG_VISIBILITIES:
        raise ServiceCatalogValidationError(f"unsupported visibility: {visibility}")
    return visibility


def normalize_business_criticality(value: Any, *, default: str = "medium") -> str:
    criticality = str(value or default).strip().lower()
    if criticality not in CATALOG_BUSINESS_CRITICALITIES:
        raise ServiceCatalogValidationError(f"unsupported business_criticality: {criticality}")
    return criticality


def full_offering_code(service_code: Any, offering_code: Any) -> str:
    return f"{normalize_catalog_code(service_code, field_name='service_code')}.{normalize_catalog_code(offering_code, field_name='offering_code')}"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _bool(value: Any) -> bool:
    return bool(value)


def request_type_label(request_type: Any) -> str:
    normalized = str(request_type or "").strip().lower()
    return REQUEST_TYPE_LABELS_RU.get(normalized, normalized or "Запрос")


def serialize_offering_for_requester(offering: dict[str, Any]) -> dict[str, Any]:
    request_type = _text(offering.get("request_type") or offering.get("ticket_type")) or "request"
    approval_required = _bool(offering.get("approval_required"))
    diagnostic_required = _bool(offering.get("diagnostic_consent_required"))
    return {
        "offering_code": _text(offering.get("code") or offering.get("offering_code")),
        "full_code": _text(offering.get("full_code")),
        "title": _text(offering.get("public_title") or offering.get("title") or offering.get("name")),
        "description": _text(offering.get("short_description") or offering.get("description")),
        "request_type": request_type,
        "request_type_label": _text(offering.get("request_type_label")) or request_type_label(request_type),
        "request_template_key": _text(offering.get("request_template_key")),
        "form_schema_version": _text(offering.get("form_schema_version")),
        "approval_required": approval_required,
        "approval_hint": "Потребуется согласование" if approval_required else None,
        "diagnostic_consent_required": diagnostic_required,
        "diagnostic_hint": "Перед диагностикой потребуется согласие" if diagnostic_required else None,
        "expected_response": _text(offering.get("expected_response")),
        "expected_resolution": _text(offering.get("expected_resolution")),
        "requires_attachment": _bool(offering.get("requires_attachment")),
    }


def serialize_service_for_requester(
    service: dict[str, Any],
    *,
    offerings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "service_code": _text(service.get("code") or service.get("service_code")),
        "title": _text(service.get("public_title") or service.get("title") or service.get("name")),
        "description": _text(service.get("short_description") or service.get("description")),
        "icon": _text(service.get("icon")),
        "business_criticality": _text(service.get("business_criticality")),
        "offerings": [
            serialize_offering_for_requester(offering)
            for offering in (offerings or [])
            if str(offering.get("visibility") or "public") in {"public", "internal"}
            and str(offering.get("lifecycle_status") or "published") == "published"
        ],
    }


def policy_ref_fields() -> tuple[str, ...]:
    fields: list[str] = []
    for kind in CATALOG_POLICY_KINDS:
        fields.append(f"default_{kind}_policy_code")
        fields.append(f"{kind}_policy_code")
    fields.append("default_sla_policy_id")
    return tuple(fields)
