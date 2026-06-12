from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SupportObserverCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_summary_endpoint: str
    drawer_tab: str


class SupportBootstrapPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace: str
    features: list[str]
    observer: SupportObserverCapabilities


class SupportFilterOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class SupportQueueFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_options: list[SupportFilterOption]
    status_options: list[SupportFilterOption]
    smart_view_options: list[SupportFilterOption] = Field(default_factory=list)


class SupportCountItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str
    count: int


class SupportQueueCountItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None
    code: str | None
    name: str | None
    count: int


class SupportQueueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible_count: int
    selected_ticket_id: str | None
    scope_counts: list[SupportCountItem] = Field(default_factory=list)
    status_counts: list[SupportCountItem] = Field(default_factory=list)
    smart_view_counts: list[SupportCountItem] = Field(default_factory=list)
    queue_counts: list[SupportQueueCountItem] = Field(default_factory=list)


class SupportQueueTicketItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    ticket_code: str | None
    title: str
    status: str
    status_label: str
    requester_status: str
    requester_status_label: str
    public_status: str
    public_status_label: str
    next_action_owner: str | None
    next_action_due_at: str | None
    first_response_at: str | None = None
    first_response_due_at: str | None = None
    resolution_due_at: str | None = None
    status_reason: str | None
    priority: str | None = None
    priority_class: str | None = None
    queue_code: str | None
    assignee_id: str | None
    assignee_display_name: str | None = None
    requester_display_name: str | None
    device_id: str | None
    updated_at: str | None
    created_at: str | None
    hidden_from_workspace: bool = False
    hidden_at: str | None = None
    hidden_by: str | None = None
    hidden_reason: str | None = None
    archived_at: str | None = None
    archived_by: str | None = None
    archive_reason: str | None = None
    requires_operator_action: bool
    unread_user_messages: int


class SupportQueuePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str
    query: str
    status_filter: str
    smart_view: str = "all"
    summary: SupportQueueSummary
    filters: SupportQueueFilters
    tickets: list[SupportQueueTicketItem]


class SupportQueueSavedViewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    scope: str
    owner_actor_id: str | None = None
    queue_id: int | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    columns: list[str] = Field(default_factory=list)
    sort: list[dict[str, Any]] = Field(default_factory=list)
    is_favorite: bool = False
    is_default: bool = False
    created_at: str | None = None
    updated_at: str | None = None
    created_by: str | None = None
    updated_by: str | None = None


class SupportQueueSavedViewsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    views: list[SupportQueueSavedViewItem] = Field(default_factory=list)
    default_view_id: str | None = None
    default_columns: list[str] = Field(default_factory=list)


class SupportQueueSavedViewUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    scope: str = "personal"
    queue_id: int | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    columns: list[str] = Field(default_factory=list)
    sort: list[dict[str, Any]] = Field(default_factory=list)
    is_favorite: bool = False
    is_default: bool = False


class SupportQueueSavedViewDeletePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool
    id: str


class SupportWorkspaceSummaryQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str | None = None
    name: str
    count: int


class SupportWorkspaceSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    views: dict[str, int] = Field(default_factory=dict)
    queues: list[SupportWorkspaceSummaryQueueItem] = Field(default_factory=list)
    smart_view_counts: list[SupportCountItem] = Field(default_factory=list)
    smart_view_options: list[SupportFilterOption] = Field(default_factory=list)


class CommandCenterTimerState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str = "unknown"
    due_at: str | None = None
    remaining_seconds: int | None = None


class CommandCenterOperationState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    status: str | None = None
    tool_name: str | None = None
    failed_at: str | None = None
    error_summary: str | None = None


class CommandCenterAgentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str | None = None
    connection_state: str = "unknown"
    last_seen_at: str | None = None


class CommandCenterDiagnosticsState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommended: bool = False
    profile_code: str | None = None
    reason: str | None = None


class CommandCenterClosureState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocked: bool = False
    missing_count: int | None = None
    primary_blocker: str | None = None


class CommandCenterSimilarGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_key: str
    count: int
    window_hours: int
    sample_ticket_ids: list[str] = Field(default_factory=list)
    reason: str


class CommandCenterItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ticket_id: str
    ticket_number: str | None = None
    title: str
    status: str
    priority: str | None = None
    queue: str | None = None
    assignee: str | None = None
    requester_name: str | None = None
    service_code: str | None = None
    offering_code: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    next_action_owner: str | None = None
    next_action_due_at: str | None = None
    requires_operator_action: bool = False
    unread_user_messages: int = 0
    sla: CommandCenterTimerState | None = None
    ola: CommandCenterTimerState | None = None
    operation: CommandCenterOperationState | None = None
    agent: CommandCenterAgentState | None = None
    diagnostics: CommandCenterDiagnosticsState | None = None
    closure: CommandCenterClosureState | None = None
    similar_group: CommandCenterSimilarGroup | None = None
    reason: str
    href: str


class CommandCenterSectionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    href: str


class CommandCenterSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    description: str
    severity: str
    count: int
    updated_at: str | None = None
    items: list[CommandCenterItem] = Field(default_factory=list)
    action: CommandCenterSectionAction | None = None


class OperatorCommandCenterFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue: str | None = None
    assignee: str | None = None
    query: str | None = None
    window_hours: int
    limit_per_section: int


class OperatorCommandCenterSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_attention_items: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    new_unassigned_count: int = 0
    operator_action_count: int = 0
    unread_user_messages_count: int = 0
    sla_risk_count: int = 0
    ola_risk_count: int = 0
    pending_approval_count: int = 0
    pending_consent_count: int = 0
    failed_operation_count: int = 0
    agent_offline_active_count: int = 0
    diagnostics_recommended_count: int = 0
    closure_blocked_count: int = 0
    similar_spikes_count: int = 0


class OperatorCommandCenterPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str
    scope: str
    filters: OperatorCommandCenterFilters
    summary: OperatorCommandCenterSummary
    sections: list[CommandCenterSection] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SupportTicketQueueInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None
    code: str | None
    name: str | None


class SupportTicketQueueMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    role_in_queue: str | None


class SupportTicketApprovalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    approval_type: str
    approver_id: str | None = None
    status: str
    reason: str | None = None
    requested_by: str | None = None
    requested_at: str | None = None
    decided_at: str | None = None
    due_at: str | None = None
    reminder_at: str | None = None
    escalation_at: str | None = None
    reminded_at: str | None = None
    escalated_at: str | None = None
    timed_out_at: str | None = None
    current: bool = False


class SupportTicketApprovalSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: bool = False
    status: str = "not_started"
    approval_mode: str = "any_one"
    approver_source: str | None = None
    current_action_owner: str | None = None
    require_comment_on_reject: bool = False
    waiting_status: str | None = None
    approved_transition: str | None = None
    rejected_transition: str | None = None
    due_in: str | None = None
    reminder_after: str | None = None
    escalate_after: str | None = None
    pending_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    timed_out_count: int = 0
    items: list[SupportTicketApprovalItem] = Field(default_factory=list)


class SupportTicketDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    ticket_code: str | None
    title: str
    description: str | None
    status: str
    status_label: str
    requester_status: str
    requester_status_label: str
    public_status: str
    public_status_label: str
    next_action_owner: str | None
    next_action_due_at: str | None
    status_reason: str | None
    requester_display_name: str | None
    device_id: str | None
    ticket_type: str | None = None
    category_id: int | None = None
    service_id: int | None = None
    subcategory_id: int | None = None
    priority: str | None = None
    priority_class: str | None = None
    impact: int | None = None
    urgency: int | None = None
    importance: int | None = None
    priority_decision: dict[str, Any] = Field(default_factory=dict)
    first_response_at: str | None = None
    first_response_due_at: str | None = None
    resolution_due_at: str | None = None
    queue: SupportTicketQueueInfo
    assignee_id: str | None
    updated_at: str | None
    created_at: str | None
    hidden_from_workspace: bool = False
    hidden_at: str | None = None
    hidden_by: str | None = None
    hidden_reason: str | None = None
    archived_at: str | None = None
    archived_by: str | None = None
    archive_reason: str | None = None
    resolution_code: str | None = None
    resolution_summary: str | None = None
    requester_resolution_summary: str | None = None
    evidence_required: bool = False
    evidence_ref: str | None = None
    closure_feedback: dict[str, Any] = Field(default_factory=dict)
    approval_summary: SupportTicketApprovalSummary | None = None
    visibility: dict[str, Any] = Field(default_factory=dict)
    requester_visible_fields: list[str] = Field(default_factory=list)
    support_visible_fields: list[str] = Field(default_factory=list)
    queue_members: list[SupportTicketQueueMember]


class SupportTicketObserverSignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_signature: str | None = None
    title: str | None = None
    severity: str | None = None
    ticket_occurrences_count: int = 0
    global_occurrences_count: int | None = None
    last_seen_at: str | None = None


class SupportTicketObserverTraceCompact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    root_kind: str | None = None
    status: str | None = None
    title: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_count: int = 0
    operation_id: str | None = None
    tool_name: str | None = None
    playbook_id: str | None = None
    trace_url: str | None = None


class SupportTicketObserverOccurrenceCompact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_signature: str | None = None
    message: str | None = None
    stage: str | None = None
    severity: str | None = None
    trace_id: str | None = None
    created_at: str | None = None
    trace_url: str | None = None


class SupportTicketObserverSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    root_trace_id: str | None = None
    root_trace_url: str | None = None
    root_trace_status: str | None = None
    root_kind: str | None = None
    trace_count: int
    active_trace_count: int
    error_trace_count: int
    signature_count: int
    latest_trace_at: str | None = None
    latest_error_at: str | None = None
    latest_error_label: str | None = None
    latest_error_stage: str | None = None
    top_signature: SupportTicketObserverSignature | None = None
    has_active_operation: bool = False
    health_label: str = "empty"


class SupportTicketObserverPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_summary_endpoint: str
    summary: SupportTicketObserverSummary
    root_trace: SupportTicketObserverTraceCompact | None = None
    related_traces: list[SupportTicketObserverTraceCompact] = Field(default_factory=list)
    active_traces: list[SupportTicketObserverTraceCompact] = Field(default_factory=list)
    error_traces: list[SupportTicketObserverTraceCompact] = Field(default_factory=list)
    signatures: list[SupportTicketObserverSignature] = Field(default_factory=list)
    recent_occurrences: list[SupportTicketObserverOccurrenceCompact] = Field(default_factory=list)


class SupportTicketRequestFormRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    value: str


class SupportTicketRequestFormPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_kind: str | None = None
    form_key: str | None = None
    form_title: str | None = None
    rows: list[SupportTicketRequestFormRow] = Field(default_factory=list)


class SupportTicketReplyTo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_message_id: str | None = None
    preview: str | None = None
    sender_role: str | None = None
    sender_display_name: str | None = None
    ts: str | None = None


class SupportTicketMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str | None
    event_id: int | None
    event_type: str = "chat_message"
    event_category: str = "message"
    event_label: str | None = None
    event_details: dict[str, Any] = Field(default_factory=dict)
    requester_timeline_text: str | None = None
    requester_timeline_kind: str | None = None
    requester_timeline_payload: dict[str, Any] | None = None
    requester_timeline_icon: str | None = None
    requester_timeline_style: str | None = None
    from_role: str
    sender_display_name: str | None = None
    text: str
    ts: str | None
    visibility: str
    direction: str
    attachments: list[dict] = Field(default_factory=list)
    reply_to: SupportTicketReplyTo | None = None
    tool_name: str | None = None
    tool_status: str | None = None
    result_summary: str | None = None
    result_preview: str | None = None
    result_payload: Any | None = None
    result_presentation_schema: dict[str, Any] | None = None
    result_presentation_schema_source: str | None = None
    operation_steps: list[dict[str, Any]] = Field(default_factory=list)
    operation_id: str | None = None
    trace_id: str | None = None
    duration_ms: int | None = None
    retry_count: int | None = None
    max_retries: int | None = None
    retryable: bool | None = None
    can_retry: bool | None = None
    can_cancel: bool | None = None
    retry_url: str | None = None
    cancel_url: str | None = None
    retry_disabled_reason: str | None = None
    cancel_disabled_reason: str | None = None
    error_code: str | None = None
    error_category: str | None = None
    details_url: str | None = None


