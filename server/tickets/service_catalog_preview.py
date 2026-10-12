"""Requester-safe Service Catalog dry-run preview."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select
from app.db.models import TicketQueue

from tickets.form_catalog import DEFAULT_TICKET_FORM_PACK_KEY
from tickets.helpdesk_policy_runtime import apply_effective_registry_policies
from tickets.policy_health_service import PolicyHealthService
from tickets.request_template_submission import resolve_create_form_submission
from tickets.service_catalog_contract import request_type_label
from tickets.service_catalog_runtime import ServiceCatalogResolutionError, ServiceCatalogRuntimeResolver


class ServiceCatalogPreviewError(ValueError):
    def __init__(self, details: dict[str, Any]):
        super().__init__("invalid service catalog preview")
        self.details = details


def _minutes_label(minutes: Any) -> str | None:
    try:
        value = int(minutes)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if value < 60:
        return f"до {value} минут"
    if value % 1440 == 0:
        days = value // 1440
        return f"до {days} дн."
    if value % 60 == 0:
        hours = value // 60
        return f"до {hours} ч"
    hours = value // 60
    rest = value % 60
    return f"до {hours} ч {rest} мин"


def _safe_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


async def simulate_service_catalog_processing(session: Any, payload: dict[str, Any], *, scenario_snapshot=None, allow_draft_offering: bool = False):
    resolver = ServiceCatalogRuntimeResolver(session)
    try:
        selection = await resolver.resolve_selection(
            service_code=_safe_text(payload.get("service_code")),
            offering_code=_safe_text(payload.get("offering_code")),
            offering_full_code=_safe_text(payload.get("offering_full_code") or payload.get("full_offering_code")),
            request_template_key=_safe_text(payload.get("request_template_key")),
            # Internal admin candidate preview only; never read this authority
            # from a requester payload or scenario answer.
            actor_role="admin" if allow_draft_offering else "requester",
            require_catalog=True,
        )
    except ServiceCatalogResolutionError as exc:
        raise ServiceCatalogPreviewError(exc.details) from exc

    if allow_draft_offering and (not selection.service or not selection.offering
            or selection.service.get("lifecycle_status") != "published"
            or selection.service.get("visibility") != "public"
            or selection.offering.get("visibility") != "public"
            or selection.offering.get("lifecycle_status") not in {"draft", "published"}):
        raise ServiceCatalogPreviewError({"offering_code": "draft candidate must have a published public parent and public visibility"})

    template_key = selection.request_template_key or _safe_text(payload.get("request_template_key"))
    if not template_key:
        raise ServiceCatalogPreviewError({"request_template_key": "request template is required"})
    form_key = _safe_text(payload.get("form_key")) or template_key
    form_payload = payload.get("form_payload") if isinstance(payload.get("form_payload"), dict) else {}
    try:
        validated = await resolve_create_form_submission(
            session,
            pack_key=_safe_text(payload.get("form_pack_key")) or DEFAULT_TICKET_FORM_PACK_KEY,
            pack_version=_safe_text(payload.get("form_pack_version")),
            form_key=form_key,
            request_template_key=template_key,
            raw_values=form_payload,
        )
        if scenario_snapshot is not None:
            from tickets.request_scenario_submission import augment_scenario_submission
            validated = augment_scenario_submission(validated, scenario_snapshot)
        validated = await resolver.apply_to_validated_submission(validated, selection)
        validated = await apply_effective_registry_policies(session, validated)
        if scenario_snapshot is not None:
            from tickets.request_scenario_processing import apply_scenario_policy_refs
            validated = await apply_scenario_policy_refs(session, validated, scenario_snapshot.get("policy_refs"))
    except ValueError as exc:
        details = exc.args[0] if exc.args else "invalid form payload"
        raise ServiceCatalogPreviewError({"form_payload": details}) from exc

    simulate_payload = {
        "service_code": selection.service.get("code") if selection.service else None,
        "offering_code": selection.offering.get("code") if selection.offering else None,
        "offering_full_code": selection.offering.get("full_code") if selection.offering else None,
        "template_code": template_key,
        "request_template_key": template_key,
        "request_form_data": deepcopy(form_payload),
        "custom_fields": deepcopy(payload.get("custom_fields") if isinstance(payload.get("custom_fields"), dict) else {}),
        "device_metadata": deepcopy(payload.get("device_metadata") if isinstance(payload.get("device_metadata"), dict) else {}),
        "requester_context": deepcopy(payload.get("requester_context") if isinstance(payload.get("requester_context"), dict) else {}),
        "description": _safe_text(payload.get("description")) or "",
        "diagnostic_consent": deepcopy(payload.get("diagnostic_consent") if isinstance(payload.get("diagnostic_consent"), dict) else {}),
    }
    simulation = await PolicyHealthService(session).simulate(simulate_payload, validated_submission=validated)
    return selection, simulation


async def lock_active_scenario_queue(session: Any, queue_id: int | None) -> bool:
    """Refresh and retain the selected queue through the caller's transaction."""
    if queue_id is None:
        return False
    queue = await session.scalar(select(TicketQueue).where(TicketQueue.id == queue_id)
                                 .with_for_update(read=True).execution_options(populate_existing=True))
    return queue is not None and queue.is_active


