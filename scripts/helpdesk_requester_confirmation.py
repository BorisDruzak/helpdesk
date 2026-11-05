"""Publish requester acceptance without closing tickets or changing special policies.

Transport owns staging host/release/backup guards. Plan is read-only; apply
rechecks its content fingerprint and uses the canonical audited policy registry.
"""
from copy import deepcopy

from sqlalchemy import select, text

from app.db.models import Ticket
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from scripts.helpdesk_phase1_catalog import CLOSURE_CODE, fingerprint, require_target
from tickets.closure_policy import requires_requester_confirmation
from tickets.helpdesk_policy_runtime import resolve_effective_ticket_policy
from tickets.handlers import _build_resolution_confirmation_request, _store_resolution_confirmation_state

CONFIRMATION_VERSION = "1.0.3"


def pending_expiry_update(ticket, confirmation_policy):
    fields = deepcopy(ticket.custom_fields or {})
    state = fields.get("resolution_confirmation") or {}
    stored = fields.get("resolution_confirmation_policy") or {}
    if (not state.get("pending") or stored.get("auto_close_after_days") in (None, "")
            or confirmation_policy.get("required") is not True
            or confirmation_policy.get("auto_close_after_days") is not None):
        return None
    fields["resolution_confirmation_policy"] = {**stored, **confirmation_policy}
    return fields


async def _uses_ordinary_policy(repo, ticket):
    template = (ticket.custom_fields or {}).get("request_template") or {}
    ref = (template.get("policy_refs") or {}).get("closure")
    code = ref.get("code") if isinstance(ref, dict) else ref
    if code:
        return code == CLOSURE_CODE
    effective = await repo.resolve_effective_policy(kind="closure",
        ticket_type=template.get("ticket_type") or ticket.ticket_type,
        category_id=template.get("category_id", ticket.category_id),
        template_code=next((template[key] for key in ("key", "template_code", "request_kind", "form_key") if template.get(key)), None))
    return any(source.get("code") == CLOSURE_CODE for source in effective.get("sources", []))


def build_confirmation_request(baseline):
    if baseline.get("code") != CLOSURE_CODE or baseline.get("version") != "1.0.2":
        raise ValueError("Expected the reviewed ordinary closure policy1.0.2")
    config = deepcopy(baseline.get("config") or {})
    confirmation = config.get("requester_confirmation") or {}
    if config.get("require_public_summary") is not True or confirmation.get("required") is not False:
        raise ValueError("Ordinary closure baseline changed; review required")
    config["requester_confirmation"] = {
        **confirmation, "required": True, "auto_close_after_days": None,
        "reopen_on_negative_feedback": True,
    }
    return {"kind": "closure", "code": CLOSURE_CODE, "requested_version": CONFIRMATION_VERSION,
        "title": baseline["title"], "description": baseline.get("description"),
        "scope_level": baseline.get("scope_level") or "system", "scope_ref": baseline.get("scope_ref"), "config": config}


