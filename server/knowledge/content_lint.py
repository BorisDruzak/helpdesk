from __future__ import annotations

from datetime import datetime
from typing import Any

from knowledge.content_templates import validate_template_body
from knowledge.contracts import REQUESTER_SAFE_VISIBILITIES, lint_requester_safe_publication


INTERNAL_SOURCE_REF_KEYS = {"queue_id", "device_id", "requester_id", "raw_custom_fields", "custom_fields", "internal_runbook", "security_detail"}


def _issue(severity: str, code: str, message: str, suggested_fix: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message, "suggested_fix": suggested_fix}


def _source_refs_are_safe(source_refs: Any) -> bool:
    text = str(source_refs or "").lower()
    return not any(marker in text for marker in INTERNAL_SOURCE_REF_KEYS)


def lint_knowledge_content(
    *,
    item_type: str,
    visibility: str,
    title: str | None,
    summary: str | None,
    body: str | None,
    owner_actor_id: str | None,
    reviewer_actor_id: str | None,
    review_due_at: datetime | None,
    bindings: list[dict[str, Any]] | None = None,
    source_refs: Any = None,
    metadata: dict[str, Any] | None = None,
    acknowledged_warning_codes: set[str] | None = None,
    review_required: bool = True,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    item_type = str(item_type or "article")
    visibility = str(visibility or "support_internal")
    body_text = str(body or "")

    if not str(title or "").strip():
        errors.append(_issue("error", "missing_title", "Knowledge title is required.", "Add a concise title."))
    if not str(summary or "").strip():
        errors.append(_issue("error", "missing_summary", "Knowledge summary is required.", "Add a requester/support-safe summary."))
    if not body_text.strip():
        errors.append(_issue("error", "empty_body", "Knowledge body is required.", "Add reviewed content."))
    if not str(owner_actor_id or "").strip():
        errors.append(_issue("error", "missing_owner", "Knowledge owner is required.", "Assign an owner."))
    if review_required and not str(reviewer_actor_id or "").strip():
        errors.append(_issue("error", "missing_reviewer", "Knowledge reviewer is required.", "Assign a reviewer."))
    if review_due_at is None:
        errors.append(_issue("error", "missing_review_due", "Published knowledge requires a review due date.", "Set review_due_at."))

    template_result = validate_template_body(item_type, body_text)
    if body_text.strip() and not template_result["valid"]:
        warnings.append(
            _issue(
                "warning",
                "missing_required_sections",
                "Knowledge body does not contain all template sections.",
                "Add missing sections: " + ", ".join(template_result["missing_sections"]),
            )
        )

    if visibility in set(REQUESTER_SAFE_VISIBILITIES):
        errors.extend(lint_requester_safe_publication(visibility=visibility, title=title, summary=summary, body=body, metadata=metadata))
        if not _source_refs_are_safe(source_refs):
            errors.append(_issue("error", "unsafe_source_refs", "Requester-safe knowledge cannot expose internal source references.", "Remove internal source references or change visibility."))
        if item_type in {"article", "faq", "service_description"} and not bindings:
            warnings.append(_issue("warning", "missing_self_service_binding", "Requester self-service content should be bound to a service/offering.", "Add a Service Catalog binding."))

    if item_type == "known_error":
        metadata = metadata or {}
        status = metadata.get("status") or metadata.get("known_error_status")
        has_fix = bool(metadata.get("workaround") or metadata.get("permanent_fix") or "Workaround" in body_text or "Permanent fix" in body_text)
        if not status:
            errors.append(_issue("error", "missing_known_error_status", "Known error requires a status.", "Set status or keep it as an internal draft."))
        if not has_fix:
            errors.append(_issue("error", "missing_known_error_fix", "Known error requires workaround/permanent fix or explicit unknown.", "Document a workaround, permanent fix or explicit unknown."))

    acknowledged = acknowledged_warning_codes or set()
    active_warnings = [warning for warning in warnings if warning["code"] not in acknowledged]
    return {"valid": not errors and not active_warnings, "errors": errors, "warnings": active_warnings, "acknowledged_warnings": sorted(acknowledged)}