class SupportTicketPresence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requester_online: bool = False
    requester_last_seen_at: str | None = None
    requester_actor_ids: list[str] = Field(default_factory=list)
    support_online: bool = False
    support_last_seen_at: str | None = None
    support_actor_ids: list[str] = Field(default_factory=list)
    agent_online: bool = False


class SupportTicketDeviceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str | None = None
    hostname: str | None = None
    os: str | None = None
    agent_version: str | None = None
    last_seen_at: str | None = None
    online: bool = False


class SupportTicketRegistrySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: str | None = None
    person_display_name: str | None = None
    person_phone: str | None = None
    person_email: str | None = None
    person_source: str | None = None
    department_id: str | None = None
    department_name: str | None = None
    location_id: str | None = None
    location_display_name: str | None = None
    building: str | None = None
    floor: str | None = None
    room: str | None = None
    asset_id: str | None = None
    asset_name: str | None = None
    asset_type: str | None = None
    service_id: str | None = None
    service_name: str | None = None
    service_owner_queue_id: int | None = None
    service_owner_queue_name: str | None = None
    service_source: str | None = None


class SupportTicketOperationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    kind: str
    status: str
    display_status: str | None = None
    display_label: str | None = None
    scope: str = "ticket"
    tool_name: str | None = None
    command_name: str | None = None
    queued_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    trace_id: str | None = None
    retry_count: int = 0
    max_retries: int = 0
    retryable: bool = False
    can_retry: bool = False
    can_cancel: bool = False
    retry_url: str | None = None
    cancel_url: str | None = None
    retry_disabled_reason: str | None = None
    cancel_disabled_reason: str | None = None
    policy_labels: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_category: str | None = None
    details_url: str | None = None
    result_summary: str | None = None
    error_message: str | None = None
    trace_relation: str = "unknown"
    root_trace_id: str | None = None
    root_trace_url: str | None = None
    trace_url: str | None = None
    retry_of_operation_id: str | None = None
    retry_source_trace_id: str | None = None


class SupportTicketSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_event_id: int
    notification_unread: int
    presence: SupportTicketPresence
    device: SupportTicketDeviceSnapshot
    registry: SupportTicketRegistrySnapshot | None = None
    latest_operations: list[SupportTicketOperationSnapshot] = Field(default_factory=list)


class SupportStatusAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class SupportClosureRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    met: bool
    detail: str = ""
    fact_key: str | None = None
    severity: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    candidate_count: int = 0
    source_candidates: list[dict[str, Any]] = Field(default_factory=list)
    stale_reasons: list[str] = Field(default_factory=list)
    current_source_counts: dict[str, int] = Field(default_factory=dict)


class SupportTicketActions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_options: list[SupportStatusAction] = Field(default_factory=list)
    can_send_internal_note: bool = False
    can_hide_from_workspace: bool = False
    can_unhide_from_workspace: bool = False
    can_archive_ticket: bool = False
    can_unarchive_ticket: bool = False
    closure_requirements: list[SupportClosureRequirement] = Field(default_factory=list)
    approval: dict[str, Any] | None = None

    @property
    def closure_missing_count(self) -> int:
        return sum(1 for item in self.closure_requirements if not item.met)


class SupportMessageActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    message: SupportTicketMessage


class SupportStatusActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    status: str
    status_label: str


class SupportToolParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str | None = None
    description: str | None = None
    type: str = "string"
    required: bool = False
    default: Any | None = None


class SupportToolPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str
    label: str
    description: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class SupportToolItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    module_name: str | None = None
    description: str | None = None
    domain: str | None = None
    tool_kind: str | None = None
    risk_level: str = "safe_read"
    requires_consent: bool = False
    install_required: bool = False
    required_permission: str | None = None
    allowed_roles: list[str] = Field(default_factory=list)
    policy_labels: list[str] = Field(default_factory=list)
    source: str
    params_schema: list[SupportToolParameter] = Field(default_factory=list)
    presets: list[SupportToolPreset] = Field(default_factory=list)
    execution: dict[str, Any] = Field(default_factory=dict)
    deployment: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
    readiness: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)


class SupportTicketToolsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    device_id: str | None = None
    tools: list[SupportToolItem] = Field(default_factory=list)


class SupportPlaybookItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    playbook_version_id: int
    key: str
    name: str
    domain: str | None = None
    version: str | None = None
    status: str
    blocks_count: int = 0
    required_tools: list[str] = Field(default_factory=list)
    missing_tools: list[str] = Field(default_factory=list)
    missing_params: list[str] = Field(default_factory=list)
    can_run: bool = False
    readiness_label: str
    updated_at: str | None = None


class SupportPlaybookRecentRunStepError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_key: str | None = None
    tool_name: str | None = None
    error_code: str | None = None
    error_message: str
    stage: str | None = None


class SupportPlaybookRecentRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    playbook_run_id: int
    playbook_version_id: int
    playbook_key: str | None = None
    playbook_name: str | None = None
    status: str
    error_code: str | None = None
    error_message: str | None = None
    trigger_type: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    step_errors: list[SupportPlaybookRecentRunStepError] = Field(default_factory=list)


class SupportDiagnosticPolicyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggested_playbooks: list[str] = Field(default_factory=list)
    auto_run_enabled: bool = False
    auto_run_priorities: list[str] = Field(default_factory=list)
    requester_consent_required: bool = False
    high_risk_consent_required: bool = False
    attach_to_timeline: bool = False
    attach_to_passport: bool = False
    attach_as_evidence: bool = False
    reroute_by_result: dict[str, str] = Field(default_factory=dict)


class SupportTicketPlaybooksPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    device_id: str | None = None
    diagnostic_policy: SupportDiagnosticPolicyPayload | None = None
    playbooks: list[SupportPlaybookItem] = Field(default_factory=list)
    recent_runs: list[SupportPlaybookRecentRun] = Field(default_factory=list)


class SupportTicketPassportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passport_id: int
    ticket_id: str
    version: int
    status: str
    summary_source: str
    generated_at: str | None = None
    generated_by: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None
    sections: dict[str, str] = Field(default_factory=dict)
    source_event_ids: list[int] = Field(default_factory=list)
    source_operation_ids: list[str] = Field(default_factory=list)
    source_payload: dict[str, Any] = Field(default_factory=dict)
    stale: bool = False


class SupportTicketEvidenceItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    ticket_id: str
    passport_id: int | None = None
    evidence_type: str
    source_ref: str | None = None
    source_kind: str | None = None
    source_id: str | None = None
    required_fact: str | None = None
    section_key: str | None = None
    artifact_id: str | None = None
    title: str
    summary: str | None = None
    visibility: str
    verification_status: str = "unverified"
    verified_by: str | None = None
    verified_at: str | None = None
    captured_at: str | None = None
    public_summary: str | None = None
    internal_summary: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    export_visibility: str = "internal"
    created_by: str | None = None
    created_at: str | None = None


class SupportTicketActionLogPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    ticket_id: str
    passport_id: int | None = None
    action_type: str
    actor_id: str | None = None
    source_event_id: int | None = None
    operation_id: str | None = None
    title: str
    summary: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None


class SupportTicketApprovalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    ticket_id: str
    passport_id: int | None = None
    approval_type: str
    approver_id: str | None = None
    status: str
    reason: str | None = None
    requested_by: str | None = None
    requested_at: str | None = None
    decided_at: str | None = None


class SupportTicketRelatedObjectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    ticket_id: str
    passport_id: int | None = None
    object_type: str
    object_ref: str
    display_name: str | None = None
    relation_type: str
    source: str
    created_at: str | None = None


class SupportTicketPassportMissingFactPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_fact: str
    section_key: str | None = None
    source: str
    current_value: str | None = None
    requester_visible_label: str
    severity: str
    accepted_evidence_types: list[str] = Field(default_factory=list)
    candidate_count: int = 0
    recommended_actions: list[str] = Field(default_factory=list)
    blocking_for_closure: bool = False
    satisfied_by_evidence_ids: list[int] = Field(default_factory=list)
    source_candidates: list[dict[str, Any]] = Field(default_factory=list)


class SupportTicketPassportRequirementsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_sections: list[str] = Field(default_factory=list)
    require_official_passport: bool = False
    missing_facts: list[SupportTicketPassportMissingFactPayload] = Field(default_factory=list)
    missing_count: int = 0
    blocking_missing_count: int = 0
    export_preview: dict[str, list[str]] = Field(default_factory=dict)
    knowledge_draft_hints: dict[str, Any] = Field(default_factory=dict)


class SupportTicketPassportDetailPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    status: str
    passport: SupportTicketPassportPayload | None = None
    requirements: SupportTicketPassportRequirementsPayload = Field(default_factory=SupportTicketPassportRequirementsPayload)
    evidence: list[SupportTicketEvidenceItemPayload] = Field(default_factory=list)
    actions: list[SupportTicketActionLogPayload] = Field(default_factory=list)
    approvals: list[SupportTicketApprovalPayload] = Field(default_factory=list)
    related_objects: list[SupportTicketRelatedObjectPayload] = Field(default_factory=list)


class SupportTicketPassportGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "refresh"
    include_internal_notes: bool = True


class SupportTicketPassportPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator_check_summary: str | None = None
    changes_made_summary: str | None = None
    repeat_guidance: str | None = None
    user_result_summary: str | None = None
    internal_result_summary: str | None = None


class SupportTicketPassportEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: str
    source_ref: str | None = None
    source_kind: str | None = None
    source_id: str | None = None
    required_fact: str | None = None
    section_key: str | None = None
    artifact_id: str | None = None
    title: str
    summary: str | None = None
    visibility: str = "internal"
    verification_status: str = "unverified"
    captured_at: str | None = None
    public_summary: str | None = None
    internal_summary: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    export_visibility: str = "internal"


class SupportTicketEvidenceCandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    source_kind: str
    source_id: str
    source_ref: str
    source_quality: str
    evidence_type: str
    required_fact: str
    section_key: str
    artifact_id: str | None = None
    title: str
    summary: str | None = None
    visibility: str = "internal"
    captured_at: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    existing_evidence_id: int | None = None


class SupportTicketEvidenceCandidatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    candidates: list[SupportTicketEvidenceCandidatePayload] = Field(default_factory=list)


class SupportTicketPassportEvidenceLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_kind: str
    source_id: str
    required_fact: str | None = None
    visibility: str = "internal"


class SupportTicketPassportEvidenceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_status: str | None = None
    reason: str | None = None
    visibility: str | None = None
    export_visibility: str | None = None
    public_summary: str | None = None
    internal_summary: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class SupportTicketKnowledgeDraftPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    problem: str
    resolution: str
    repeat_guidance: str
    source_passport_id: int
    item_id: str | None = None
    version_id: str | None = None
    status: str = "draft"
    item_type: str | None = None
    edit_url: str | None = None
    warnings: list[str] = Field(default_factory=list)
    bindings: list[dict[str, Any]] = Field(default_factory=list)


class SupportToolActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    device_id: str
    tool_name: str
    dispatch_status: str
    operation_id: str
    poll_url: str
    trace_id: str | None = None
    message: str


class SupportPlaybookRunActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    device_id: str
    playbook_version_id: int
    playbook_run_id: int
    status: str
    first_operation_id: str | None = None
    observer_url: str
    message: str


class SupportTicketMutationActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    action: str
    status: str
    status_label: str
    queue: SupportTicketQueueInfo
    assignee_id: str | None = None
    priority: str | None = None
    priority_class: str | None = None
    auto_assigned: bool = False
    hidden_from_workspace: bool = False
    hidden_at: str | None = None
    hidden_by: str | None = None
    hidden_reason: str | None = None
    archived_at: str | None = None
    archived_by: str | None = None
    archive_reason: str | None = None


class SupportQueueMassActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    ticket_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    comment: str | None = None
    assignee_id: str | None = None
    queue_id: int | None = None
    priority: str | None = None
    internal_note: str | None = None
    tool_name: str | None = None
    preset_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    mass_problem_key: str | None = None


class SupportQueueMassActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    ticket_code: str | None = None
    status: str
    action: str
    message: str
    result: SupportTicketMutationActionResult | SupportToolActionResult | None = None


class SupportQueueMassActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    requested_count: int
    success_count: int
    skipped_count: int
    error_count: int
    results: list[SupportQueueMassActionItem] = Field(default_factory=list)


class SupportWorkspaceCleanupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = "cleanup_noise"
    matched_count: int = 0
    hidden_count: int = 0
    hidden_ticket_ids: list[str] = Field(default_factory=list)
    skipped_ticket_ids: list[str] = Field(default_factory=list)


class SupportKnowledgeSimilarTicket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    number: str | None = None
    subject: str
    resolution_summary: str | None = None


class SupportKnowledgeArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    url: str | None = None


class SupportKnowledgeRequesterAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    version_id: str | None = None
    result: str
    surface: str
    occurred_at: str


class SupportKnowledgeAiSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    sources: list[str] = Field(default_factory=list)
    confidence: str = "none"
    source_count: int = 0


class SupportKnowledgeDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "support_knowledge_provider"
    provider_version: str = "local-v1"
    provider_status: str = "ok"
    external_provider_status: str = "not_configured"
    fallback_reason: str | None = None
    catalog_entry_count: int = 0
    query_tokens: list[str] = Field(default_factory=list)
    source_counts: dict[str, int] = Field(default_factory=dict)
    query_signals: list[str] = Field(default_factory=list)
    article_matches: dict[str, dict[str, Any]] = Field(default_factory=dict)
    similar_ticket_matches: dict[str, dict[str, Any]] = Field(default_factory=dict)


class SupportTicketKnowledgeSuggestionsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    similar_tickets: list[SupportKnowledgeSimilarTicket] = Field(default_factory=list)
    articles: list[SupportKnowledgeArticle] = Field(default_factory=list)
    requester_attempts: list[SupportKnowledgeRequesterAttempt] = Field(default_factory=list)
    ai_summary: SupportKnowledgeAiSummary = Field(default_factory=SupportKnowledgeAiSummary)
    diagnostics: SupportKnowledgeDiagnostics = Field(default_factory=SupportKnowledgeDiagnostics)


class SupportTicketTimerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    due_at: str | None = None
    remaining_seconds: int | None = None
    target_seconds: int | None = None
    status: str = "unknown"


class SupportTicketSlaOlaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_response: SupportTicketTimerPayload = Field(default_factory=SupportTicketTimerPayload)
    resolution: SupportTicketTimerPayload = Field(default_factory=SupportTicketTimerPayload)
    ola_ack: SupportTicketTimerPayload = Field(default_factory=SupportTicketTimerPayload)
    ola_processing: SupportTicketTimerPayload = Field(default_factory=SupportTicketTimerPayload)


class SupportTicketPassportReadinessItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    status: str = "pending"


class SupportTicketPassportReadinessPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    status: str
    done: int
    total: int
    items: list[SupportTicketPassportReadinessItem] = Field(default_factory=list)


class SupportTicketClosurePlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    met: bool = False
    detail: str = ""
    source: str = "closure_requirement"
    action_kind: str = "review_requirement"
    action_label: str = "Проверить требование"
    severity: str | None = None
    candidate_count: int = 0
    fact_key: str | None = None
    blocking_for_closure: bool = True


class SupportTicketClosurePlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    ready_for_resolution: bool = True
    missing_count: int = 0
    total: int = 0
    evidence_candidate_count: int = 0
    recommended_next_action: str | None = None
    blockers: list[SupportTicketClosurePlanItem] = Field(default_factory=list)


class SupportTicketQualityFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: str
    rating: int
    sentiment: str | None = None
    problem_resolved: bool | None = None
    resolution_confirmed: bool | None = None
    reason_codes: list[str] = Field(default_factory=list)
    comment: str | None = None
    source_surface: str | None = None
    submitted_at: str | None = None


class SupportTicketQualityReopenEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reopen_id: str
    reason_code: str
    reason_comment: str | None = None
    previous_status: str | None = None
    new_status: str | None = None
    created_at: str | None = None


class SupportTicketQualityReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    review_type: str
    severity: str
    status: str
    assigned_to_actor_id: str | None = None
    score: int | None = None
    due_at: str | None = None
    created_at: str | None = None
    closed_at: str | None = None


class SupportTicketQualityAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    source_kind: str
    action_type: str
    title: str
    status: str
    priority: str
    owner_actor_id: str | None = None
    due_at: str | None = None
    created_at: str | None = None
    closed_at: str | None = None


class SupportTicketQualityPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latest_feedback: SupportTicketQualityFeedback | None = None
    reopen_events: list[SupportTicketQualityReopenEvent] = Field(default_factory=list)
    reviews: list[SupportTicketQualityReview] = Field(default_factory=list)
    improvement_actions: list[SupportTicketQualityAction] = Field(default_factory=list)
    indicators: list[str] = Field(default_factory=list)


class SupportTicketDetailPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket: SupportTicketDetail
    request_form: SupportTicketRequestFormPayload | None = None
    observer: SupportTicketObserverPayload
    timeline: list[SupportTicketMessage]
    snapshot: SupportTicketSnapshot
    actions: SupportTicketActions
    quality: SupportTicketQualityPayload | None = None


class SupportTicketTimelinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    filter: str = "all"
    items: list[SupportTicketMessage] = Field(default_factory=list)
    total: int = 0
    limit: int = 80


class SupportTicketInventoryAgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connection_state: str = "unknown"
    last_seen_at: str | None = None
    version: str | None = None
    update_status: str | None = None
    update_available: bool | None = None


class SupportTicketInventorySnapshotContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latest_snapshot_id: str | None = None
    collected_at: str | None = None
    age_seconds: int | None = None
    freshness: str = "unknown"
    source: str | None = None
    summary: dict[str, Any] | None = None


class SupportTicketInventoryBindingContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    responsible_person: str | None = None
    department: str | None = None
    building: str | None = None
    room: str | None = None
    status: str | None = None
    tags: list[str] = Field(default_factory=list)


class SupportTicketInventoryRefreshContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_enabled: bool | None = None
    last_run_id: str | None = None
    last_run_status: str | None = None
    last_run_at: str | None = None
    next_due_at: str | None = None
    can_request_refresh: bool = False


class SupportTicketInventorySignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stale_inventory: bool = False
    missing_inventory: bool = False
    agent_offline: bool = False
    failed_recent_refresh: bool = False
    failed_recent_operation: bool = False


class SupportTicketInventoryContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str | None = None
    hostname: str | None = None
    display_name: str | None = None
    agent: SupportTicketInventoryAgentContext | None = None
    inventory: SupportTicketInventorySnapshotContext | None = None
    binding: SupportTicketInventoryBindingContext | None = None
    refresh: SupportTicketInventoryRefreshContext | None = None
    signals: SupportTicketInventorySignals | None = None


class SupportTicketWorkspacePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: SupportTicketDetailPayload
    tools: SupportTicketToolsPayload
    playbooks: SupportTicketPlaybooksPayload
    passport: SupportTicketPassportDetailPayload
    knowledge: SupportTicketKnowledgeSuggestionsPayload
    sla_ola: SupportTicketSlaOlaPayload
    passport_readiness: SupportTicketPassportReadinessPayload
    closure_plan: SupportTicketClosurePlanPayload
    inventory_context: SupportTicketInventoryContext | None = None