async def publish_confirmation(session_factory, auth, *, apply=False, expected_fingerprint=None, isolated_test=False):
    if not auth.is_admin() or not auth.actor_id:
        raise ValueError("Explicit trusted administrator context required")
    async with session_factory() as session:
        async with session.begin():
            database = await session.scalar(text("SELECT current_database()"))
            require_target(database, isolated_test=isolated_test)
            if apply:
                await session.execute(text("LOCK TABLE closure_policies IN SHARE ROW EXCLUSIVE MODE"))
                # Exclude SELECT FOR UPDATE holders as well as writers, avoiding
                # a row-holder/table-writer lock inversion during acceptance.
                await session.execute(text("LOCK TABLE tickets IN EXCLUSIVE MODE"))
            repo = HelpdeskPolicyRepo(session)
            rows = [row for row in (await repo.list_policies("closure"))["closure"] if row["code"] == CLOSURE_CODE]
            rows.sort(key=lambda row: row["version"])
            resolved = list((await session.execute(select(Ticket).where(Ticket.status == "resolved").order_by(Ticket.ticket_id))).scalars())
            candidates = []
            pending_expiry = []
            for ticket in resolved:
                state = (ticket.custom_fields or {}).get("resolution_confirmation") or {}
                if state.get("pending"):
                    if await _uses_ordinary_policy(repo, ticket) and pending_expiry_update(ticket, {"required": True, "auto_close_after_days": None}):
                        pending_expiry.append(ticket)
                    continue
                if await requires_requester_confirmation(session, ticket):
                    continue
                if state.get("responded_option_id"):
                    raise ValueError("Resolved ticket has an existing requester decision; explicit review required")
                candidates.append(ticket)
            before = fingerprint({"policies": rows, "resolved": [{"id": t.ticket_id,
                "custom_fields": t.custom_fields, "result": t.requester_resolution_summary} for t in [*candidates, *pending_expiry]]})
            baseline = next((row for row in rows if row["version"] == "1.0.2"), None)
            if baseline is None:
                raise ValueError("Reviewed ordinary policy baseline is missing")
            request = build_confirmation_request(baseline)
            active = [row for row in rows if row["is_active"]]
            exact = next((row for row in rows if row["version"] == CONFIRMATION_VERSION), None)
            if len(active) != 1:
                raise ValueError("Expected exactly one active ordinary closure policy")
            if exact:
                if not exact["is_active"] or any(exact[key] != request[key] for key in ("config", "title", "description", "scope_level", "scope_ref")):
                    raise ValueError("Confirmation policy version conflicts with reviewed content")
            elif active[0]["version"] != "1.0.2" or any(row["version"] not in {"1.0.1", "1.0.2"} for row in rows):
                raise ValueError("Ordinary closure policy changed after review")
            plan = {"fingerprint": before, "request": request, "already_published": exact is not None,
                    "resolved_candidates": [t.ticket_id for t in candidates],
                    "pending_expiry_candidates": [t.ticket_id for t in pending_expiry]}
            if not apply:
                return {"status": "plan", **plan}
            if expected_fingerprint != before:
                raise ValueError("Policy state changed; obtain a fresh plan")
            if exact is None:
                await repo.publish_policy(**request, actor_id=auth.actor_id, actor_role=auth.actor_role)
            reconciled = []
            events = TicketEventsRepo(session)
            for ticket in candidates:
                if not await requires_requester_confirmation(session, ticket):
                    continue  # A special policy kept its original explicit opt-out.
                request_state = _build_resolution_confirmation_request()
                fields = {**(ticket.custom_fields or {}), "resolution_confirmation_policy": request["config"]["requester_confirmation"]}
                await events.update_ticket(ticket.ticket_id, custom_fields=fields)
                await _store_resolution_confirmation_state(events, ticket, pending=True, request_id=request_state["request_id"])
                await events.add_event(ticket_id=ticket.ticket_id, device_id=ticket.device_id, agent_seq=None,
                    event_type="closure_confirmation_requested", payload={"actor_id": auth.actor_id,
                        "actor_role": auth.actor_role, "source": "closure_policy_publication",
                        "policy_code": CLOSURE_CODE, "policy_version": CONFIRMATION_VERSION,
                        "request_id": request_state["request_id"]})
                reconciled.append(ticket.ticket_id)
            expiry_cleared = []
            for ticket in pending_expiry:
                effective = await resolve_effective_ticket_policy(session, ticket, "closure")
                fields = pending_expiry_update(ticket, effective.get("requester_confirmation") or {})
                if fields is None:
                    continue
                await events.update_ticket(ticket.ticket_id, custom_fields=fields)
                await events.add_event(ticket_id=ticket.ticket_id, device_id=ticket.device_id, agent_seq=None,
                    event_type="closure_confirmation_expiry_disabled", payload={"actor_id": auth.actor_id,
                        "actor_role": auth.actor_role, "source": "closure_policy_publication",
                        "policy_code": CLOSURE_CODE, "policy_version": CONFIRMATION_VERSION})
                expiry_cleared.append(ticket.ticket_id)
            return {"status": "applied", **plan, "changed": exact is None,
                    "reconciled_tickets": reconciled, "expiry_cleared_tickets": expiry_cleared}
