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
class WorkflowTransitionGate:
    to_status: str
    allowed_roles: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    required_comment: str | None = None
    require_approval: bool = False
    require_evidence: bool = False
    notify: tuple[str, ...] = ()
    sla_action: str | None = None

    def to_dict(self) -> dict:
        payload: dict[str, Any] = {"to": self.to_status}
        if self.allowed_roles:
            payload["allowed_roles"] = list(self.allowed_roles)
        if self.required_fields:
            payload["required_fields"] = list(self.required_fields)
        if self.required_comment:
            payload["required_comment"] = self.required_comment
        if self.require_approval:
            payload["require_approval"] = True
        if self.require_evidence:
            payload["require_evidence"] = True
        actions: dict[str, Any] = {}
        if self.notify:
            actions["notify"] = list(self.notify)
        if self.sla_action:
            actions["sla"] = self.sla_action
        if actions:
            payload["actions"] = actions
        return payload


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
    transition_gates: dict[str, dict[str, WorkflowTransitionGate]] | None = None

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
        gates = self.transition_gates or {}
        if gates:
            payload["transition_gates"] = {
                str(from_status): {
                    str(to_status): gate.to_dict() if isinstance(gate, WorkflowTransitionGate) else gate
                    for to_status, gate in by_target.items()
                }
                for from_status, by_target in gates.items()
                if by_target
            }
        else:
            payload["transition_gates"] = {}
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


def _normalize_comment_requirement(value: Any, *, field_name: str) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    aliases = {
        "public_comment": "public",
        "internal_comment": "internal",
        "comment": "any",
        "required": "any",
        "true": "any",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"public", "internal", "any"}:
        raise ValueError(f"{field_name} must be public, internal or any")
    return normalized


def _normalize_sla_action(value: Any, *, field_name: str) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized not in {"pause", "resume", "stop"}:
        raise ValueError(f"{field_name} must be pause, resume or stop")
    return normalized


def _normalize_transition_gate(raw_gate: Any, *, to_status: str, field_name: str) -> WorkflowTransitionGate:
    if raw_gate is None or isinstance(raw_gate, str):
        return WorkflowTransitionGate(to_status=to_status)
    if not isinstance(raw_gate, dict):
        raise ValueError(f"{field_name} must be an object")
    actions = raw_gate.get("actions") if isinstance(raw_gate.get("actions"), dict) else {}
    return WorkflowTransitionGate(
        to_status=to_status,
        allowed_roles=_normalize_string_list(
            raw_gate.get("allowed_roles") or raw_gate.get("roles"),
            field_name=f"{field_name}.allowed_roles",
        ),
        required_fields=_normalize_string_list(
            raw_gate.get("required_fields"),
            field_name=f"{field_name}.required_fields",
        ),
        required_comment=_normalize_comment_requirement(
            raw_gate.get("required_comment")
            or raw_gate.get("comment_required")
            or raw_gate.get("comment_visibility"),
            field_name=f"{field_name}.required_comment",
        ),
        require_approval=bool(raw_gate.get("require_approval") or raw_gate.get("approval_required")),
        require_evidence=bool(raw_gate.get("require_evidence") or raw_gate.get("evidence_required")),
        notify=_normalize_string_list(
            actions.get("notify") or raw_gate.get("notify"),
            field_name=f"{field_name}.actions.notify",
        ),
        sla_action=_normalize_sla_action(
            actions.get("sla") or raw_gate.get("sla_action"),
            field_name=f"{field_name}.actions.sla",
        ),
    )


