"""Trusted scenario bindings resolve through the existing Helpdesk registry."""
from copy import deepcopy
from datetime import date, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re

from sqlalchemy import select

from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from web_api.dto.request_scenario import ProcessBinding

FACT_VALUES = {"impact": ("single_user", "multiple_users", "department"),
               "urgency": ("can_work", "degraded", "blocked"), "importance": ("normal", "important", "critical")}
POLICY_VALUES = {"impact": {"single_user": "single_user", "multiple_users": "several_people", "department": "department"},
                 "urgency": {"can_work": "workaround_available", "degraded": "strongly_degraded", "blocked": "work_stopped_no_workaround"},
                 "importance": {"normal": "normal", "important": "high", "critical": "critical"}}


class ScenarioProcessingUnavailable(ValueError):
    """A trusted published target became unavailable; answers cannot repair it."""


def validated_scenario_calendar(calendar):
    """Reject malformed schedules instead of the calendar engine's 24x7 fallback."""
    def value(key, default=None):
        return calendar.get(key, default) if isinstance(calendar, dict) else getattr(calendar, key, default)
    try:
        if not value("is_active", False):
            raise ValueError("inactive")
        timezone = value("timezone")
        ZoneInfo(timezone)
        weekly, holidays = value("weekly_hours_json"), value("holidays_json", []) or []
        if not isinstance(weekly, list) or not weekly or not isinstance(holidays, list):
            raise ValueError("empty schedule")
        for slot in weekly:
            if not isinstance(slot, dict) or type(slot.get("day")) is not int or not 0 <= slot["day"] <= 6:
                raise ValueError("invalid day")
            if not all(isinstance(slot.get(key), str) and re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", slot[key]) for key in ("start", "end")):
                raise ValueError("invalid time format")
            start, end = time.fromisoformat(slot["start"]), time.fromisoformat(slot["end"])
            if start.tzinfo or end.tzinfo or start.second or end.second or start >= end:
                raise ValueError("invalid interval")
        for item in holidays:
            if not isinstance(item, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item):
                raise ValueError("invalid holiday format")
            date.fromisoformat(item)
        weekly = sorted(weekly, key=lambda slot: (slot["day"], slot["start"], slot["end"]))
        if any(left["day"] == right["day"] and left["end"] > right["start"] for left, right in zip(weekly, weekly[1:])):
            raise ValueError("overlapping intervals")
    except (ValueError, TypeError, KeyError, ZoneInfoNotFoundError) as exc:
        raise ValueError({"processing.calendar": "Рабочий календарь недоступен или содержит некорректное расписание."}) from exc
    return {"timezone": timezone, "weekly_hours_json": deepcopy(weekly), "holidays_json": deepcopy(holidays)}


def validate_map_processing_references(definition, queues, calendars):
    """Validate every named target, including assignments not reached by a sample."""
    if definition.schema_version != 3 or definition.processing is None:
        return []
    active = {item["code"] for item in queues if item.get("is_active") is True}
    by_id = {item["id"]: item for item in calendars}
    issues = []
    for key, route in definition.processing.routes.items():
        if route.queue_code not in active:
            issues.append({"code": "processing_queue_unavailable", "path": f"processing.routes.{key}.queue_code",
                "message": "Направление ссылается на отсутствующую или отключённую очередь."})
    for key, profile in definition.processing.sla_profiles.items():
        if profile.calendar_id is None and profile.time_basis != "business":
            continue
        try:
            validated_scenario_calendar(by_id.get(profile.calendar_id))
        except ValueError:
            issues.append({"code": "processing_calendar_invalid", "path": f"processing.sla_profiles.{key}.calendar_id",
                "message": "Выберите действующий рабочий календарь с корректным расписанием."})
    return issues


async def apply_scenario_map_processing(session, validated, selection):
    """Internal adapter: selection comes only from a server-built route snapshot."""
    if selection is None:
        return validated
    from app.db.models import TicketQueue, TicketBusinessCalendar
    from web_api.dto.request_scenario import ScenarioRoute, ScenarioSlaProfile
    route = ScenarioRoute.model_validate({key: value for key, value in selection["route"].items() if key not in {"key", "source"}})
    profile = ScenarioSlaProfile.model_validate({key: value for key, value in selection["sla_profile"].items() if key not in {"key", "source"}})
    if profile.first_response_minutes < 1 or profile.resolution_minutes < 1:
        raise ValueError({"processing.sla_profile": "Укажите положительные сроки обработки."})
    queue = await session.scalar(select(TicketQueue).where(TicketQueue.code == route.queue_code).execution_options(populate_existing=True))
    if queue is None or not queue.is_active:
        raise ScenarioProcessingUnavailable({"processing.route": "Выбранная очередь отключена или недоступна."})
    calendar = None
    if profile.calendar_id is not None:
        current = await session.get(TicketBusinessCalendar, profile.calendar_id, populate_existing=True)
        try:
            calendar = validated_scenario_calendar(current)
        except ValueError as exc:
            raise ScenarioProcessingUnavailable(*exc.args) from exc
    elif profile.time_basis == "business":
        raise ValueError({"processing.sla_profile": "Для рабочих сроков необходим рабочий календарь."})
    result = deepcopy(validated)
    context = result.setdefault("template_context", {})
    context["routing_policy"] = {"fallback": {"queue_id": queue.id, "queue_code": queue.code}}
    context["sla_policy"] = {"code": selection["sla_profile"]["key"], "source": "request_scenario.processing",
        "targets": {"first_response": {priority: profile.first_response_minutes for priority in ("P0", "P1", "P2", "P3", "P4")},
                    "resolution": {priority: profile.resolution_minutes for priority in ("P0", "P1", "P2", "P3", "P4")}}}
    if profile.time_basis == "business":
        context["sla_policy"]["calendar"] = (validated_scenario_calendar({"is_active": True, **selection["calendar_snapshot"]})
            if "calendar_snapshot" in selection else calendar)
    context.pop("sla_policy_id", None)
    for kind in ("routing", "sla"):
        context.pop(kind + "_policy_code", None)
        for field in ("policy_refs", "effective_policy_sources", "effective_policy_snapshots"):
            if isinstance(context.get(field), dict):
                context[field].pop(kind, None)
    context["scenario_processing"] = deepcopy(selection)
    if "approval_required" in selection:
        context.setdefault("approval_policy", {})["required"] = selection["approval_required"]
    return result


def apply_scenario_processing_facts(validated, facts):
    """Adapt trusted typed facts to existing policy inputs; never set a priority."""
    from web_api.dto.request_scenario import ProcessingFacts
    facts = ProcessingFacts.model_validate(facts or {}).model_dump(exclude_none=True)
    result = deepcopy(validated)
    policy = result.get("template_context", {}).get("priority_policy") or {}
    inputs = policy.get("input_fields") or {}
    for kind, value in facts.items():
        key = policy.get(kind + "_field") or inputs.get(kind + "_field")
        if not isinstance(key, str) or not key:
            raise ValueError({"processing_facts." + kind: "Действующая политика не принимает это значение"})
        result.setdefault("submitted_values", {})[key] = POLICY_VALUES[kind][value]
    return result


async def apply_scenario_policy_refs(session, validated, references):
    if not references:
        return validated
    # Defensive validation for historical stored definitions; callers supply
    # references only from server-loaded scenario snapshots, never request JSON.
    refs = ProcessBinding(request_template_key="scenario", policy_refs=references).policy_refs
    result = deepcopy(validated)
    context = result.setdefault("template_context", {})
    repo = HelpdeskPolicyRepo(session)
    for kind, code in refs.items():
        effective = await repo.resolve_policy_ref(kind=kind, code=code, source=f"request_scenario.policy_refs.{kind}")
        policy = effective.get("policy") or {}
        config = effective.get("config")
        if not policy.get("is_active") or not policy.get("published_at") or not isinstance(config, dict) or not config:
            raise ValueError({"policy_refs." + kind: "Selected processing policy is not published or available"})
        context[kind + "_policy"] = deepcopy(config)
        context[kind + "_policy_code"] = code
        context.setdefault("policy_refs", {})[kind] = {"code": code, "version": policy["version"]}
        context.setdefault("effective_policy_sources", {})[kind] = deepcopy(effective.get("sources") or [])
        context.setdefault("effective_policy_snapshots", {})[kind] = deepcopy(policy)
        if kind == "sla":
            # Canonical registry overlay uses the same bridge for legacy SLA rows.
            from app.db.models import TicketSlaPolicy
            from tickets.helpdesk_policy_runtime import _as_int
            identifier = _as_int(config.get("sla_policy_id") or config.get("legacy_sla_policy_id"))
            if identifier is not None:
                legacy = await session.get(TicketSlaPolicy, identifier)
                if legacy is None or not legacy.is_active:
                    raise ValueError({"policy_refs.sla": "Selected SLA references an unavailable legacy policy"})
                context["sla_policy_id"] = identifier
            else:
                context.pop("sla_policy_id", None)
    return result
