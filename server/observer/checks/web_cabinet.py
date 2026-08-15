"""Phase D web-cabinet observer integrity checks."""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ObserverTrace, Ticket
from app.repos.observer_integrity_repo import ObserverIntegrityEventInput
from customer_history.projection_service import CustomerHistoryProjectionService
from domain_ports import (
    DomainPortContainer,
    RegistryInvalidProjection,
    RegistryNotFound,
    RegistryObserverReadContext,
    RegistryPort,
    RegistryUnavailable,
    RequesterProfileCompletionProjection,
    RequesterRef,
)
from observer.checks.types import ObserverIntegrityCheckResult, limit_plus_one_window


SOURCE = "observer.web_cabinet"
WEB_REQUESTER_ACCOUNT_MODES = {
    "browser_no_device",
    "confirmed_binding",
    "registration_pending",
    "verified_other_account",
}
WEB_REQUEST_CONTEXTS = {
    "authenticated_requester_workspace",
    "no_device",
    "requester_portal",
}
REQUESTER_KNOWLEDGE_SURFACES = {"", "requester_portal", "agent_gui"}
CREATOR_KNOWLEDGE_VISIBILITY_SCOPE = "creator_visible"
CREATOR_KNOWLEDGE_AUDIENCE_SCOPE = "creator"
SUCCESSFUL_CREATE_EVENT_TYPES = ("ticket_create_succeeded", "ticket_create_created")
SUCCESSFUL_CREATE_RESULTS = ("created", "ok", "success", "succeeded")


