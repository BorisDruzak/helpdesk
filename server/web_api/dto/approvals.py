from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ApprovalConsentAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    href: str | None = None
    method: str | None = None
    endpoint: str | None = None
    enabled: bool = True
    disabled_reason: str | None = None
    requires_comment: bool = False
    risk_warning: str | None = None


class ApprovalConsentBlocking(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocks_ticket_progress: bool = False
    blocks_sla: bool = False
    blocks_operation: bool = False
    blocks_closure: bool = False
    blocks_change: bool = False


class ApprovalConsentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue: str | None = None
    assignee: str | None = None
    service_code: str | None = None
    offering_code: str | None = None
    device_hostname: str | None = None
    tool_name: str | None = None
    change_window: str | None = None
    closure_blocker: str | None = None
    policy_code: str | None = None


class ApprovalConsentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    status: str
    title: str
    reason: str
    object_type: str
    object_id: str
    ticket_id: str | None = None
    ticket_number: str | None = None
    change_id: str | None = None
    change_number: str | None = None
    operation_id: str | None = None
    device_id: str | None = None
    requester_name: str | None = None
    requested_by: str | None = None
    approver: str | None = None
    approver_group: str | None = None
    risk: str = "unknown"
    due_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    blocking: ApprovalConsentBlocking = Field(default_factory=ApprovalConsentBlocking)
    context: ApprovalConsentContext = Field(default_factory=ApprovalConsentContext)
    actions: list[ApprovalConsentAction] = Field(default_factory=list)


class ApprovalConsentSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    description: str
    count: int
    severity: str
    href: str | None = None


class ApprovalConsentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    pending_count: int
    overdue_count: int
    high_risk_count: int
    waiting_user_count: int
    waiting_approver_count: int
    blocking_sla_count: int
    ticket_approvals_count: int
    change_approvals_count: int
    risky_tool_consents_count: int
    closure_approvals_count: int
    policy_overrides_count: int


class ApprovalConsentFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str | None = None
    status: str | None = None
    risk: str | None = None
    object_type: str | None = None
    queue: str | None = None
    assignee: str | None = None
    due_window_hours: int | None = None
    limit: int
    offset: int


class ApprovalConsentCenterPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str
    scope: str
    filters: ApprovalConsentFilters
    summary: ApprovalConsentSummary
    sections: list[ApprovalConsentSection] = Field(default_factory=list)
    items: list[ApprovalConsentItem] = Field(default_factory=list)
