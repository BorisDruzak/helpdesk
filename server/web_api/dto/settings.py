from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WebSettingsCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_write: bool
    actor_role: str
    can_manage_queues: bool = False
    can_manage_routing: bool = False
    manage_queues_denial_reason: str | None = None
    manage_routing_denial_reason: str | None = None


class WebSettingsOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queues_count: int
    active_queues_count: int
    routing_rules_count: int
    active_routing_rules_count: int
    sla_policies_count: int
    calendars_count: int
    resolution_codes_count: int
    audit_records_count: int


class WebSettingsQueueMemberItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    role_in_queue: str | None = None


class WebSettingsOlaTargetItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: str
    ack_min: int
    processing_min: int


class WebSettingsQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    code: str
    name: str
    is_triage: bool
    is_active: bool
    auto_assign_enabled: bool
    open_tickets_count: int
    enabled_routing_rules_count: int
    members: list[WebSettingsQueueMemberItem] = Field(default_factory=list)
    ola_targets: list[WebSettingsOlaTargetItem] = Field(default_factory=list)


class WebSettingsRoutingRuleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    enabled: bool
    priority_order: int
    condition_json: dict | None = None
    target_queue_id: int
    target_queue_name: str | None = None


class WebSettingsRoutingBuilderOperatorItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class WebSettingsRoutingBuilderFieldItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    label: str
    source: str
    form_key: str | None = None
    form_title: str | None = None
    field_type: str | None = None


class WebSettingsRoutingBuilderFormFieldItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    field: str
    type: str


class WebSettingsRoutingBuilderFormItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    request_kind: str
    title: str
    fields: list[WebSettingsRoutingBuilderFormFieldItem] = Field(default_factory=list)


class WebSettingsRoutingBuilderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operators: list[WebSettingsRoutingBuilderOperatorItem] = Field(default_factory=list)
    fields: list[WebSettingsRoutingBuilderFieldItem] = Field(default_factory=list)
    forms: list[WebSettingsRoutingBuilderFormItem] = Field(default_factory=list)


class WebSettingsTicketStatusItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str
    requester_status: str
    requester_label: str
    next_action_owner: str
    stage: str
    waits: bool
    terminal: bool


class WebSettingsRequesterStatusItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str
    internal_statuses: list[str] = Field(default_factory=list)


class WebSettingsNextActionOwnerItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str
    internal_statuses: list[str] = Field(default_factory=list)


class WebSettingsWorkflowProfileItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_type: str
    label: str
    purpose: str
    suggested_path: list[str] = Field(default_factory=list)
    allowed_statuses: list[str] = Field(default_factory=list)
    required_create_fields: list[str] = Field(default_factory=list)
    required_resolve_fields: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    requires_change_plan: bool = False
    requires_action_log: bool = False
    evidence_required_for_priorities: list[str] = Field(default_factory=list)
    transitions: dict[str, list[str]] = Field(default_factory=dict)
    transition_gates: dict[str, dict[str, dict]] = Field(default_factory=dict)


class WebSettingsRequestTemplateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    public_title: str
    internal_name: str
    active: bool = True
    version: str
    classification: dict
    form: dict
    workflow: dict
    priority: dict
    routing: dict
    sla: dict
    ola: dict
    approvals: dict
    diagnostics: dict
    closure: dict
    visibility: dict
    notifications: dict
    field_roles: dict[str, list[str]] = Field(default_factory=dict)
    policies_missing: list[str] = Field(default_factory=list)


class WebSettingsTicketTypeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    version: str
    title: str
    description: str | None = None
    default_workflow_profile_id: str | None = None
    default_priority_policy_code: str | None = None
    default_routing_policy_code: str | None = None
    default_sla_policy_id: int | None = None
    default_sla_policy_code: str | None = None
    default_ola_policy_code: str | None = None
    default_approval_policy_code: str | None = None
    default_diagnostic_policy_code: str | None = None
    default_closure_policy_code: str | None = None
    default_visibility_policy_code: str | None = None
    default_notification_policy_code: str | None = None
    default_reporting_policy_code: str | None = None
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)
    is_active: bool = True
    published_at: str | None = None
    created_at: str | None = None
    created_by: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None


class WebSettingsProcessSchemaItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    meaning: str
    source: str
    ui_surface: str
    status: str


class WebSettingsSupportLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    competence_depth: str
    routing_role: str
    status: str


class WebSettingsPriorityModelPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direct_user_priority_choice: bool
    impact_levels: list[str] = Field(default_factory=list)
    urgency_levels: list[str] = Field(default_factory=list)
    importance_sources: list[str] = Field(default_factory=list)
    modifiers: list[str] = Field(default_factory=list)


class WebSettingsTicketGovernancePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fsm_mode: str
    legacy_role_fields: bool
    auto_close_hours: int
    resolution_validation_mode: str
    require_root_cause_priorities: list[str] = Field(default_factory=list)
    evidence_gate_enabled: bool
    passport_enabled: bool
    requester_confirmation_required: bool


class WebSettingsTicketOperationalFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    admin_config_api_enabled: bool
    admin_config_write_enabled: bool
    auditor_role_enabled: bool
    sla_calendar_enabled: bool
    ola_enabled: bool
    retention_enabled: bool
    retention_dry_run: bool
    events_hot_retention_days: int
    admin_audit_hot_retention_days: int
    take_queue_mode: str
    take_queue_common_code: str
    take_queue_test_code: str


class WebSettingsTicketSettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    internal_statuses: list[WebSettingsTicketStatusItem] = Field(default_factory=list)
    requester_statuses: list[WebSettingsRequesterStatusItem] = Field(default_factory=list)
    next_action_owners: list[WebSettingsNextActionOwnerItem] = Field(default_factory=list)
    workflow_profiles: list[WebSettingsWorkflowProfileItem] = Field(default_factory=list)
    ticket_types: list[WebSettingsTicketTypeItem] = Field(default_factory=list)
    request_templates: list[WebSettingsRequestTemplateItem] = Field(default_factory=list)
    process_schema: list[WebSettingsProcessSchemaItem] = Field(default_factory=list)
    support_lines: list[WebSettingsSupportLineItem] = Field(default_factory=list)
    priority_model: WebSettingsPriorityModelPayload
    governance: WebSettingsTicketGovernancePayload
    operational_flags: WebSettingsTicketOperationalFlags


class WebSettingsSlaTargetItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: str
    first_response_min: int
    resolution_min: int


class WebSettingsPriorityMatrixItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    impact: int
    urgency: int
    priority: str


class WebSettingsSlaPolicyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    timezone: str
    business_hours_json: dict | None = None
    calendar_id: int | None = None
    calendar_name: str | None = None
    is_default: bool
    is_active: bool
    open_tickets_count: int
    targets: list[WebSettingsSlaTargetItem] = Field(default_factory=list)
    priority_matrix: list[WebSettingsPriorityMatrixItem] = Field(default_factory=list)


class WebSettingsCalendarItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    code: str
    name: str
    timezone: str
    weekly_hours_json: dict[str, Any] | list[Any] | None = None
    holidays_json: dict[str, Any] | list[Any] | None = None
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None


class WebSettingsResolutionCodeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    is_active: bool
    sort_order: int
    usage_count: int


class WebSettingsAuditItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    entity_type: str
    entity_id: str
    action: str
    actor_id: str
    actor_role: str
    trace_id: str | None = None
    created_at: str | None = None


class WebSettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: WebSettingsCapabilities
    overview: WebSettingsOverview
    routing_builder: WebSettingsRoutingBuilderPayload
    ticket_settings: WebSettingsTicketSettingsPayload
    queues: list[WebSettingsQueueItem] = Field(default_factory=list)
    routing_rules: list[WebSettingsRoutingRuleItem] = Field(default_factory=list)
    sla_policies: list[WebSettingsSlaPolicyItem] = Field(default_factory=list)
    calendars: list[WebSettingsCalendarItem] = Field(default_factory=list)
    resolution_codes: list[WebSettingsResolutionCodeItem] = Field(default_factory=list)
    audit: list[WebSettingsAuditItem] = Field(default_factory=list)
