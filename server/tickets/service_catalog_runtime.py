"""Runtime Service Catalog resolution for ticket preview/create."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.service_catalog_repo import ServiceCatalogRepo
from tickets.service_catalog_contract import (
    CATALOG_POLICY_KINDS,
    full_offering_code,
    normalize_catalog_code,
    serialize_service_for_requester,
)


class ServiceCatalogResolutionError(ValueError):
    def __init__(self, details: dict[str, Any]):
        super().__init__("invalid service catalog selection")
        self.details = details


@dataclass(frozen=True)
class ServiceCatalogSelection:
    service: dict[str, Any] | None
    offering: dict[str, Any] | None
    selected_by: str
    inferred: bool = False

    @property
    def request_template_key(self) -> str | None:
        return str((self.offering or {}).get("request_template_key") or "").strip() or None


def _policy_code_from_service(service: dict[str, Any] | None, kind: str) -> str | None:
    if not service:
        return None
    return str(service.get(f"default_{kind}_policy_code") or "").strip() or None


def _policy_code_from_offering(offering: dict[str, Any] | None, kind: str) -> str | None:
    if not offering:
        return None
    return str(offering.get(f"{kind}_policy_code") or "").strip() or None


def _apply_catalog_policy_refs(
    template_context: dict[str, Any],
    *,
    service: dict[str, Any] | None,
    offering: dict[str, Any] | None,
) -> dict[str, Any]:
    result = deepcopy(template_context or {})
    sources = result.get("effective_policy_sources") if isinstance(result.get("effective_policy_sources"), dict) else {}
    refs = result.get("policy_refs") if isinstance(result.get("policy_refs"), dict) else {}
    catalog_sources: dict[str, list[dict[str, Any]]] = {}
    for kind in CATALOG_POLICY_KINDS:
        service_code = _policy_code_from_service(service, kind)
        offering_code = _policy_code_from_offering(offering, kind)
        selected_code = offering_code or service_code
        if selected_code and not result.get(f"{kind}_policy_code"):
            result[f"{kind}_policy_code"] = selected_code
            refs[kind] = {
                "code": selected_code,
                "source": "offering" if offering_code else "service",
            }
        if service_code:
            catalog_sources.setdefault(kind, []).append(
                {
                    "code": service_code,
                    "scope_level": "service",
                    "scope_ref": (service or {}).get("code"),
                }
            )
        if offering_code:
            catalog_sources.setdefault(kind, []).append(
                {
                    "code": offering_code,
                    "scope_level": "offering",
                    "scope_ref": (offering or {}).get("full_code"),
                }
            )
    for kind, rows in catalog_sources.items():
        existing = sources.get(kind) if isinstance(sources.get(kind), list) else []
        sources[kind] = [*existing, *rows]
    if refs:
        result["policy_refs"] = refs
    if sources:
        result["effective_policy_sources"] = sources
    return result


def build_catalog_snapshot(
    selection: ServiceCatalogSelection,
    *,
    request_template_key: str | None,
    request_template_version: Any = None,
    effective_policy_refs: dict[str, Any] | None = None,
    effective_policy_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    service = selection.service or {}
    offering = selection.offering or {}
    return {
        "service_id": service.get("service_id"),
        "service_code": service.get("code"),
        "service_title": service.get("public_title") or service.get("name"),
        "offering_id": offering.get("offering_id"),
        "offering_code": offering.get("code"),
        "offering_full_code": offering.get("full_code"),
        "offering_title": offering.get("public_title") or offering.get("name"),
        "request_template_key": request_template_key,
        "request_template_version": request_template_version,
        "ticket_type_code": offering.get("ticket_type_code") or offering.get("request_type") or service.get("default_ticket_type_code"),
        "policy_inheritance_sources": deepcopy(effective_policy_sources or {}),
        "effective_policy_refs": deepcopy(effective_policy_refs or {}),
        "reporting_category": offering.get("reporting_category") or service.get("reporting_category"),
        "business_criticality": service.get("business_criticality"),
        "selected_by": selection.selected_by,
    }


class ServiceCatalogRuntimeResolver:
    def __init__(self, session: Any):
        self.session = session
        self.repo = ServiceCatalogRepo(session)

    async def resolve_selection(
        self,
        *,
        service_code: str | None = None,
        offering_code: str | None = None,
        offering_full_code: str | None = None,
        request_template_key: str | None = None,
        actor_role: str = "requester",
        require_catalog: bool = False,
    ) -> ServiceCatalogSelection:
        full_code_value = str(offering_full_code or "").strip().lower()
        if service_code and offering_code:
            full_code_value = full_offering_code(service_code, offering_code)
        if full_code_value:
            offering = await self.repo.get_offering_by_full_code(full_code_value)
            if not offering:
                raise ServiceCatalogResolutionError({"offering_code": "offering not found"})
            service = await self.repo.get_service_by_code(offering.get("service_code"))
            self._assert_visible(service, offering, actor_role=actor_role)
            return ServiceCatalogSelection(service=service, offering=offering, selected_by=actor_role or "api")

        template_key = str(request_template_key or "").strip()
        if template_key:
            offerings = [
                item
                for item in await self.repo.list_offerings(published_only=True)
                if str(item.get("request_template_key") or "").strip() == template_key
            ]
            if len(offerings) == 1:
                offering = offerings[0]
                service = await self.repo.get_service_by_code(offering.get("service_code"))
                if service and self._is_visible(service, offering, actor_role=actor_role):
                    return ServiceCatalogSelection(service=service, offering=offering, selected_by="inferred", inferred=True)
            if require_catalog:
                raise ServiceCatalogResolutionError({"request_template_key": "catalog offering is required or ambiguous"})

        if require_catalog:
            raise ServiceCatalogResolutionError({"service_code": "service_code and offering_code are required"})
        return ServiceCatalogSelection(service=None, offering=None, selected_by="legacy", inferred=False)

    def _is_visible(self, service: dict[str, Any] | None, offering: dict[str, Any] | None, *, actor_role: str) -> bool:
        if not service or not offering:
            return False
        if service.get("lifecycle_status") != "published" or offering.get("lifecycle_status") != "published":
            return actor_role in {"admin", "support", "auditor"}
        if actor_role in {"admin", "support", "auditor"}:
            return True
        return service.get("visibility") == "public" and offering.get("visibility") == "public"

    def _assert_visible(self, service: dict[str, Any] | None, offering: dict[str, Any] | None, *, actor_role: str) -> None:
        if not self._is_visible(service, offering, actor_role=actor_role):
            raise ServiceCatalogResolutionError({"service_code": "service or offering is not visible"})

    async def current_catalog_for_requester(self) -> dict[str, Any]:
        services = [
            service
            for service in await self.repo.list_services(published_only=True)
            if service.get("visibility") == "public"
        ]
        offerings = [
            offering
            for offering in await self.repo.list_offerings(published_only=True)
            if offering.get("visibility") == "public"
        ]
        by_service: dict[str, list[dict[str, Any]]] = {}
        for offering in offerings:
            by_service.setdefault(str(offering.get("service_code") or ""), []).append(offering)
        return {
            "catalog_version": "runtime",
            "services": [
                serialize_service_for_requester(service, offerings=by_service.get(str(service.get("code") or ""), []))
                for service in services
            ],
            "fallback": None,
        }

    async def apply_to_validated_submission(
        self,
        validated_submission: dict[str, Any],
        selection: ServiceCatalogSelection,
    ) -> dict[str, Any]:
        if not selection.service and not selection.offering:
            return validated_submission
        result = deepcopy(validated_submission)
        template_context = result.get("template_context") if isinstance(result.get("template_context"), dict) else {}
        template_context = _apply_catalog_policy_refs(
            template_context,
            service=selection.service,
            offering=selection.offering,
        )
        repo = HelpdeskPolicyRepo(self.session)
        for kind in CATALOG_POLICY_KINDS:
            policy_ref = template_context.get("policy_refs") if isinstance(template_context.get("policy_refs"), dict) else {}
            ref = policy_ref.get(kind) if isinstance(policy_ref, dict) else None
            code = str(ref.get("code") if isinstance(ref, dict) else ref or "").strip()
            if not code:
                continue
            effective = await repo.resolve_policy_ref(kind=kind, code=code, source=f"service_catalog.{kind}")
            config = effective.get("config") if isinstance(effective, dict) else {}
            if isinstance(config, dict) and config:
                existing = template_context.get(f"{kind}_policy") if isinstance(template_context.get(f"{kind}_policy"), dict) else {}
                template_context[f"{kind}_policy"] = {**existing, **deepcopy(config)}
        offering = selection.offering or {}
        service = selection.service or {}
        if offering.get("ticket_type_code") or offering.get("request_type"):
            result["ticket_type"] = offering.get("ticket_type_code") or offering.get("request_type")
            template_context["ticket_type"] = result["ticket_type"]
        if offering.get("request_template_key"):
            result["request_template_key"] = offering.get("request_template_key")
            template_context["key"] = offering.get("request_template_key")
            template_context["template_code"] = offering.get("request_template_key")
        template_context["service_catalog"] = build_catalog_snapshot(
            selection,
            request_template_key=str(template_context.get("key") or result.get("request_template_key") or ""),
            request_template_version=template_context.get("request_template_version"),
            effective_policy_refs=template_context.get("policy_refs") if isinstance(template_context.get("policy_refs"), dict) else {},
            effective_policy_sources=template_context.get("effective_policy_sources") if isinstance(template_context.get("effective_policy_sources"), dict) else {},
        )
        result["template_context"] = template_context
        result["catalog_fields"] = {
            "catalog_service_id": service.get("service_id"),
            "catalog_offering_id": offering.get("offering_id"),
            "service_code": service.get("code"),
            "offering_code": offering.get("full_code") or offering.get("code"),
            "request_type": offering.get("request_type") or offering.get("ticket_type_code"),
            "business_criticality": service.get("business_criticality"),
            "reporting_category": offering.get("reporting_category") or service.get("reporting_category"),
            "service_owner_actor_id": service.get("owner_actor_id"),
            "support_group_code": service.get("support_group_code"),
        }
        return result

    async def resolve_effective_template_for_catalog(
        self,
        selection: ServiceCatalogSelection,
        *,
        fallback_template_key: str | None,
    ) -> dict[str, Any]:
        template_key = selection.request_template_key or fallback_template_key
        if not template_key:
            return {}
        return await HelpdeskPolicyRepo(self.session).resolve_effective_request_template(
            template_code=normalize_catalog_code(template_key, field_name="request_template_key"),
            raise_if_missing=False,
        )
