from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdminObserverCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quick_endpoint: str
    traces_endpoint: str


class AdminBootstrapPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace: str
    features: list[str]
    observer: AdminObserverCapabilities


class AdminObserverQuickLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quick_endpoint: str
    traces_endpoint: str
    runtime_endpoint: str


class AdminObserverQuickSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lookback_hours: int
    recent_trace_count: int
    hot_trace_count: int
    signature_count: int
    degradation_group_count: int
    dangerous_flow_count: int


class AdminObserverRuntimeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    running: bool
    health_status: str
    health_status_label: str
    pending_trace_count: int | None = None
    last_projected_at: str | None = None
    issues: list[str] = Field(default_factory=list)


class AdminObserverQuickTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    root_kind: str | None = None
    root_kind_label: str
    status: str | None = None
    status_label: str
    ticket_id: str | None = None
    ticket_code: str | None = None
    ticket_title: str | None = None
    ticket_status: str | None = None
    ticket_status_label: str | None = None
    ticket_priority: str | None = None
    queue_name: str | None = None
    requester_display_name: str | None = None
    device_id: str | None = None
    device_hostname: str | None = None
    device_label: str | None = None
    operation_label: str | None = None
    latest_error_label: str | None = None
    latest_error_stage: str | None = None
    primary_tool_name: str | None = None
    primary_module_name: str | None = None
    display_title: str | None = None
    display_subtitle: str | None = None
    duration_ms: int | None = None
    error_count: int = 0
    span_count: int = 0
    started_at: str | None = None
    finished_at: str | None = None


class AdminObserverSignatureItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_signature: str
    title: str
    tool_name: str | None = None
    component: str | None = None
    occurrences_count: int
    affected_devices_count: int
    last_seen_at: str | None = None


class AdminObserverDegradationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_kind: str | None = None
    operation_kind_label: str
    tool_name: str | None = None
    operations_count: int
    timeout_count: int
    retried_operations_count: int
    slow_operations_count: int
    max_duration_ms: int
    latest_operation_at: str | None = None


class AdminObserverDangerousFlowItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_kind: str
    root_kind_label: str
    operations_count: int
    error_count: int
    timeout_count: int
    retried_count: int
    active_count: int
    latest_operation_at: str | None = None


class AdminObserverQuickPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: AdminObserverQuickSummary
    runtime: AdminObserverRuntimeSummary
    hot_traces: list[AdminObserverQuickTrace]
    top_signatures: list[AdminObserverSignatureItem]
    top_degradations: list[AdminObserverDegradationItem]
    dangerous_flows: list[AdminObserverDangerousFlowItem]
    links: AdminObserverQuickLinks


class AdminObserverTraceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    root_span_id: str | None = None
    root_kind: str | None = None
    root_kind_label: str
    status: str | None = None
    status_label: str
    ticket_id: str | None = None
    ticket_code: str | None = None
    ticket_title: str | None = None
    ticket_status: str | None = None
    ticket_status_label: str | None = None
    ticket_priority: str | None = None
    queue_name: str | None = None
    requester_display_name: str | None = None
    device_id: str | None = None
    device_hostname: str | None = None
    device_label: str | None = None
    operation_id: str | None = None
    operation_label: str | None = None
    latest_error_label: str | None = None
    latest_error_stage: str | None = None
    primary_tool_name: str | None = None
    primary_module_name: str | None = None
    display_title: str | None = None
    display_subtitle: str | None = None
    job_id: str | None = None
    duration_ms: int | None = None
    error_count: int = 0
    span_count: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    attrs_json: dict[str, Any] = Field(default_factory=dict)


class AdminObserverTracesQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str | None = None
    lookback_hours: int
    status_filter: str
    root_kind_filter: str
    limit: int
    query: str | None = None
    trace_id: str | None = None
    ticket_id: str | None = None
    operation_id: str | None = None
    tool_name: str | None = None
    module_name: str | None = None
    error_signature: str | None = None
    min_duration_ms: int | None = None
    playbook_run_id: int | None = None
    step_run_id: int | None = None
    route: str | None = None


class AdminObserverTracesSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible_count: int
    active_count: int
    error_count: int
    selected_trace_id: str | None = None


class AdminObserverTracesFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_options: list["AdminFilterOption"]
    root_kind_options: list["AdminFilterOption"]


class AdminObserverTracesLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail_endpoint_template: str
    runtime_endpoint: str


class AdminObserverTracesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: AdminObserverTracesQuery
    summary: AdminObserverTracesSummary
    filters: AdminObserverTracesFilters
    traces: list[AdminObserverTraceItem]
    links: AdminObserverTracesLinks


class AdminObserverTraceDetailSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    span_count: int
    error_count: int
    linked_trace_count: int


class AdminObserverTraceSpanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    span_id: str
    trace_id: str
    parent_span_id: str | None = None
    source_type: str | None = None
    source_ref: str | None = None
    name: str
    kind: str | None = None
    component: str | None = None
    event_type: str | None = None
    module_name: str | None = None
    tool_name: str | None = None
    status: str | None = None
    status_label: str
    stage_label: str | None = None
    stage_state: str | None = None
    stage_note: str | None = None
    is_failure_stage: bool = False
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    attrs_json: dict[str, Any] = Field(default_factory=dict)


class AdminObserverTraceSpanLinkItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    span_id: str
    linked_trace_id: str | None = None
    linked_span_id: str | None = None
    reason: str | None = None
    attrs_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class AdminObserverTraceErrorOccurrenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occurrence_id: str
    trace_id: str
    span_id: str | None = None
    error_signature: str
    device_id: str | None = None
    ticket_id: str | None = None
    operation_id: str | None = None
    component: str | None = None
    module_name: str | None = None
    tool_name: str | None = None
    error_kind: str | None = None
    exception_type: str | None = None
    failure_stage: str | None = None
    severity: str | None = None
    severity_label: str
    message_norm: str | None = None
    stack_hash: str | None = None
    attrs_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class AdminObserverTraceExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    launch_source: str
    launch_source_label: str
    actor_role: str | None = None
    actor_id: str | None = None
    actor_display_name: str | None = None
    actor_label: str | None = None
    tool_name: str | None = None
    tool_label: str | None = None
    tool_description: str | None = None
    module_name: str | None = None
    module_label: str | None = None
    preset_id: str | None = None
    preset_label: str | None = None
    preset_description: str | None = None
    error_code: str | None = None
    error_diagnosis: str | None = None
    error_details: str | None = None
    failure_stage: str | None = None
    failure_stage_label: str | None = None
    agent_online: bool | None = None
    agent_status_label: str | None = None
    agent_last_seen_at: str | None = None
    agent_last_handshake_at: str | None = None
    launch_path: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    human_timeline: list[str] = Field(default_factory=list)
    debug_refs: dict[str, Any] = Field(default_factory=dict)


class AdminObserverTraceDetailPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace: AdminObserverTraceItem
    summary: AdminObserverTraceDetailSummary
    explanation: AdminObserverTraceExplanation | None = None
    spans: list[AdminObserverTraceSpanItem]
    span_links: list[AdminObserverTraceSpanLinkItem]
    error_occurrences: list[AdminObserverTraceErrorOccurrenceItem]


class AdminFilterOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class AdminFormsFieldOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class AdminFormsVisibleWhen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    equals: str | None = None
    values: list[str] = Field(default_factory=list)


class AdminFormsFieldItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    type: str
    type_label: str
    required: bool = False
    placeholder: str | None = None
    help_text: str | None = None
    options: list[AdminFormsFieldOption] = Field(default_factory=list)
    visible_when: AdminFormsVisibleWhen | None = None
    validation: dict[str, Any] = Field(default_factory=dict)
    process_mapping: dict[str, Any] = Field(default_factory=dict)


class AdminFormsPlaybookTrigger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: str = "ticket_created"
    playbook_key: str
    module_kind: str = "diagnostic"
    enabled: bool = True


class AdminFormsFormItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    request_kind: str
    ticket_type: str | None = None
    title: str
    description: str | None = None
    category_id: int | None = None
    service_id: int | None = None
    subcategory_id: int | None = None
    default_queue_id: int | None = None
    sla_policy_id: int | None = None
    suggested_playbook_id: str | None = None
    field_roles: dict[str, list[str]] = Field(default_factory=dict)
    priority_policy: dict[str, Any] = Field(default_factory=dict)
    routing_policy: dict[str, Any] = Field(default_factory=dict)
    approval_policy: dict[str, Any] = Field(default_factory=dict)
    diagnostic_policy: dict[str, Any] = Field(default_factory=dict)
    ola_policy: dict[str, Any] = Field(default_factory=dict)
    closure_policy: dict[str, Any] = Field(default_factory=dict)
    visibility_policy: dict[str, Any] = Field(default_factory=dict)
    notification_policy: dict[str, Any] = Field(default_factory=dict)
    reporting_policy: dict[str, Any] = Field(default_factory=dict)
    priority_policy_ref: str | None = None
    routing_policy_ref: str | None = None
    sla_policy_ref: str | None = None
    ola_policy_ref: str | None = None
    approval_policy_ref: str | None = None
    diagnostic_policy_ref: str | None = None
    closure_policy_ref: str | None = None
    visibility_policy_ref: str | None = None
    notification_policy_ref: str | None = None
    reporting_policy_ref: str | None = None
    route_preview_examples: list[dict[str, Any]] = Field(default_factory=list)
    process_preview_examples: list[dict[str, Any]] = Field(default_factory=list)
    field_aliases: dict[str, str | list[str]] = Field(default_factory=dict)
    field_migration_note: str | None = None
    fields: list[AdminFormsFieldItem] = Field(default_factory=list)
    playbook_triggers: list[AdminFormsPlaybookTrigger] = Field(default_factory=list)


class AdminFormsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack_key: str
    version: str
    title: str
    description: str | None = None
    forms_count: int
    fields_count: int
    required_fields_count: int
    last_published_at: str | None = None
    last_published_by: str | None = None


class AdminFormsBuilderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_endpoint: str
    save_endpoint: str
    preview_endpoint: str
    process_preview_endpoint: str
    field_type_options: list[AdminFilterOption]
    field_role_options: list[AdminFilterOption] = Field(default_factory=list)


class AdminFormsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: AdminFormsSummary
    capabilities: AdminFormsBuilderCapabilities
    forms: list[AdminFormsFormItem] = Field(default_factory=list)


class AdminFormsSaveFieldOptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class AdminFormsSaveVisibleWhenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    equals: str | None = None
    values: list[str] = Field(default_factory=list)


class AdminFormsSaveFieldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    type: str
    required: bool = False
    placeholder: str | None = None
    help_text: str | None = None
    options: list[AdminFormsSaveFieldOptionRequest] = Field(default_factory=list)
    visible_when: AdminFormsSaveVisibleWhenRequest | None = None
    validation: dict[str, Any] = Field(default_factory=dict)
    process_mapping: dict[str, Any] = Field(default_factory=dict)


class AdminFormsSaveFormRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    request_kind: str
    ticket_type: str | None = None
    title: str
    description: str | None = None
    category_id: int | None = None
    service_id: int | None = None
    subcategory_id: int | None = None
    default_queue_id: int | None = None
    sla_policy_id: int | None = None
    suggested_playbook_id: str | None = None
    field_roles: dict[str, list[str]] = Field(default_factory=dict)
    priority_policy: dict[str, Any] = Field(default_factory=dict)
    routing_policy: dict[str, Any] = Field(default_factory=dict)
    sla_policy: dict[str, Any] = Field(default_factory=dict)
    approval_policy: dict[str, Any] = Field(default_factory=dict)
    diagnostic_policy: dict[str, Any] = Field(default_factory=dict)
    ola_policy: dict[str, Any] = Field(default_factory=dict)
    closure_policy: dict[str, Any] = Field(default_factory=dict)
    visibility_policy: dict[str, Any] = Field(default_factory=dict)
    notification_policy: dict[str, Any] = Field(default_factory=dict)
    reporting_policy: dict[str, Any] = Field(default_factory=dict)
    priority_policy_ref: str | None = None
    routing_policy_ref: str | None = None
    sla_policy_ref: str | None = None
    ola_policy_ref: str | None = None
    approval_policy_ref: str | None = None
    diagnostic_policy_ref: str | None = None
    closure_policy_ref: str | None = None
    visibility_policy_ref: str | None = None
    notification_policy_ref: str | None = None
    reporting_policy_ref: str | None = None
    route_preview_examples: list[dict[str, Any]] = Field(default_factory=list)
    process_preview_examples: list[dict[str, Any]] = Field(default_factory=list)
    field_aliases: dict[str, str | list[str]] = Field(default_factory=dict)
    field_migration_note: str | None = None
    fields: list[AdminFormsSaveFieldRequest] = Field(default_factory=list)
    playbook_triggers: list[AdminFormsPlaybookTrigger] = Field(default_factory=list)


class AdminFormsSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    forms: list[AdminFormsSaveFormRequest] = Field(default_factory=list)
    publish: bool = True
    make_preferred: bool = True


class AdminFormsSaveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: AdminFormsSummary
    forms: list[AdminFormsFormItem] = Field(default_factory=list)
    message: str


class AdminFormsDraftSaveRequest(AdminFormsSaveRequest):
    base_version: str | None = None
    draft_id: str | None = None


class AdminFormsDraftSaveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    pack_key: str
    base_version: str | None = None
    status: str = "draft"
    summary: AdminFormsSummary
    published_version: str | None = None
    preferred_version: str | None = None
    message: str


class AdminFormsValidationReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    errors_count: int = 0
    warnings_count: int = 0
    can_publish: bool = True


class AdminFormsValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    path: str | None = None
    severity: str | None = None
    blocking: bool | None = None
    recommendation: str | None = None
    source: str | None = None


class AdminFormsValidateRequest(AdminFormsSaveRequest):
    base_version: str | None = None
    draft_id: str | None = None


class AdminFormsValidateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "validated"
    summary: AdminFormsValidationReportSummary
    errors: list[AdminFormsValidationIssue] = Field(default_factory=list)
    warnings: list[AdminFormsValidationIssue] = Field(default_factory=list)
    message: str


class AdminFormsPublishRequest(AdminFormsSaveRequest):
    base_version: str | None = None
    draft_id: str | None = None
    make_preferred: bool = True


class AdminFormsPublishResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: AdminFormsSummary
    forms: list[AdminFormsFormItem] = Field(default_factory=list)
    published_version: str
    preferred_version: str | None = None
    made_preferred: bool = True
    message: str


class AdminFormsPreferredUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str


class AdminFormsPreferredUpdateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack_key: str
    previous_version: str | None = None
    preferred_version: str
    message: str


class AdminFormsRoutePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form: AdminFormsSaveFormRequest
    form_payload: dict[str, Any] = Field(default_factory=dict)


class AdminFormsRoutePreviewMatchedRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    priority_order: int
    target_queue_id: int
    target_queue_name: str | None = None
    condition_json: dict | None = None


class AdminFormsRoutePreviewSummaryRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    value: str


class AdminFormsRoutePreviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_type: str
    request_kind: str
    target_queue_id: int | None = None
    target_queue_name: str | None = None
    fallback_applied: bool = False
    matched_rule: AdminFormsRoutePreviewMatchedRule | None = None
    summary_rows: list[AdminFormsRoutePreviewSummaryRow] = Field(default_factory=list)


class AdminFormsProcessPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form: AdminFormsSaveFormRequest
    form_payload: dict[str, Any] = Field(default_factory=dict)
    requester_context: dict[str, Any] = Field(default_factory=dict)
    device_context: dict[str, Any] = Field(default_factory=dict)
    draft_id: str | None = None
    base_version: str | None = None


class AdminFormsProcessPreviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_type: str
    request_kind: str
    priority: dict[str, Any] = Field(default_factory=dict)
    routing: dict[str, Any] = Field(default_factory=dict)
    sla: dict[str, Any] = Field(default_factory=dict)
    ola: dict[str, Any] = Field(default_factory=dict)
    approval: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    closure: dict[str, Any] = Field(default_factory=dict)
    visibility: dict[str, Any] = Field(default_factory=dict)
    notifications: dict[str, Any] = Field(default_factory=dict)
    summary_rows: list[AdminFormsRoutePreviewSummaryRow] = Field(default_factory=list)
    validation_report: dict[str, Any] = Field(default_factory=dict)
    preview_metadata: dict[str, Any] = Field(default_factory=dict)


class AdminHelpdeskPolicyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    table: str
    code: str
    version: str
    title: str
    description: str | None = None
    scope_level: str
    scope_ref: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    published_at: str | None = None
    created_at: str | None = None
    created_by: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None


class AdminHelpdeskRequestTemplateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_code: str
    version: str
    public_title: str
    internal_name: str | None = None
    description: str | None = None
    ticket_type: str
    category_id: int | None = None
    service_id: int | None = None
    subcategory_id: int | None = None
    form_schema_id: str | None = None
    workflow_profile_id: str | None = None
    priority_policy_code: str | None = None
    routing_policy_code: str | None = None
    sla_policy_id: int | None = None
    sla_policy_code: str | None = None
    ola_policy_code: str | None = None
    approval_policy_code: str | None = None
    diagnostic_policy_code: str | None = None
    closure_policy_code: str | None = None
    visibility_policy_code: str | None = None
    notification_policy_code: str | None = None
    reporting_policy_code: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    overrides: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    published_at: str | None = None
    created_at: str | None = None
    created_by: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None


class AdminHelpdeskTicketTypeItem(BaseModel):
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
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    published_at: str | None = None
    created_at: str | None = None
    created_by: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None


class AdminHelpdeskSmartViewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    version: str
    title: str
    description: str | None = None
    scope_level: str
    scope_ref: str | None = None
    filter: dict[str, Any] = Field(default_factory=dict)
    sort: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    is_active: bool = True
    published_at: str | None = None
    created_at: str | None = None
    created_by: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None


class AdminHelpdeskFormFieldItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    type: str
    required: bool = False
    options: list[dict[str, Any]] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    process_mapping: dict[str, Any] = Field(default_factory=dict)
    visibility: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0


class AdminHelpdeskFormConditionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition: dict[str, Any] = Field(default_factory=dict)
    show_fields: list[str] = Field(default_factory=list)
    require_fields: list[str] = Field(default_factory=list)
    sort_order: int = 0


class AdminHelpdeskFormSchemaItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_id: str
    version: str
    title: str
    description: str | None = None
    form_key: str | None = None
    request_template_code: str | None = None
    ticket_type: str | None = None
    fields: list[AdminHelpdeskFormFieldItem] = Field(default_factory=list)
    conditions: list[AdminHelpdeskFormConditionItem] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    published_at: str | None = None
    created_at: str | None = None
    created_by: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None


class AdminHelpdeskModelCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_endpoint: str
    publish_from_form_endpoint: str
    republish_legacy_forms_endpoint: str | None = None
    publish_policy_endpoint: str
    policy_diff_endpoint: str | None = None
    policy_deactivate_endpoint: str | None = None
    policy_rollback_endpoint: str | None = None
    publish_ticket_type_endpoint: str
    ticket_type_deactivate_endpoint: str | None = None
    ticket_type_rollback_endpoint: str | None = None
    publish_form_schema_endpoint: str
    publish_smart_view_endpoint: str
    inheritance_order: list[str]
    policy_kinds: list[str]


class AdminHelpdeskModelSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_templates_count: int
    active_request_templates_count: int
    ticket_types_count: int
    active_ticket_types_count: int
    form_schemas_count: int
    active_form_schemas_count: int
    policies_count: int
    active_policies_count: int
    smart_views_count: int
    active_smart_views_count: int
    data_quality_issue_count: int = 0


class AdminHelpdeskDataQualityItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_code: str
    severity: str
    issue_code: str
    field: str
    message: str
    remediation: str | None = None


class AdminHelpdeskModelPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: AdminHelpdeskModelSummary
    capabilities: AdminHelpdeskModelCapabilities
    request_templates: list[AdminHelpdeskRequestTemplateItem] = Field(default_factory=list)
    ticket_types: list[AdminHelpdeskTicketTypeItem] = Field(default_factory=list)
    form_schemas: list[AdminHelpdeskFormSchemaItem] = Field(default_factory=list)
    policies: dict[str, list[AdminHelpdeskPolicyItem]] = Field(default_factory=dict)
    smart_views: list[AdminHelpdeskSmartViewItem] = Field(default_factory=list)
    data_quality: list[AdminHelpdeskDataQualityItem] = Field(default_factory=list)


class AdminHelpdeskPublishFromFormRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form: AdminFormsSaveFormRequest
    publish_policies: bool = True


class AdminHelpdeskPublishFromFormResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_template: AdminHelpdeskRequestTemplateItem
    form_schema: AdminHelpdeskFormSchemaItem
    policies: dict[str, AdminHelpdeskPolicyItem] = Field(default_factory=dict)
    message: str


class AdminHelpdeskRepublishLegacyFormsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack_key: str = "request_forms"
    publish_policies: bool = True
    force: bool = False


class AdminHelpdeskRepublishLegacyFormsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack_key: str
    pack_version: str | None = None
    forms_seen_count: int
    published_templates_count: int
    skipped_unchanged_count: int
    failed_count: int


class AdminHelpdeskRepublishLegacyFormsItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_code: str
    status: str
    form_schema_id: str | None = None
    request_template_version: str | None = None
    published_policy_count: int = 0
    message: str | None = None


class AdminHelpdeskRepublishLegacyFormsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: AdminHelpdeskRepublishLegacyFormsSummary
    items: list[AdminHelpdeskRepublishLegacyFormsItem] = Field(default_factory=list)
    message: str


class AdminHelpdeskPublishFormSchemaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_id: str
    title: str
    description: str | None = None
    form_key: str | None = None
    request_template_code: str | None = None
    ticket_type: str | None = None
    fields: list[dict[str, Any]]
    field_roles: dict[str, list[str]] = Field(default_factory=dict)
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    requested_version: str | None = None


class AdminHelpdeskPublishFormSchemaResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form_schema: AdminHelpdeskFormSchemaItem
    message: str


class AdminHelpdeskPublishPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    code: str
    title: str
    description: str | None = None
    scope_level: str = "request_template"
    scope_ref: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    requested_version: str | None = None


class AdminHelpdeskPublishPolicyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: AdminHelpdeskPolicyItem
    message: str


class AdminHelpdeskPublishTicketTypeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
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
    feature_flags: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    requested_version: str | None = None


class AdminHelpdeskPublishTicketTypeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_type: AdminHelpdeskTicketTypeItem
    message: str


class AdminHelpdeskTicketTypeDeactivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    version: str


class AdminHelpdeskTicketTypeDeactivateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_type: AdminHelpdeskTicketTypeItem
    message: str


class AdminHelpdeskTicketTypeRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    target_version: str


class AdminHelpdeskTicketTypeRollbackResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_type: AdminHelpdeskTicketTypeItem
    message: str


class AdminHelpdeskPolicyDiffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    code: str
    from_version: str
    to_version: str


class AdminHelpdeskPolicyDiffResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    code: str
    from_policy: AdminHelpdeskPolicyItem = Field(alias="from")
    to_policy: AdminHelpdeskPolicyItem = Field(alias="to")
    changes: list[dict[str, Any]] = Field(default_factory=list)


class AdminHelpdeskPolicyDeactivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    code: str
    version: str


class AdminHelpdeskPolicyDeactivateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: AdminHelpdeskPolicyItem
    message: str


class AdminHelpdeskPolicyRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    code: str
    target_version: str


class AdminHelpdeskPolicyRollbackResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: AdminHelpdeskPolicyItem
    message: str


class AdminHelpdeskPublishSmartViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    title: str
    description: str | None = None
    scope_level: str = "system"
    scope_ref: str | None = None
    filter: dict[str, Any] = Field(default_factory=dict)
    sort: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    requested_version: str | None = None


class AdminHelpdeskPublishSmartViewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    smart_view: AdminHelpdeskSmartViewItem
    message: str


class AdminPlaybookBlockCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    tool: str | None = None
    tool_name: str | None = None
    capability_id: str | None = None
    execution_target: str | None = None
    provider_id: str | None = None
    block_type: str
    module_kind: str
    module_name: str | None = None
    description: str
    default_params: dict[str, Any] = Field(default_factory=dict)
    changes_device: bool = False
    requires_confirmation: bool = False
    requires_consent: bool = False
    output_contract: dict[str, Any] = Field(default_factory=dict)
    condition_hints: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None
    install_required: bool = False
    install_policy: str | None = None
    supported_platforms: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    min_agent_version: str | None = None
    risk_level: str | None = None
    params_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    presentation_schema: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    presets: list[dict[str, Any]] = Field(default_factory=list)
    error_codes: list[str] = Field(default_factory=list)


class AdminScenarioTemplateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    problem: str
    recommended_form_keys: list[str] = Field(default_factory=list)
    block_ids: list[str] = Field(default_factory=list)


class AdminPlaybookItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    domain: str | None = None
    version: str | None = None
    status: str
    blocks_count: int = 0
    updated_at: str | None = None


class AdminPlaybookBuilderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_endpoint: str
    save_endpoint: str
    block_types: list[AdminFilterOption] = Field(default_factory=list)
    module_kind_options: list[AdminFilterOption] = Field(default_factory=list)


class AdminPlaybookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: AdminPlaybookBuilderCapabilities
    block_catalog: list[AdminPlaybookBlockCatalogItem] = Field(default_factory=list)
    scenario_templates: list[AdminScenarioTemplateItem] = Field(default_factory=list)
    playbooks: list[AdminPlaybookItem] = Field(default_factory=list)


class AdminPlaybookDraftBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str = "diagnostic"
    module_kind: str = "diagnostic"
    tool: str | None = None
    capability_id: str | None = None
    execution_target: str | None = None
    provider_id: str | None = None
    label: str | None = None
    preset_id: str | None = None
    install_policy: str | None = "lazy"
    tool_manifest: dict[str, Any] | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    condition: str | None = None
    timeout_sec: int | None = None
    continue_on_error: bool = False
    parallel_group: str | None = None


class AdminPlaybookDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    domain: str | None = "diagnostics"
    version: str | None = None
    blocks: list[AdminPlaybookDraftBlock] = Field(default_factory=list)


class AdminPlaybookSaveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    version: str
    status: str
    blocks_count: int
    message: str


class AdminRolloutAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    channel: str
    version: str
    updated_at: str | None = None
    updated_by: str | None = None


class AdminDeviceUpdateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    label: str
    summary: str | None = None


class AdminBuildIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    channel: str
    version: str


class AdminDeviceUpdateRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    update_available: bool
    recommendation_source: str
    recommendation_source_label: str
    comparison: str
    comparison_label: str
    recommended_reason: str | None = None
    recommended_reason_label: str | None = None
    recommended_build: AdminBuildIdentity | None = None
    assigned_rollout: AdminRolloutAssignment | None = None


class AdminDeviceUpdateAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    label: str
    reason_required: bool
    endpoint: str


class AdminDeviceUpdatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    device_label: str
    online: bool
    target: str | None = None
    current_version: str | None = None
    release_channel: str
    is_release: bool
    summary: AdminDeviceUpdateSummary
    recommendation: AdminDeviceUpdateRecommendation
    action: AdminDeviceUpdateAction


class AdminDeviceUpdateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    restart_delay_sec: int | None = None


class AdminDeviceUpdateRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    operation_id: str
    status: str
    message: str
    build_source: str
    poll_url: str
    build: AdminBuildIdentity


class AdminDeviceInventoryHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    collected_at: str
    status: str
    summary: str | None = None


class AdminDeviceInventoryLatestSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_tool: str
    collected_at: str
    status: str
    summary: str | None = None
    result: dict[str, Any]
    presentation_schema: dict[str, Any] = Field(default_factory=dict)
    effective_presentation_schema: dict[str, Any] = Field(default_factory=dict)
    presentation_schema_source: str = "none"
    device_card_slots: list[str] = Field(default_factory=list)


class AdminDeviceInventoryBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    person_id: str | None = None
    asset_id: str | None = None
    source_binding_id: str | None = None
    registration_status: str | None = None
    building: str | None = None
    floor: str | None = None
    room: str | None = None
    department: str | None = None
    responsible_user: str | None = None
    responsible_user_login: str | None = None
    inventory_number: str | None = None
    status: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None


class AdminDeviceInventoryBindingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    building: str | None = None
    floor: str | None = None
    room: str | None = None
    department: str | None = None
    responsible_user: str | None = None
    responsible_user_login: str | None = None
    inventory_number: str | None = None
    status: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class AdminDeviceInventoryBindingHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changed_at: str
    changed_by: str | None = None
    changed_fields: list[str] = Field(default_factory=list)
    old_binding: dict[str, Any] | None = None
    new_binding: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


class AdminDeviceInventoryRefreshPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    scope: str
    device_id: str | None = None
    enabled: bool
    interval_minutes: int
    jitter_minutes: int
    last_requested_at: str | None = None
    next_due_at: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None


class AdminDeviceInventoryRefreshPolicyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    interval_minutes: int = 1440
    jitter_minutes: int = 30


class AdminDeviceInventoryRefreshRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    device_id: str | None = None
    policy_id: str | None = None
    bulk_operation_id: str | None = None
    requested_at: str
    requested_by: str | None = None
    status: str
    job_id: str | None = None
    error: str | None = None
    completed_at: str | None = None


class AdminDeviceProfileItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requester_id: str | None = None
    display_name: str | None = None
    full_name: str | None = None
    department: str | None = None
    building: str | None = None
    floor: str | None = None
    room: str | None = None
    phone: str | None = None
    email: str | None = None
    active: bool = False
    last_seen_at: str | None = None
    source: str = "agent_profile"
    status: str = "observed"


class AdminBindingSuggestionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    device_id: str
    source: str
    source_ref: str | None = None
    suggested_binding: dict[str, Any] = Field(default_factory=dict)
    profile_snapshot: dict[str, Any] = Field(default_factory=dict)
    status: str
    confidence: str | None = None
    created_at: str
    updated_at: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_note: str | None = None


class AdminBindingSuggestionApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[str] = Field(default_factory=list)
    reason: str | None = None


class AdminBindingSuggestionReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


class AdminPresenceSnapshotItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    collected_at: str
    received_at: str | None = None
    session_state: str | None = None
    current_user: str | None = None
    idle_seconds: int | None = None
    locked: bool | None = None
    result: dict[str, Any] | None = None


class AdminPresenceDailySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    active_seconds: int = 0
    idle_seconds: int = 0
    locked_seconds: int = 0
    offline_seconds: int = 0
    unknown_seconds: int = 0
    updated_at: str | None = None


class AdminDevicePresencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    latest: AdminPresenceSnapshotItem | None = None
    today: AdminPresenceDailySummary | None = None
    history: list[AdminPresenceSnapshotItem] = Field(default_factory=list)


class AdminDeviceInventoryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    latest_snapshot: AdminDeviceInventoryLatestSnapshot | None = None
    history: list[AdminDeviceInventoryHistoryItem] = Field(default_factory=list)
    binding: AdminDeviceInventoryBinding | None = None
    binding_history: list[AdminDeviceInventoryBindingHistoryItem] = Field(default_factory=list)
    refresh_policy: AdminDeviceInventoryRefreshPolicy | None = None
    refresh_runs: list[AdminDeviceInventoryRefreshRun] = Field(default_factory=list)
    last_refresh_run: AdminDeviceInventoryRefreshRun | None = None
    profiles: list[AdminDeviceProfileItem] = Field(default_factory=list)
    binding_suggestions: list[AdminBindingSuggestionItem] = Field(default_factory=list)
    presence: AdminDevicePresencePayload | None = None


class AdminInventoryBindingImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    csv_text: str
    dry_run: bool = True
    reason: str | None = None


class AdminInventoryBindingImportChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row: int
    device_id: str | None = None
    hostname: str | None = None
    action: str
    changed_fields: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AdminInventoryBindingImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool
    total_rows: int
    valid_rows: int
    error_rows: int
    changes: list[AdminInventoryBindingImportChange] = Field(default_factory=list)


class AdminInventoryDashboardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    totals: dict[str, Any] = Field(default_factory=dict)
    freshness: dict[str, Any] = Field(default_factory=dict)
    by_os: list[dict[str, Any]] = Field(default_factory=list)
    by_building: list[dict[str, Any]] = Field(default_factory=list)
    by_department: list[dict[str, Any]] = Field(default_factory=list)
    binding_gaps: dict[str, Any] = Field(default_factory=dict)
    health: dict[str, Any] = Field(default_factory=dict)
    refresh: dict[str, Any] = Field(default_factory=dict)
    attention: dict[str, Any] = Field(default_factory=dict)


class AdminDeviceInventoryCollectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    tool_name: str
    operation_id: str | None = None
    status: str
    message: str
    poll_url: str | None = None


class AdminBulkRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_ids: list[str] = Field(default_factory=list)
    mode: str = "selected"
    filters: dict[str, Any] = Field(default_factory=dict)
    wave: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True


class AdminBulkRefreshItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    device_id: str
    hostname: str | None = None
    online: bool | None = None
    status: str
    reason: str | None = None


class AdminBulkRefreshResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool
    selected_count: int
    online_count: int
    offline_count: int
    estimated_waves: int
    operation_id: str | None = None
    status: str | None = None
    items: list[AdminBulkRefreshItem] = Field(default_factory=list)


class AdminBulkOperationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    operation_id: str
    device_id: str
    wave_index: int
    status: str
    job_id: str | None = None
    error: str | None = None
    requested_at: str | None = None


class AdminBulkOperationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    operation_type: str
    status: str
    requested_by: str | None = None
    requested_at: str
    filters: dict[str, Any] = Field(default_factory=dict)
    wave: dict[str, Any] = Field(default_factory=dict)
    total_count: int = 0
    dispatched_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    completed_at: str | None = None


class AdminBulkOperationsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AdminBulkOperationSummary] = Field(default_factory=list)


class AdminDeviceIdentitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    machine_id: str
    install_id: str | None = None
    machine_id_source: str | None = None
    identity_scheme: str | None = None
    source_label: str
    is_stable: bool


class AdminDeviceDuplicateWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    severity: str
    title: str
    description: str
    duplicate_count: int
    cleanup_available: bool


class AdminDeviceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    hostname: str | None = None
    os: str | None = None
    agent_version: str | None = None
    target: str | None = None
    online: bool
    last_seen_at: str | None = None
    connection_status_label: str
    latest_update: AdminDeviceUpdateSummary
    identity_summary: AdminDeviceIdentitySummary
    duplicate_warning: AdminDeviceDuplicateWarning | None = None


class AdminDevicesSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible_count: int
    online_count: int
    rollout_targets: int
    duplicate_hosts: int = 0
    cleanup_candidates: int = 0


class AdminDevicesFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_options: list[AdminFilterOption]


class AdminDevicesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    status_filter: str
    summary: AdminDevicesSummary
    filters: AdminDevicesFilters
    rollout: list[AdminRolloutAssignment]
    devices: list[AdminDeviceItem]


class AdminDeviceCleanupCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    hostname: str | None = None
    agent_version: str | None = None
    last_seen_at: str | None = None
    machine_id_source: str | None = None
    online: bool


class AdminDeviceCleanupPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str
    applied: bool
    archived_count: int
    candidates: list[AdminDeviceCleanupCandidate]
    kept_device_ids: list[str]


class AdminDeviceTokenItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token_hash: str
    token_prefix: str | None = None
    created_at: str | None = None
    expires_at: str | None = None
    revoked_at: str | None = None
    last_used_at: str | None = None
    is_active: bool


class AdminAgentTokenItem(AdminDeviceTokenItem):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    hostname: str | None = None
    online: bool


class AdminDeviceTokensSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    active_count: int
    revoked_count: int


class AdminDeviceTokensPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    summary: AdminDeviceTokensSummary
    tokens: list[AdminDeviceTokenItem]


class AdminAgentTokensPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    status_filter: str
    summary: AdminDeviceTokensSummary
    tokens: list[AdminAgentTokenItem]


class AdminModulesSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible_count: int
    preferred_count: int
    invalid_count: int
    missing_files_count: int


class AdminModulesRolloutSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_version_rollout_mode: str
    preferred_version_rollout_mode_label: str
    sync_after_preferred_change: bool


class AdminModulesRolloutSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_version_rollout_mode: str | None = None
    sync_after_preferred_change: bool | None = None


class AdminModuleVersionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    created_at: str | None = None
    uploaded_by: str | None = None
    manifest_version: int | None = None
    module_api_version: str | None = None
    owner_scope: str | None = None
    validation_status: str
    validation_status_label: str
    preflight_status: str
    preflight_status_label: str
    is_preferred: bool = False
    tools_count: int = 0
    platforms: list[str] = Field(default_factory=list)
    tool_ids: list[str] = Field(default_factory=list)
    warnings_count: int = 0
    file_exists: bool = True


class AdminModuleFamilyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_name: str
    preferred_version: str | None = None
    preferred_assigned: bool = False
    latest_version: str | None = None
    owner_scope: str | None = None
    module_api_version: str | None = None
    validation_status: str
    validation_status_label: str
    version_count: int = 0
    tools_count: int = 0
    platforms: list[str] = Field(default_factory=list)
    tool_ids: list[str] = Field(default_factory=list)
    warnings_count: int = 0
    has_missing_files: bool = False
    versions: list[AdminModuleVersionItem] = Field(default_factory=list)


class AdminModulesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    summary: AdminModulesSummary
    rollout_settings: AdminModulesRolloutSettings
    modules: list[AdminModuleFamilyItem]


class AdminModulePreferredVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str | None = None


class AdminModulePreferredRolloutSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    should_sync: bool
    desired_updates: int
    sync_enqueued: int
    refresh_enqueued: int = 0


class AdminModulePreferredVersionActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_name: str
    preferred_version: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None
    message: str
    rollout_summary: AdminModulePreferredRolloutSummary | None = None