def _custom_fields(ticket: Ticket) -> dict[str, Any]:
    return ticket.custom_fields if isinstance(ticket.custom_fields, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _ticket_context(ticket: Ticket) -> dict[str, Any]:
    return _dict(_custom_fields(ticket).get("ticket_context"))


def _is_web_requester_ticket(ticket: Ticket) -> bool:
    custom_fields = _custom_fields(ticket)
    account_mode = str(ticket.requester_account_mode or custom_fields.get("requester_account_mode") or "").strip()
    if account_mode in WEB_REQUESTER_ACCOUNT_MODES:
        return True
    request_context = str(custom_fields.get("request_context") or "").strip()
    if request_context in WEB_REQUEST_CONTEXTS:
        return True
    no_device = custom_fields.get("no_device") if isinstance(custom_fields.get("no_device"), dict) else {}
    if no_device.get("created_from") == "requester_portal":
        return True
    return bool(custom_fields.get("requester_context_snapshot"))


def _has_ticket_context_v1(ticket: Ticket) -> bool:
    custom_fields = _custom_fields(ticket)
    context = custom_fields.get("ticket_context")
    return isinstance(context, dict) and context.get("schema") == "ticket_context_v1"


def _context_target_device_id(context: dict[str, Any]) -> str | None:
    diagnostic_target = _dict(context.get("diagnostic_target"))
    target_device = _dict(context.get("target_device"))
    return _clean(diagnostic_target.get("device_id")) or _clean(target_device.get("device_id"))


def _context_diagnostic_source(context: dict[str, Any], custom_fields: dict[str, Any]) -> str | None:
    diagnostic_target = _dict(context.get("diagnostic_target"))
    return (
        _clean(diagnostic_target.get("source"))
        or _clean(context.get("diagnostic_target_source"))
        or _clean(custom_fields.get("diagnostic_target_source"))
    )


def _created_on_behalf(context: dict[str, Any], custom_fields: dict[str, Any]) -> bool:
    on_behalf = _dict(context.get("on_behalf"))
    creator_id = _clean(_dict(context.get("creator")).get("person_id")) or _clean(custom_fields.get("creator_person_id"))
    affected_id = _clean(_dict(context.get("affected")).get("person_id")) or _clean(custom_fields.get("affected_person_id"))
    return bool(
        context.get("created_on_behalf")
        or custom_fields.get("created_on_behalf")
        or on_behalf.get("enabled")
        or (creator_id and affected_id and creator_id != affected_id)
    )


def _profile_completion_snapshot(context: dict[str, Any], custom_fields: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    requester_context = _dict(context.get("requester_context"))
    completion = _dict(requester_context.get("profile_completion"))
    if completion:
        return completion, "ticket_context"
    snapshot = _dict(custom_fields.get("requester_context_snapshot"))
    completion = _dict(snapshot.get("profile_completion"))
    if completion:
        return completion, "requester_context_snapshot"
    completion = _dict(custom_fields.get("profile_completion"))
    if completion:
        return completion, "custom_fields"
    return {}, None


def _profile_schema_version(context: dict[str, Any], custom_fields: dict[str, Any]) -> tuple[str | None, str | None]:
    requester_context = _dict(context.get("requester_context"))
    profile_schema = _dict(requester_context.get("profile_schema"))
    version = _clean(profile_schema.get("version"))
    if version:
        return version, "ticket_context"
    snapshot = _dict(custom_fields.get("requester_context_snapshot"))
    profile_schema = _dict(snapshot.get("profile_schema"))
    version = _clean(profile_schema.get("version"))
    if version:
        return version, "requester_context_snapshot"
    return _clean(custom_fields.get("profile_schema_version")), "custom_fields"


def _form_schema_version(context: dict[str, Any], custom_fields: dict[str, Any]) -> tuple[str | None, str | None, bool]:
    form = _dict(context.get("form"))
    version = _clean(form.get("form_schema_version")) or _clean(form.get("resolved_form_schema_version"))
    if version:
        return version, "ticket_context.form", True
    version = _clean(custom_fields.get("resolved_form_schema_version"))
    if version:
        return version, "custom_fields.resolved_form_schema_version", True
    request_template = _dict(custom_fields.get("request_template"))
    version = _clean(request_template.get("form_schema_version"))
    if version:
        return version, "custom_fields.request_template", True
    request_form = _dict(custom_fields.get("request_form"))
    version = _clean(request_form.get("form_schema_version"))
    if version:
        return version, "custom_fields.request_form", True
    has_form = bool(
        form
        or request_form
        or _clean(custom_fields.get("request_form_key"))
        or _clean(custom_fields.get("resolved_template_key"))
    )
    return None, None, has_form


def _profile_completion_blocks(completion: dict[str, Any]) -> bool:
    if not completion:
        return False
    if completion.get("blocks") is True:
        return True
    if completion.get("complete") is False and str(completion.get("status") or "").strip() in {"", "required"}:
        return True
    missing = completion.get("missing_fields")
    return completion.get("complete") is False and isinstance(missing, list) and bool(missing)


def _profile_gate_bypass_allowed(context: dict[str, Any], custom_fields: dict[str, Any]) -> bool:
    form = _dict(context.get("form"))
    availability = _dict(form.get("availability_policy"))
    if not availability:
        request_form = _dict(custom_fields.get("request_form"))
        availability = _dict(request_form.get("availability_policy"))
    return availability.get("available_without_completed_profile") is True


def _requested_target_device_id(custom_fields: dict[str, Any]) -> str | None:
    for key in (
        "requested_target_device_id",
        "browser_target_device_id",
        "unsafe_target_device_id",
    ):
        value = _clean(custom_fields.get(key))
        if value:
            return value
    for key in ("request_payload", "request_body", "ticket_context_input"):
        value = _clean(_dict(custom_fields.get(key)).get("target_device_id"))
        if value:
            return value
    return None


def _knowledge_attempts(custom_fields: dict[str, Any]) -> list[dict[str, Any]]:
    attempts = custom_fields.get("knowledge_attempts")
    if not isinstance(attempts, list):
        return []
    return [item for item in attempts if isinstance(item, dict)]


def _knowledge_item_ref(item: dict[str, Any]) -> str | None:
    item_id = _clean(item.get("item_id"))
    if not item_id:
        return None
    return f"knowledge:{item_id[:8]}"


def _requester_side_knowledge_attempt(item: dict[str, Any]) -> bool:
    return str(item.get("surface") or "").strip().lower() in REQUESTER_KNOWLEDGE_SURFACES


def _invalid_on_behalf_knowledge_attempts(custom_fields: dict[str, Any]) -> list[dict[str, Any]]:
    invalid: list[dict[str, Any]] = []
    for item in _knowledge_attempts(custom_fields):
        if not _requester_side_knowledge_attempt(item):
            continue
        visibility_scope = str(item.get("visibility_scope") or "").strip().lower()
        audience_scope = str(item.get("audience_scope") or "").strip().lower()
        if not visibility_scope and not audience_scope:
            continue
        if (
            visibility_scope != CREATOR_KNOWLEDGE_VISIBILITY_SCOPE
            or audience_scope != CREATOR_KNOWLEDGE_AUDIENCE_SCOPE
        ):
            invalid.append(
                {
                    "item_ref": _knowledge_item_ref(item),
                    "surface": str(item.get("surface") or "requester_portal").strip() or "requester_portal",
                    "visibility_scope": visibility_scope or None,
                    "audience_scope": audience_scope or None,
                }
            )
    return invalid


def _customer_history_projection_issue(payload: Any) -> tuple[list[str], dict[str, Any]]:
    if not isinstance(payload, dict):
        return ["payload"], {
            "payload_type": type(payload).__name__,
            "projection_event_count": 0,
            "sources": [],
        }
    missing: list[str] = []
    ticket_ref = _clean(payload.get("ticket_ref"))
    if not ticket_ref:
        missing.append("ticket_ref")

    events_raw = payload.get("events")
    events = events_raw if isinstance(events_raw, list) else []
    if not events:
        missing.append("events")

    ticket_created = False
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("source") == "ticket" and event.get("event_type") == "ticket_created":
            ticket_created = True
            break
    if not ticket_created:
        missing.append("events.ticket_created")

    sources_raw = payload.get("sources")
    sources = [str(item) for item in sources_raw if item] if isinstance(sources_raw, list) else []
    if "ticket" not in sources:
        missing.append("sources.ticket")

    redaction_report = _dict(payload.get("redaction_report"))
    if redaction_report.get("role") != "support":
        missing.append("redaction_report.role")

    return missing, {
        "ticket_ref_present": bool(ticket_ref),
        "projection_event_count": len(events),
        "reported_count": payload.get("count") if isinstance(payload.get("count"), int) else None,
        "sources": sorted(set(sources))[:12],
        "redaction_role": redaction_report.get("role"),
    }


async def _customer_history_missing_event(
    session: AsyncSession,
    *,
    ticket: Ticket,
    device_id: str | None,
    run_id: str | None,
) -> ObserverIntegrityEventInput | None:
    try:
        payload = await CustomerHistoryProjectionService(session).history_for_ticket(
            ticket.ticket_id,
            actor_context={"actor_id": SOURCE, "actor_role": "support"},
            role="support",
            limit=20,
        )
    except Exception as exc:  # pragma: no cover - exercised through integrity behavior, not exception taxonomy.
        return ObserverIntegrityEventInput(
            event_type="missing_customer_history_for_ticket",
            severity="medium",
            source=SOURCE,
            dedupe_key=f"missing_customer_history_for_ticket:{ticket.ticket_id}",
            ticket_id=ticket.ticket_id,
            device_id=device_id or ticket.device_id,
            actor_role="requester",
            expected="Every web requester ticket must be projectable through Customer History with a support-safe ticket_created event.",
            actual="Customer History projection raised before producing ticket history.",
            evidence={
                "projection_error_type": exc.__class__.__name__,
                "missing_fields": ["projection"],
            },
            runbook="docs/runbooks/observer_web_cabinet.md",
            run_id=run_id,
        )

    missing, evidence = _customer_history_projection_issue(payload)
    if not missing:
        return None
    return ObserverIntegrityEventInput(
        event_type="missing_customer_history_for_ticket",
        severity="medium",
        source=SOURCE,
        dedupe_key=f"missing_customer_history_for_ticket:{ticket.ticket_id}",
        ticket_id=ticket.ticket_id,
        device_id=device_id or ticket.device_id,
        actor_role="requester",
        expected="Every web requester ticket must be projectable through Customer History with ticket_ref, ticket source and a support-safe ticket_created event.",
        actual="Customer History projection for this web requester ticket is missing required support-safe ticket history fields.",
        evidence={
            **evidence,
            "missing_fields": missing,
        },
        runbook="docs/runbooks/observer_web_cabinet.md",
        run_id=run_id,
    )


async def _has_create_observer_trace(session: AsyncSession, ticket_id: str) -> bool:
    count = int(
        await session.scalar(
            select(func.count())
            .select_from(ObserverTrace)
            .where(
                ObserverTrace.ticket_id == ticket_id,
                ObserverTrace.root_kind == "requester_web",
                ObserverTrace.status == "succeeded",
                ObserverTrace.attrs_json["source"].astext == "requester_ticket_create",
                ObserverTrace.attrs_json["event_type"].astext.in_(SUCCESSFUL_CREATE_EVENT_TYPES),
                ObserverTrace.attrs_json["result"].astext.in_(SUCCESSFUL_CREATE_RESULTS),
            )
        )
        or 0
    )
    return count > 0


async def _recompute_profile_completion(
    registry_port: RegistryPort,
    *,
    person_id: str | None,
) -> tuple[dict[str, Any], str | None, RegistryUnavailable | RegistryInvalidProjection | None]:
    if not person_id:
        return {}, None, None
    try:
        person = RequesterRef(external_id=person_id)
    except ValidationError:
        return {}, None, RegistryInvalidProjection()
    result = await registry_port.requester_profile_completion(
        RegistryObserverReadContext(source=SOURCE),
        person,
    )
    if isinstance(result, RequesterProfileCompletionProjection):
        return (
            {
                "complete": result.complete,
                "blocks": result.blocks,
                "status": result.status,
                "missing_fields": [{"key": key} for key in result.missing_field_keys],
            },
            "registry_recomputed",
            None,
        )
    if isinstance(result, RegistryNotFound):
        return {}, None, None
    if isinstance(result, (RegistryUnavailable, RegistryInvalidProjection)):
        return {}, None, result
    return {}, None, RegistryInvalidProjection()


async def _web_invariant_events(
    session: AsyncSession,
    *,
    registry_port: RegistryPort,
    ticket: Ticket,
    custom_fields: dict[str, Any],
    context: dict[str, Any],
    run_id: str | None,
) -> list[ObserverIntegrityEventInput]:
    events: list[ObserverIntegrityEventInput] = []
    target_device_id = _context_target_device_id(context)
    source = _context_diagnostic_source(context, custom_fields)
    creator_id = _clean(_dict(context.get("creator")).get("person_id")) or _clean(custom_fields.get("creator_person_id"))
    affected_id = _clean(_dict(context.get("affected")).get("person_id")) or _clean(custom_fields.get("affected_person_id"))

    completion, completion_source = _profile_completion_snapshot(context, custom_fields)
    if not completion:
        completion, completion_source, source_state = await _recompute_profile_completion(
            registry_port,
            person_id=creator_id or _clean(getattr(ticket, "requester_person_id", None)),
        )
        if source_state is not None:
            outcome = "unavailable" if isinstance(source_state, RegistryUnavailable) else "invalid"
            events.append(
                ObserverIntegrityEventInput(
                    event_type=f"profile_completion_registry_{outcome}",
                    severity="medium",
                    source=SOURCE,
                    dedupe_key=f"profile_completion_registry_{outcome}:{ticket.ticket_id}",
                    ticket_id=ticket.ticket_id,
                    device_id=ticket.device_id,
                    actor_role="requester",
                    expected="Observer profile-completion recomputation must receive a valid RegistryPort projection.",
                    actual=f"RegistryPort returned typed {outcome} profile-completion state.",
                    evidence={
                        "profile_completion_source": "registry_port",
                        "registry_outcome": outcome,
                        "registry_code": source_state.code,
                    },
                    runbook="docs/runbooks/observer_web_cabinet.md",
                    run_id=run_id,
                )
            )
    if _profile_completion_blocks(completion) and not _profile_gate_bypass_allowed(context, custom_fields):
        missing = completion.get("missing_fields") if isinstance(completion.get("missing_fields"), list) else []
        events.append(
            ObserverIntegrityEventInput(
                event_type="profile_incomplete_normal_ticket_created",
                severity="high",
                source=SOURCE,
                dedupe_key=f"profile_incomplete_normal_ticket_created:{ticket.ticket_id}",
                ticket_id=ticket.ticket_id,
                device_id=ticket.device_id,
                actor_role="requester",
                expected="Normal web requester ticket creation must be blocked while profile_completion.blocks is true.",
                actual="A web requester ticket exists with incomplete profile completion evidence.",
                evidence={
                    "requester_account_mode": ticket.requester_account_mode,
                    "request_context": custom_fields.get("request_context"),
                    "profile_completion_complete": completion.get("complete"),
                    "profile_completion_blocks": completion.get("blocks"),
                    "profile_completion_status": completion.get("status"),
                    "profile_completion_source": completion_source,
                    "missing_field_keys": [
                        item.get("key")
                        for item in missing
                        if isinstance(item, dict) and item.get("key")
                    ][:12],
                },
                runbook="docs/runbooks/observer_web_cabinet.md",
                run_id=run_id,
            )
        )

    profile_schema_version, profile_schema_source = _profile_schema_version(context, custom_fields)
    if not profile_schema_version:
        events.append(
            ObserverIntegrityEventInput(
                event_type="web_ticket_missing_profile_schema_version",
                severity="high",
                source=SOURCE,
                dedupe_key=f"web_ticket_missing_profile_schema_version:{ticket.ticket_id}",
                ticket_id=ticket.ticket_id,
                device_id=target_device_id or ticket.device_id,
                actor_role="requester",
                expected="Every web requester ticket must keep the server-owned requester profile schema version used for profile completion.",
                actual="Requester context did not include profile_schema.version.",
                evidence={
                    "has_ticket_context_requester_context": bool(_dict(context.get("requester_context"))),
                    "has_requester_context_snapshot": bool(_dict(custom_fields.get("requester_context_snapshot"))),
                    "profile_schema_source": profile_schema_source,
                },
                runbook="docs/runbooks/observer_web_cabinet.md",
                run_id=run_id,
            )
        )

    form_schema_version, form_schema_source, has_form_snapshot = _form_schema_version(context, custom_fields)
    if has_form_snapshot and not form_schema_version:
        events.append(
            ObserverIntegrityEventInput(
                event_type="web_ticket_missing_form_schema_version",
                severity="high",
                source=SOURCE,
                dedupe_key=f"web_ticket_missing_form_schema_version:{ticket.ticket_id}",
                ticket_id=ticket.ticket_id,
                device_id=target_device_id or ticket.device_id,
                actor_role="requester",
                expected="Every web requester ticket with a dynamic request form must keep the resolved form schema version.",
                actual="Request form snapshot did not include a resolved form schema version.",
                evidence={
                    "has_ticket_context_form": bool(_dict(context.get("form"))),
                    "has_request_form_snapshot": bool(_dict(custom_fields.get("request_form"))),
                    "request_form_key_present": bool(_clean(custom_fields.get("request_form_key"))),
                    "form_schema_source": form_schema_source,
                },
                runbook="docs/runbooks/observer_web_cabinet.md",
                run_id=run_id,
            )
        )

    if (
        _created_on_behalf(context, custom_fields)
        and creator_id
        and affected_id
        and creator_id != affected_id
        and source == "creator_primary_agent"
    ):
        events.append(
            ObserverIntegrityEventInput(
                event_type="diagnostic_target_creator_fallback_on_behalf",
                severity="critical",
                source=SOURCE,
                dedupe_key=f"diagnostic_target_creator_fallback_on_behalf:{ticket.ticket_id}",
                ticket_id=ticket.ticket_id,
                device_id=target_device_id or ticket.device_id,
                actor_role="requester",
                expected="On-behalf web requester tickets must target the affected person's primary agent or record no/ambiguous affected target evidence.",
                actual="Ticket context marks an on-behalf ticket but diagnostic_target.source=creator_primary_agent.",
                evidence={
                    "creator_person_present": bool(creator_id),
                    "affected_person_present": bool(affected_id),
                    "diagnostic_target_source": source,
                    "target_device_id": target_device_id,
                    "flat_target_device_id": custom_fields.get("target_device_id"),
                    "created_on_behalf": True,
                },
                runbook="docs/runbooks/observer_web_cabinet.md",
                run_id=run_id,
            )
        )

    if _created_on_behalf(context, custom_fields) and creator_id and affected_id and creator_id != affected_id:
        invalid_attempts = _invalid_on_behalf_knowledge_attempts(custom_fields)
        if invalid_attempts:
            events.append(
                ObserverIntegrityEventInput(
                    event_type="knowledge_audience_leak_on_behalf",
                    severity="critical",
                    source=SOURCE,
                    dedupe_key=f"knowledge_audience_leak_on_behalf:{ticket.ticket_id}",
                    ticket_id=ticket.ticket_id,
                    device_id=target_device_id or ticket.device_id,
                    actor_role="requester",
                    expected="Requester-side Knowledge attempts on on-behalf web tickets must stay scoped to creator_visible/creator.",
                    actual="At least one requester-side Knowledge attempt carries an affected/support audience or non-creator visibility scope.",
                    evidence={
                        "creator_person_present": True,
                        "affected_person_present": True,
                        "created_on_behalf": True,
                        "invalid_attempt_count": len(invalid_attempts),
                        "invalid_attempts": invalid_attempts[:10],
                    },
                    runbook="docs/runbooks/observer_web_cabinet.md",
                    run_id=run_id,
                )
            )

    requested_target_device_id = _requested_target_device_id(custom_fields)
    flat_target_device_id = _clean(custom_fields.get("target_device_id"))
    if (
        requested_target_device_id
        and flat_target_device_id
        and target_device_id
        and requested_target_device_id == flat_target_device_id
        and flat_target_device_id != target_device_id
    ):
        events.append(
            ObserverIntegrityEventInput(
                event_type="forged_target_device_accepted",
                severity="critical",
                source=SOURCE,
                dedupe_key=f"forged_target_device_accepted:{ticket.ticket_id}",
                ticket_id=ticket.ticket_id,
                device_id=flat_target_device_id,
                actor_role="requester",
                expected="Browser/request-supplied target_device_id must not be accepted as the web ticket dispatch target when ticket_context has a different server-owned target.",
                actual="Flat target_device_id matches requester-supplied target but differs from ticket_context diagnostic target.",
                evidence={
                    "requested_target_device_id": requested_target_device_id,
                    "flat_target_device_id": flat_target_device_id,
                    "context_target_device_id": target_device_id,
                    "diagnostic_target_source": source,
                },
                runbook="docs/runbooks/observer_web_cabinet.md",
                run_id=run_id,
            )
        )
    history_event = await _customer_history_missing_event(
        session,
        ticket=ticket,
        device_id=target_device_id,
        run_id=run_id,
    )
    if history_event is not None:
        events.append(history_event)
    return events


async def check_web_cabinet(
    session: AsyncSession,
    *,
    registry_port: RegistryPort | None = None,
    run_id: str | None = None,
    limit: int = 300,
) -> ObserverIntegrityCheckResult:
    if registry_port is None:
        registry_port = DomainPortContainer.from_config(registry_session=session).registry
    query_limit = max(1, min(int(limit or 300), 1000))
    ticket_rows = (
        await session.execute(
            select(Ticket)
            .where(
                or_(
                    Ticket.requester_account_mode.in_(tuple(sorted(WEB_REQUESTER_ACCOUNT_MODES))),
                    Ticket.custom_fields["request_context"].astext.in_(tuple(sorted(WEB_REQUEST_CONTEXTS))),
                    Ticket.custom_fields["no_device"]["created_from"].astext == "requester_portal",
                    Ticket.custom_fields["requester_context_snapshot"].is_not(None),
                )
            )
            .order_by(Ticket.created_at.desc(), Ticket.ticket_id.desc())
            .limit(query_limit + 1)
        )
    ).scalars().all()
    rows, complete = limit_plus_one_window(ticket_rows, limit=query_limit)

    events: list[ObserverIntegrityEventInput] = []
    for ticket in rows:
        if not _is_web_requester_ticket(ticket):
            continue
        custom_fields = _custom_fields(ticket)
        context = _ticket_context(ticket)
        if not _has_ticket_context_v1(ticket):
            events.append(
                ObserverIntegrityEventInput(
                    event_type="web_ticket_missing_ticket_context_v1",
                    severity="critical",
                    source=SOURCE,
                    dedupe_key=f"web_ticket_missing_ticket_context_v1:{ticket.ticket_id}",
                    ticket_id=ticket.ticket_id,
                    device_id=ticket.device_id,
                    actor_role="requester",
                    expected="Every web-created requester ticket must store custom_fields.ticket_context.schema=ticket_context_v1.",
                    actual=f"ticket_context_schema={context.get('schema') if isinstance(context, dict) else None}",
                    evidence={
                        "requester_account_mode": ticket.requester_account_mode,
                        "request_context": custom_fields.get("request_context"),
                        "has_ticket_context": isinstance(context, dict),
                        "ticket_context_keys": sorted(context.keys()) if isinstance(context, dict) else [],
                    },
                    runbook="docs/runbooks/observer_web_cabinet.md",
                    run_id=run_id,
                )
            )
        else:
            events.extend(
                await _web_invariant_events(
                    session,
                    registry_port=registry_port,
                    ticket=ticket,
                    custom_fields=custom_fields,
                    context=context,
                    run_id=run_id,
                )
            )
        if not await _has_create_observer_trace(session, ticket.ticket_id):
            events.append(
                ObserverIntegrityEventInput(
                    event_type="missing_observer_event_for_web_ticket_create",
                    severity="medium",
                    source=SOURCE,
                    dedupe_key=f"missing_observer_event_for_web_ticket_create:{ticket.ticket_id}",
                    ticket_id=ticket.ticket_id,
                    device_id=ticket.device_id,
                    actor_role="requester",
                    expected="Web requester ticket creation must write a requester_web Observer trace with source=requester_ticket_create.",
                    actual="No requester_web requester_ticket_create trace found for ticket.",
                    evidence={
                        "requester_account_mode": ticket.requester_account_mode,
                        "request_context": custom_fields.get("request_context"),
                        "ticket_created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                    },
                    runbook="docs/runbooks/observer_web_cabinet.md",
                    run_id=run_id,
                )
            )
    return ObserverIntegrityCheckResult(
        source=SOURCE,
        events=events,
        complete=complete,
        scanned_count=len(ticket_rows),
        limit=query_limit,
    )
