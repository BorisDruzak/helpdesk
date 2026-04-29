"""Workflow profile registry keyed by ticket_type.

The first implementation is code-defined on purpose: it makes ticket_type a real
process selector while keeping the future DB-backed editor shape serializable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


DEFAULT_WORKFLOW_PROFILE = "service_request"


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

    def to_dict(self) -> dict:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, tuple):
                payload[key] = list(value)
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
    ),
    WorkflowProfile(
        ticket_type="service_request",
        label="Запрос услуги",
        purpose="fulfill_standard_service",
        suggested_path=("new", "queued", "assigned", "in_progress", "resolved", "closed"),
        allowed_statuses=COMMON_ACTIVE_STATUSES,
        required_create_fields=("requested_service",),
        required_resolve_fields=("resolution_code", "public_summary"),
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
    ),
    WorkflowProfile(
        ticket_type="consultation",
        label="Консультация",
        purpose="answer_or_instruction",
        suggested_path=("new", "queued", "in_progress", "resolved", "closed"),
        allowed_statuses=COMMON_ACTIVE_STATUSES,
        required_create_fields=("question",),
        required_resolve_fields=("public_summary",),
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