async def build_requester_service_catalog_preview(session: Any, payload: dict[str, Any], *, scenario_snapshot=None) -> dict[str, Any]:
    selection, simulation = await simulate_service_catalog_processing(session, payload, scenario_snapshot=scenario_snapshot)

    service = selection.service or {}
    offering = selection.offering or {}
    sla = simulation.get("sla") if isinstance(simulation.get("sla"), dict) else {}
    approval = simulation.get("approval") if isinstance(simulation.get("approval"), dict) else {}
    diagnostic = simulation.get("diagnostic") if isinstance(simulation.get("diagnostic"), dict) else {}
    routing = simulation.get("routing") if isinstance(simulation.get("routing"), dict) else {}
    warnings = [str(item) for item in simulation.get("warnings") or [] if str(item or "").strip()]
    blockers: list[str] = []
    if not routing.get("queue_code") and routing.get("queue_id") is None:
        blockers.append("Не удалось определить маршрут обращения.")
    if scenario_snapshot is not None and not await lock_active_scenario_queue(session, routing.get("queue_id")):
        blockers.append("Маршрут обращения недоступен. Обратитесь в поддержку.")

    first_response = _minutes_label(sla.get("first_response_min"))
    resolution = _minutes_label(sla.get("resolution_min"))
    request_type = _safe_text(offering.get("request_type") or offering.get("ticket_type_code") or simulation.get("template_code")) or "request"
    approval_required = bool(approval.get("required"))
    diagnostic_required = bool(diagnostic.get("suggested_playbooks") or diagnostic.get("auto_run_triggers"))
    consent_required = bool(
        offering.get("diagnostic_consent_required")
        or diagnostic_required
    )

    return {
        "ok": not blockers,
        "service": {
            "code": service.get("code"),
            "title": service.get("public_title") or service.get("name") or service.get("code"),
        },
        "offering": {
            "code": offering.get("code"),
            "full_code": offering.get("full_code"),
            "title": offering.get("public_title") or offering.get("name") or offering.get("code"),
        },
        "request_type_label": request_type_label(request_type),
        "public_status_after_create": "Новое обращение",
        "expected_first_response": first_response,
        "expected_resolution": resolution,
        "approval": {
            "required": approval_required,
            "text": "Потребуется согласование" if approval_required else "Согласование не требуется",
        },
        "diagnostics": {
            "required": diagnostic_required,
            "consent_required": consent_required,
            "text": "Может потребоваться диагностика устройства" if consent_required else "Диагностика не требуется до отправки",
        },
        "next_action": "После отправки обращение попадет в поддержку. Детали маршрута скрыты из публичной проверки.",
        "warnings": warnings,
        "blockers": blockers,
        "would_create_ticket": False,
    }
