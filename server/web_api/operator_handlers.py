"""Ticket-scoped HTTP reads and verified diagnostic device selection."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from aiohttp import web
from sqlalchemy import select

from access_control.service import can
from app.db import get_session
from app.db.models import Device, DeviceUserBinding, RegistryEndpointDeviceMapping, RegistryPerson, TicketAdminAudit
from app.repos.inventory_binding_authority import active_binding_condition
from app.repos.registration_repo import _active_person_condition
from app.services.endpoint_device_reference_service import EndpointDeviceReferenceService, EndpointDeviceSnapshotV1
from auth.context import AuthType
from auth.middleware import require_auth
from domain_ports.container import DomainPortContainer
from domain_ports.endpoint import EndpointDeviceProjection, EndpointDeviceRef, EndpointUnavailable
from tickets.handlers import _get_ticket_or_response, _push_ticket_event
from tickets.operator_feed import OPERATOR_FEED_EVENT_TYPES
from tickets.ticket_context import requester_reference_snapshot_from_record
from web_api.support_handlers import _build_timeline_entry, _read_support_json, _support_json_error


def _success(data: dict) -> web.Response:
    return web.json_response({"status": "success", "data": data}, headers={"Cache-Control": "no-store"})


def _requester_person_id(ticket) -> str | None:
    try:
        requester, _ = requester_reference_snapshot_from_record(ticket)
    except (TypeError, ValueError):
        return None
    return requester.external_id if requester else ticket.requester_person_id


async def _confirmed_devices(session, ticket, *, selected_id: str | None = None):
    person_id = _requester_person_id(ticket)
    if not person_id:
        return []
    stmt = (
        select(DeviceUserBinding, RegistryEndpointDeviceMapping, Device.hostname)
        .join(RegistryPerson, RegistryPerson.person_id == DeviceUserBinding.person_id)
        .join(RegistryEndpointDeviceMapping, RegistryEndpointDeviceMapping.device_id == DeviceUserBinding.device_id)
        .join(Device, Device.device_id == DeviceUserBinding.device_id)
        .where(
            DeviceUserBinding.person_id == person_id,
            active_binding_condition(),
            DeviceUserBinding.valid_to.is_(None),
            Device.deleted_at.is_(None),
            _active_person_condition(),
        )
        .order_by(DeviceUserBinding.device_id)
        .limit(100)
    )
    if selected_id is not None:
        stmt = stmt.where(DeviceUserBinding.device_id == selected_id).with_for_update(
            of=(DeviceUserBinding, RegistryEndpointDeviceMapping, RegistryPerson)
        )
    return (await session.execute(stmt)).all()


async def operator_ticket_detail(session, ticket, actor, payload) -> dict:
    actions = payload.actions
    scopes = actor.operator_scopes
    assigned = ticket.assignee_id == actor.actor_id
    can_reply = "tickets.reply" in scopes
    can_transition = "tickets.transition" in scopes and await can(session, actor, "ticket.status.change")
    transitions = {option.value: option for option in actions.status_options}
    public = assigned and actions.can_send_public_message and await can(session, actor, "ticket.comment.public")
    start = can_transition and ticket.assignee_id in (None, actor.actor_id) and actions.take_in_work and actions.take_in_work.allowed
    options = []
    if start and "in_progress" in transitions:
        options.append(transitions["in_progress"])
    if can_transition and public:
        options.extend(transitions[value] for value in ("waiting_on_user", "resolved") if value in transitions)
    actions = actions.model_copy(update={
        "status_options": options,
        "can_send_internal_note": can_reply and await can(session, actor, "ticket.comment.internal"),
        "can_send_public_message": can_reply and public,
        "can_resolve_and_close": can_transition and public and actions.can_resolve_and_close,
        "take_in_work": actions.take_in_work if start else None,
        "can_hide_from_workspace": False,
        "can_unhide_from_workspace": False,
        "can_archive_ticket": False,
        "can_unarchive_ticket": False,
        "approval": None,
    })
    devices = {
        binding.device_id: {"device_id": binding.device_id, "display_name": hostname}
        for binding, _mapping, hostname in await _confirmed_devices(session, ticket)
    }
    return {
        "ticket": payload.ticket.model_dump(mode="json", include={
            "ticket_id", "ticket_code", "title", "description", "status", "status_label",
            "assignee_id", "queue", "requester_display_name", "device_id", "updated_at",
        }),
        "actions": actions.model_dump(mode="json"),
        "timeline": [item.model_dump(mode="json") for item in payload.timeline],
        "requester_devices": list(devices.values()),
        "diagnostic_device_ref": EndpointDeviceReferenceService._validated_existing(ticket).device_ref,
        "can_select_diagnostic_device": (
            not ticket.endpoint_device_ref and assigned and bool(devices) and "diagnostics.run" in scopes
            and await can(session, actor, "ticket.tool.run")
        ),
    }


@require_auth("admin", "support")
async def handle_operator_ticket_events(request: web.Request) -> web.Response:
    try:
        after = int(request.query.get("after", "0"))
        limit = int(request.query.get("limit", "50"))
    except ValueError:
        return _support_json_error("Некорректный курсор или размер страницы", error_code="INVALID_EVENT_CURSOR")
    if not 0 <= after <= 2**63 - 1 or not 1 <= limit <= 100:
        return _support_json_error("Некорректный курсор или размер страницы", error_code="INVALID_EVENT_CURSOR")
    async with get_session() as session:
        ticket, error, repo, actor = await _get_ticket_or_response(request, session)
        if error is not None:
            return error
        if not await can(session, actor, "ticket.detail.view"):
            return _support_json_error("Доступ к заявке запрещён", status=403)
        events = await repo.get_events_since_id(ticket.ticket_id, after, limit + 1, event_types=OPERATOR_FEED_EVENT_TYPES)
        page = events[:limit]
        return _success({
            "ticket_id": ticket.ticket_id,
            "items": [_build_timeline_entry(event, ticket=ticket).model_dump(mode="json") for event in page],
            "next_cursor": page[-1].id if page else after,
            "has_more": len(events) > limit,
        })


@require_auth("admin", "support")
async def handle_operator_ticket_device(request: web.Request) -> web.Response:
    body = await _read_support_json(request)
    if isinstance(body, web.Response):
        return body
    try:
        if set(body) != {"device_id"}:
            raise ValueError
        device_id = str(UUID(body["device_id"]))
    except (ValueError, TypeError, AttributeError):
        return _support_json_error("Укажите UUID устройства из профиля заявителя", error_code="INVALID_DEVICE")

    async with get_session() as session:
        ticket, error, repo, actor = await _get_ticket_or_response(request, session)
        if error is not None:
            return error
        if await repo.get_ticket(ticket.ticket_id, for_update=True) is None:
            return _support_json_error("Обращение не найдено", status=404)
        ticket, error, _, actor = await _get_ticket_or_response(request, session, write=True)
        if error is not None:
            return error
        if ticket.assignee_id != actor.actor_id or not await can(session, actor, "ticket.tool.run"):
            return _support_json_error("Выбор устройства доступен исполнителю с правами диагностики", status=403)
        confirmed = await _confirmed_devices(session, ticket, selected_id=device_id)
        if not confirmed:
            return _support_json_error("Устройство не подтверждено в профиле заявителя", status=409, error_code="DEVICE_NOT_CONFIRMED")
        binding, mapping, _ = confirmed[0]
        ref = EndpointDeviceRef(external_id=mapping.endpoint_device_ref)
        existing = EndpointDeviceReferenceService._validated_existing(ticket)
        if existing.status == "resolved" and existing.device_ref == ref.external_id:
            return _success({"ticket_id": ticket.ticket_id, "device_id": device_id, "diagnostic_device_ref": ref.external_id})
        if ticket.endpoint_device_ref and ticket.endpoint_device_ref != ref.external_id:
            return _support_json_error("Цель диагностики уже выбрана", status=409, error_code="DIAGNOSTIC_DEVICE_ALREADY_SET")
        endpoint = DomainPortContainer.from_config().endpoint
        outcome = await endpoint.read_device(ref)
        if isinstance(outcome, EndpointUnavailable):
            return _support_json_error("Endpoint временно недоступен", status=503, error_code="ENDPOINT_UNAVAILABLE")
        if not isinstance(outcome, EndpointDeviceProjection) or outcome.device != ref or outcome.retired:
            return _support_json_error("Endpoint не подтвердил устройство", status=409, error_code="ENDPOINT_DEVICE_NOT_VERIFIED")

        ticket.endpoint_device_ref = ref.external_id
        ticket.endpoint_device_snapshot_json = EndpointDeviceSnapshotV1(
            device_ref=ref.external_id, display_name=outcome.display_name, retired=False,
            last_seen_at=outcome.last_seen_at, captured_at=datetime.now(timezone.utc),
        ).model_dump(mode="json")
        source = "helpdesk_operator" if actor.auth_type == AuthType.OPERATOR_TOKEN else "web_support_api"
        audit = {"device_id": device_id, "endpoint_device_ref": ref.external_id, "binding_id": binding.binding_id, "source": source}
        session.add(TicketAdminAudit(
            entity_type="ticket", entity_id=ticket.ticket_id, action="diagnostic_device_selected",
            actor_id=actor.actor_id, actor_role=actor.actor_role, after_json=audit,
        ))
        event = {**audit, "actor_id": actor.actor_id, "actor_role": actor.actor_role}
        result = await repo.add_event(
            ticket_id=ticket.ticket_id, device_id=device_id, agent_seq=None,
            event_type="diagnostic_device_selected", payload=event,
        )
        if result is None:
            await session.rollback()
            return _support_json_error("Не удалось сохранить цель диагностики", status=409)
        await session.commit()
    await _push_ticket_event(request, ticket.ticket_id, result, "diagnostic_device_selected", event)
    return _success({"ticket_id": ticket.ticket_id, "device_id": device_id, "diagnostic_device_ref": ref.external_id})
