"""Workflow profile registry keyed by ticket_type."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServerConfig
from tickets.statuses import CANONICAL_STATUSES


DEFAULT_WORKFLOW_PROFILE = "service_request"
WORKFLOW_PROFILES_CONFIG_KEY = "ticket.workflow_profiles"

DEFAULT_SUPPORT_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "new": ("queued", "assigned", "in_progress", "canceled"),
    "triaged": (
        "assigned",
        "in_progress",
        "waiting_on_user",
        "waiting_on_internal_team",
        "waiting_on_vendor",
        "waiting_on_approval",
        "scheduled",
        "resolved",
        "canceled",
    ),
    "queued": (
        "assigned",
        "in_progress",
        "waiting_on_user",
        "waiting_on_internal_team",
        "waiting_on_vendor",
        "waiting_on_approval",
        "scheduled",
        "canceled",
    ),
    "assigned": (
        "queued",
        "in_progress",
        "waiting_on_user",
        "waiting_on_internal_team",
        "waiting_on_vendor",
        "waiting_on_approval",
        "scheduled",
        "canceled",
    ),
    "in_progress": (
        "queued",
        "assigned",
        "waiting_on_user",
        "waiting_on_internal_team",
        "waiting_on_vendor",
        "waiting_on_approval",
        "scheduled",
        "resolved",
        "canceled",
    ),
    "waiting_on_user": ("queued", "assigned", "in_progress", "resolved", "canceled"),
    "waiting_on_internal_team": ("queued", "assigned", "in_progress", "resolved", "canceled"),
    "waiting_on_vendor": ("queued", "assigned", "in_progress", "resolved", "canceled"),
    "waiting_on_approval": ("queued", "assigned", "in_progress", "resolved", "canceled"),
    "scheduled": ("assigned", "in_progress", "canceled"),
    "resolved": ("new", "in_progress", "closed"),
    "closed": ("new",),
    "canceled": ("new",),
}

DEFAULT_REQUESTER_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "resolved": ("in_progress", "closed"),
}

ALLOWED_WORKFLOW_STATUSES = set(CANONICAL_STATUSES) | {"triaged"}


@dataclass(frozen=True)
class WorkflowProfile:
    ticket_type: str
    label: str
    purpose: str
    suggested_path: tuple[str, ...]
    allowed_statuses: tuple[str, ...]
    required_create_fields: tuple[str, ...] = ()
    required_resolve_fields: tuple[str, ...] = ()
    requires_approval: bool = False
    requires_change_plan: bool = False
    requires_action_log: bool = False
    evidence_required_for_priorities: tuple[str, ...] = ()
    transitions: dict[str, tuple[str, ...]] | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, tuple):
                payload[key] = list(value)
            if isinstance(value, dict):
                payload[key] = {
                    str(inner_key): list(inner_value) if isinstance(inner_value, tuple) else inner_value
                    for inner_key, inner_value in value.items()
                }
        return payload


COMMON_ACTIVE_STATUSES = (
    "new",
    "queued",
    "assigned",
    "in_progress",
    "waiting_on_user",
    "waiting_on_internal_team",
    "waiting_on_vendor",
    "waiting_on_approval",
    "scheduled",
    "resolved",
    "closed",
    "canceled",
)


_PROFILES: tuple[WorkflowProfile, ...] = (
    WorkflowProfile(
        ticket_type="incident",
        label="Инцидент",
        purpose="restore_service",
        suggested_path=("new", "queued", "in_progress", "resolved", "closed"),
        allowed_statuses=COMMON_ACTIVE_STATUSES,
        required_create_fields=("affected_object", "impact", "urgency"),
        required_resolve_fields=("resolution_code", "public_summary"),
        evidence_required_for_priorities=("P0", "P1"),
        transitions=DEFAULT_SUPPORT_TRANSITIONS,
    ),
    WorkflowProfile(
        ticket_type="service_request",
        label="Запрос услуги",
        purpose="fulfill_standard_service",
        suggested_path=("new", "queued", "assigned", "in_progress", "resolved", "closed"),
        allowed_statuses=COMMON_ACTIVE_STATUSES,
        required_create_fields=("requested_service",),
        required_resolve_fields=("resolution_code", "public_summary"),
        transitions=DEFAULT_SUPPORT_TRANSITIONS,
    ),
    WorkflowProfile(
        ticket_type="access_request",
        label="Запрос доступа",
        purpose="approve_and_grant_access",
        suggested_path=("new", "waiting_on_approval", "assigned", "in_progress", "resolved", "closed"),
        allowed_statuses=COMMON_ACTIVE_STATUSES,
        required_create_fields=("system", "role", "justification", "approver"),
        required_resolve_fields=("approval_evidence", "action_log", "resolution_code", "public_summary"),
        requires_approval=True,
        requires_action_log=True,
        transitions={
            **DEFAULT_SUPPORT_TRANSITIONS,
            "new": ("waiting_on_approval", "queued", "canceled"),
            "waiting_on_approval": ("assigned", "in_progress", "canceled"),
        },
    ),
    WorkflowProfile(
        ticket_type="change_request",
        label="Запрос изменения",
        purpose="plan_approve_schedule_execute",
        suggested_path=("new", "waiting_on_approval", "scheduled", "in_progress", "resolved", "closed"),
        allowed_statuses=COMMON_ACTIVE_STATUSES,
        required_create_fields=("change_plan", "work_window", "risk", "rollback_plan", "approver"),
        required_resolve_fields=("approval_evidence", "change_result", "rollback_status", "public_summary"),
        requires_approval=True,
        requires_change_plan=True,
        transitions={
            **DEFAULT_SUPPORT_TRANSITIONS,
            "new": ("waiting_on_approval", "canceled"),
            "waiting_on_approval": ("scheduled", "assigned", "canceled"),
            "scheduled": ("in_progress", "canceled"),
            "in_progress": ("waiting_on_user", "waiting_on_internal_team", "resolved", "canceled"),
        },
    ),
    WorkflowProfile(
        ticket_type="consultation",
        label="Консультация",
        purpose="answer_or_instruction",
        suggested_path=("new", "queued", "in_progress", "resolved", "closed"),
        allowed_statuses=COMMON_ACTIVE_STATUSES,
        required_create_fields=("question",),
        required_resolve_fields=("public_summary",),
        transitions=DEFAULT_SUPPORT_TRANSITIONS,
    ),
)

_PROFILE_BY_TYPE = {profile.ticket_type: profile for profile in _PROFILES}


def list_workflow_profiles() -> tuple[WorkflowProfile, ...]:
    return _PROFILES


def get_workflow_profile(ticket_type: str | None) -> WorkflowProfile:
    normalized = str(ticket_type or "").strip()
    return _PROFILE_BY_TYPE.get(normalized) or _PROFILE_BY_TYPE[DEFAULT_WORKFLOW_PROFILE]


def serialize_workflow_profiles(profiles: Iterable[WorkflowProfile] | None = None) -> list[dict]:
    return [profile.to_dict() for profile in (profiles or _PROFILES)]


def _normalize_string_list(value: Any, *, field_name: str, allow_statuses: bool = False) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list | tuple):
        raise ValueError(f"{field_name} must be a list")
    normalized: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        if allow_statuses and text not in ALLOWED_WORKFLOW_STATUSES:
            raise ValueError(f"{field_name} contains unknown status {text!r}")
        if text not in normalized:
            normalized.append(text)
    return tuple(normalized)


def _normalize_transitions(value: Any, *, allowed_statuses: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    if value is None:
        return dict(DEFAULT_SUPPORT_TRANSITIONS)
    if not isinstance(value, dict):
        raise ValueError("transitions must be an object")
    allowed = set(allowed_statuses) | {"triaged"}
    normalized: dict[str, tuple[str, ...]] = {}
    for raw_from, raw_targets in value.items():
        from_status = str(raw_from or "").strip()
        if from_status not in allowed:
            raise ValueError(f"transitions contains unknown source status {from_status!r}")
        targets = _normalize_string_list(
            raw_targets,
            field_name=f"transitions.{from_status}",
            allow_statuses=True,
        )
        invalid_targets = [target for target in targets if target not in allowed]
        if invalid_targets:
            raise ValueError(
                f"transitions.{from_status} contains statuses outside allowed_statuses: "
                + ", ".join(invalid_targets)
            )
        normalized[from_status] = targets
    return normalized


def normalize_workflow_profile(raw_profile: Any) -> WorkflowProfile:
    if not isinstance(raw_profile, dict):
        raise ValueError("workflow profile must be an object")
    ticket_type = str(raw_profile.get("ticket_type") or "").strip()
    if not ticket_type:
        raise ValueError("ticket_type is required")
    label = str(raw_profile.get("label") or ticket_type).strip() or ticket_type
    purpose = str(raw_profile.get("purpose") or ticket_type).strip() or ticket_type
    allowed_statuses = _normalize_string_list(
        raw_profile.get("allowed_statuses") or list(CANONICAL_STATUSES),
        field_name=f"{ticket_type}.allowed_statuses",
        allow_statuses=True,
    )
    if "new" not in allowed_statuses:
        allowed_statuses = ("new", *allowed_statuses)
    suggested_path = _normalize_string_list(
        raw_profile.get("suggested_path") or ["new", "queued", "in_progress", "resolved", "closed"],
        field_name=f"{ticket_type}.suggested_path",
        allow_statuses=True,
    )
    for status in suggested_path:
        if status not in allowed_statuses:
            raise ValueError(f"{ticket_type}.suggested_path contains status outside allowed_statuses: {status}")
    return WorkflowProfile(
        ticket_type=ticket_type,
        label=label,
        purpose=purpose,
        suggested_path=suggested_path,
        allowed_statuses=allowed_statuses,
        required_create_fields=_normalize_string_list(
            raw_profile.get("required_create_fields"),
            field_name=f"{ticket_type}.required_create_fields",
        ),
        required_resolve_fields=_normalize_string_list(
            raw_profile.get("required_resolve_fields"),
            field_name=f"{ticket_type}.required_resolve_fields",
        ),
        requires_approval=bool(raw_profile.get("requires_approval")),
        requires_change_plan=bool(raw_profile.get("requires_change_plan")),
        requires_action_log=bool(raw_profile.get("requires_action_log")),
        evidence_required_for_priorities=_normalize_string_list(
            raw_profile.get("evidence_required_for_priorities"),
            field_name=f"{ticket_type}.evidence_required_for_priorities",
        ),
        transitions=_normalize_transitions(raw_profile.get("transitions"), allowed_statuses=allowed_statuses),
    )


def normalize_workflow_profiles_payload(raw_payload: Any) -> tuple[WorkflowProfile, ...]:
    source = raw_payload
    if isinstance(raw_payload, dict):
        source = raw_payload.get("workflow_profiles") or raw_payload.get("profiles")
    if source is None:
        return _PROFILES
    if not isinstance(source, list):
        raise ValueError("workflow_profiles must be a list")
    profiles: list[WorkflowProfile] = []
    seen: set[str] = set()
    for raw_profile in source:
        profile = normalize_workflow_profile(raw_profile)
        if profile.ticket_type in seen:
            raise ValueError(f"duplicate ticket_type {profile.ticket_type!r}")
        seen.add(profile.ticket_type)
        profiles.append(profile)
    if DEFAULT_WORKFLOW_PROFILE not in seen:
        profiles.append(_PROFILE_BY_TYPE[DEFAULT_WORKFLOW_PROFILE])
    return tuple(profiles)


async def load_workflow_profiles(session: AsyncSession) -> tuple[WorkflowProfile, ...]:
    result = await session.execute(
        select(ServerConfig.value).where(ServerConfig.key == WORKFLOW_PROFILES_CONFIG_KEY)
    )
    raw_value = result.scalar_one_or_none()
    if not raw_value:
        return _PROFILES
    try:
        payload = json.loads(raw_value)
        return normalize_workflow_profiles_payload(payload)
    except Exception:
        return _PROFILES


async def save_workflow_profiles(session: AsyncSession, raw_payload: Any) -> tuple[WorkflowProfile, ...]:
    profiles = normalize_workflow_profiles_payload(raw_payload)
    value = json.dumps({"workflow_profiles": serialize_workflow_profiles(profiles)}, ensure_ascii=False)
    stmt = (
        insert(ServerConfig)
        .values(key=WORKFLOW_PROFILES_CONFIG_KEY, value=value)
        .on_conflict_do_update(
            index_elements=[ServerConfig.key],
            set_={"value": value},
        )
    )
    await session.execute(stmt)
    await session.flush()
    return profiles


def workflow_profile_by_type(
    profiles: Iterable[WorkflowProfile],
    ticket_type: str | None,
) -> WorkflowProfile:
    normalized = str(ticket_type or "").strip()
    profile_map = {profile.ticket_type: profile for profile in profiles}
    return profile_map.get(normalized) or profile_map.get(DEFAULT_WORKFLOW_PROFILE) or get_workflow_profile(normalized)
