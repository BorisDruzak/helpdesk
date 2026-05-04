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


class SupportQueueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible_count: int
    selected_ticket_id: str | None
    scope_counts: list[SupportCountItem] = Field(default_factory=list)
    status_counts: list[SupportCountItem] = Field(default_factory=list)
    smart_view_counts: list[SupportCountItem] = Field(default_factory=list)


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
    status_reason: str | None
    queue_code: str | None
    assignee_id: str | None
    requester_display_name: str | None
    device_id: str | None
    updated_at: str | None
    created_at: str | None
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
    first_response_due_at: str | None = None
    resolution_due_at: str | None = None
    queue: SupportTicketQueueInfo
    assignee_id: str | None
    updated_at: str | None
    created_at: str | None
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


class SupportTicketObserverSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    root_trace_id: str | None = None
    trace_count: int
    active_trace_count: int
    error_trace_count: int
    signature_count: int
    latest_trace_at: str | None = None


class SupportTicketObserverPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_summary_endpoint: str
    summary: SupportTicketObserverSummary


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
    department_id: str | None = None
    department_name: str | None = None
    location_id: str | None = None
    location_display_name: str | None = None
    building: str | None = None
    room: str | None = None
    asset_id: str | None = None
    asset_name: str | None = None
    asset_type: str | None = None
    service_id: str | None = None
    service_name: str | None = None


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
    finished_at: str | None = None
    result_summary: str | None = None
    error_message: str | None = None


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


class SupportTicketActions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_options: list[SupportStatusAction] = Field(default_factory=list)
    can_send_internal_note: bool = False
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
    risk_level: str = "safe_read"
    requires_consent: bool = False
    install_required: bool = False
    source: str
    params_schema: list[SupportToolParameter] = Field(default_factory=list)
    presets: list[SupportToolPreset] = Field(default_factory=list)


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


class SupportTicketKnowledgeDraftPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    problem: str
    resolution: str
    repeat_guidance: str
    source_passport_id: int


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


class SupportTicketDetailPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket: SupportTicketDetail
    request_form: SupportTicketRequestFormPayload | None = None
    observer: SupportTicketObserverPayload
    timeline: list[SupportTicketMessage]
    snapshot: SupportTicketSnapshot
    actions: SupportTicketActions
