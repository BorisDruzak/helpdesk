"""Publication gates for Service Catalog services and offerings."""

from __future__ import annotations

from typing import Any

from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.service_catalog_repo import ServiceCatalogRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from tickets.service_catalog_contract import CATALOG_POLICY_KINDS


def _issue(
    severity: str,
    kind: str,
    object_type: str,
    object_code: str,
    path: str,
    message: str,
    *,
    suggested_fix: str | None = None,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "kind": kind,
        "object_type": object_type,
        "object_code": object_code,
        "path": path,
        "message": message,
        "suggested_fix": suggested_fix,
    }


class ServiceCatalogPublicationService:
    def __init__(self, session: Any):
        self.session = session
        self.repo = ServiceCatalogRepo(session)

    async def validate_service(self, service_code: str) -> dict[str, Any]:
        service = await self.repo.get_service_by_code(service_code)
        if not service:
            raise ValueError("service not found")
        queues = await TicketAdminConfigRepo(self.session).list_queues(include_inactive=False)
        queue_ids = {getattr(queue, "id", None) for queue in queues}
        issues: list[dict[str, Any]] = []
        code = str(service.get("code") or "")
        if not service.get("public_title") and not service.get("name"):
            issues.append(_issue("error", "missing_required_field", "service", code, "public_title", "Public title is required"))
        if not (service.get("owner_actor_id") or service.get("owner_person_id") or service.get("owner_queue_id")):
            issues.append(_issue("error", "missing_owner", "service", code, "owner", "Service owner is required"))
        default_queue_id = service.get("default_queue_id") or service.get("owner_queue_id")
        metadata = service.get("metadata") if isinstance(service.get("metadata"), dict) else {}
        if default_queue_id is None and not metadata.get("informational") and not metadata.get("no_ticket"):
            issues.append(_issue("error", "missing_queue", "service", code, "default_queue_id", "Support/default queue is required"))
        if default_queue_id is not None and default_queue_id not in queue_ids:
            issues.append(_issue("error", "invalid_reference", "service", code, "default_queue_id", "Default queue is not active"))
        if service.get("visibility") == "public" and not service.get("short_description"):
            issues.append(_issue("warning", "missing_public_description", "service", code, "short_description", "Public service should have a short safe description"))
        issues.extend(await self._policy_ref_issues("service", code, service, default_prefix=True))
        status = _status_from_issues(issues)
        return {"status": status, "issues": issues, "blocking": any(item["severity"] in {"critical", "error"} for item in issues)}

    async def validate_offering(self, full_code: str) -> dict[str, Any]:
        offering = await self.repo.get_offering_by_full_code(full_code)
        if not offering:
            raise ValueError("offering not found")
        service = await self.repo.get_service_by_code(offering.get("service_code"))
        issues: list[dict[str, Any]] = []
        code = str(offering.get("full_code") or full_code)
        if service and service.get("lifecycle_status") == "retired":
            issues.append(_issue("error", "invalid_parent", "offering", code, "service", "Parent service is retired"))
        if not offering.get("public_title") and not offering.get("name"):
            issues.append(_issue("error", "missing_required_field", "offering", code, "public_title", "Public title is required"))
        if not (offering.get("request_type") or offering.get("ticket_type_code")):
            issues.append(_issue("error", "missing_request_type", "offering", code, "request_type", "Request/ticket type is required"))
        template_key = offering.get("request_template_key")
        metadata = offering.get("metadata") if isinstance(offering.get("metadata"), dict) else {}
        if not template_key and not metadata.get("no_form") and not metadata.get("no_ticket"):
            issues.append(_issue("error", "missing_template", "offering", code, "request_template_key", "Request template is required"))
        if template_key:
            effective = await HelpdeskPolicyRepo(self.session).resolve_effective_request_template(
                template_code=str(template_key),
                raise_if_missing=False,
            )
            if not effective:
                issues.append(_issue("error", "invalid_reference", "offering", code, "request_template_key", "Request template is not active"))
        if offering.get("visibility") == "public" and not offering.get("short_description"):
            issues.append(_issue("warning", "missing_public_description", "offering", code, "short_description", "Public offering should have a short safe description"))
        issues.extend(await self._policy_ref_issues("offering", code, offering, default_prefix=False))
        status = _status_from_issues(issues)
        return {"status": status, "issues": issues, "blocking": any(item["severity"] in {"critical", "error"} for item in issues)}

    async def _policy_ref_issues(
        self,
        object_type: str,
        object_code: str,
        payload: dict[str, Any],
        *,
        default_prefix: bool,
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        policy_repo = HelpdeskPolicyRepo(self.session)
        for kind in CATALOG_POLICY_KINDS:
            field_name = f"{'default_' if default_prefix else ''}{kind}_policy_code"
            code = str(payload.get(field_name) or "").strip()
            if not code:
                continue
            effective = await policy_repo.resolve_policy_ref(kind=kind, code=code, source=f"service_catalog_publication.{object_type}")
            if not effective.get("sources"):
                issues.append(
                    _issue(
                        "error",
                        "invalid_reference",
                        object_type,
                        object_code,
                        field_name,
                        f"{kind} policy is not active or does not exist",
                    )
                )
                continue
            config = effective.get("config") if isinstance(effective.get("config"), dict) else {}
            if kind == "approval" and _approval_requires_approvers(config):
                issues.append(
                    _issue(
                        "error",
                        "invalid_reference",
                        object_type,
                        object_code,
                        field_name,
                        "Approval policy is required but has no resolvable approver source",
                        suggested_fix="Configure explicit users, roles, groups or approver_source before publication.",
                    )
                )
        return issues


def _status_from_issues(issues: list[dict[str, Any]]) -> str:
    if any(item["severity"] in {"critical", "error"} for item in issues):
        return "error"
    if any(item["severity"] == "warning" for item in issues):
        return "warning"
    return "ok"


def _approval_requires_approvers(config: dict[str, Any]) -> bool:
    if not config.get("required"):
        return False
    source = config.get("approver_source") if isinstance(config.get("approver_source"), dict) else {}
    if source:
        return False
    return not any(
        config.get(key)
        for key in (
            "approvers",
            "approver_user_ids",
            "approver_ids",
            "roles",
            "role_codes",
            "groups",
            "group_codes",
        )
    )