def _normalize_transitions(
    value: Any,
    *,
    allowed_statuses: tuple[str, ...],
) -> tuple[dict[str, tuple[str, ...]], dict[str, dict[str, WorkflowTransitionGate]]]:
    if value is None:
        return dict(DEFAULT_SUPPORT_TRANSITIONS), {}
    if not isinstance(value, dict):
        raise ValueError("transitions must be an object")
    allowed = set(allowed_statuses) | {"triaged"}
    normalized: dict[str, tuple[str, ...]] = {}
    gates: dict[str, dict[str, WorkflowTransitionGate]] = {}
    for raw_from, raw_targets in value.items():
        from_status = str(raw_from or "").strip()
        if from_status not in allowed:
            raise ValueError(f"transitions contains unknown source status {from_status!r}")
        targets_list: list[str] = []
        target_gates: dict[str, WorkflowTransitionGate] = {}
        if isinstance(raw_targets, dict):
            iterable_targets = [
                {"to": raw_to, **(raw_gate or {})} if isinstance(raw_gate, dict) else {"to": raw_to}
                for raw_to, raw_gate in raw_targets.items()
            ]
        elif isinstance(raw_targets, list | tuple):
            iterable_targets = list(raw_targets)
        else:
            raise ValueError(f"transitions.{from_status} must be a list or object")

        for index, raw_target in enumerate(iterable_targets):
            if isinstance(raw_target, dict):
                target = str(
                    raw_target.get("to")
                    or raw_target.get("to_status")
                    or raw_target.get("target")
                    or ""
                ).strip()
                if not target:
                    raise ValueError(f"transitions.{from_status}[{index}].to is required")
                if target not in ALLOWED_WORKFLOW_STATUSES:
                    raise ValueError(f"transitions.{from_status} contains unknown status {target!r}")
                gate = _normalize_transition_gate(
                    raw_target,
                    to_status=target,
                    field_name=f"transitions.{from_status}.{target}",
                )
                if gate.to_dict() != {"to": gate.to_status}:
                    target_gates[target] = gate
            else:
                target = str(raw_target or "").strip()
                if not target:
                    continue
                if target not in ALLOWED_WORKFLOW_STATUSES:
                    raise ValueError(f"transitions.{from_status} contains unknown status {target!r}")
            if target not in targets_list:
                targets_list.append(target)
        targets = tuple(targets_list)
        invalid_targets = [target for target in targets if target not in allowed]
        if invalid_targets:
            raise ValueError(
                f"transitions.{from_status} contains statuses outside allowed_statuses: "
                + ", ".join(invalid_targets)
            )
        normalized[from_status] = targets
        if target_gates:
            gates[from_status] = target_gates
    return normalized, gates


def _normalize_transition_gates(
    value: Any,
    *,
    transitions: dict[str, tuple[str, ...]],
    allowed_statuses: tuple[str, ...],
) -> dict[str, dict[str, WorkflowTransitionGate]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("transition_gates must be an object")
    allowed = set(allowed_statuses) | {"triaged"}
    gates: dict[str, dict[str, WorkflowTransitionGate]] = {}
    for raw_from, raw_targets in value.items():
        from_status = str(raw_from or "").strip()
        if from_status not in allowed:
            raise ValueError(f"transition_gates contains unknown source status {from_status!r}")
        if not isinstance(raw_targets, dict):
            raise ValueError(f"transition_gates.{from_status} must be an object")
        for raw_to, raw_gate in raw_targets.items():
            to_status = str(raw_to or "").strip()
            if to_status not in allowed:
                raise ValueError(f"transition_gates.{from_status} contains unknown status {to_status!r}")
            if to_status not in transitions.get(from_status, ()):
                raise ValueError(
                    f"transition_gates.{from_status}.{to_status} is not present in transitions"
                )
            gate = _normalize_transition_gate(
                raw_gate,
                to_status=to_status,
                field_name=f"transition_gates.{from_status}.{to_status}",
            )
            if gate.to_dict() != {"to": gate.to_status}:
                gates.setdefault(from_status, {})[to_status] = gate
    return gates


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
    transitions, transition_gates = _normalize_transitions(
        raw_profile.get("transitions"),
        allowed_statuses=allowed_statuses,
    )
    explicit_transition_gates = _normalize_transition_gates(
        raw_profile.get("transition_gates"),
        transitions=transitions,
        allowed_statuses=allowed_statuses,
    )
    for from_status, by_target in explicit_transition_gates.items():
        transition_gates.setdefault(from_status, {}).update(by_target)
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
        transitions=transitions,
        transition_gates=transition_gates,
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
