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
    device_id: str | None = None
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
    device_id: str | None = None
    operation_id: str | None = None
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


class AdminObserverTraceDetailPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace: AdminObserverTraceItem
    summary: AdminObserverTraceDetailSummary
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


class AdminFormsFormItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    request_kind: str
    title: str
    description: str | None = None
    fields: list[AdminFormsFieldItem] = Field(default_factory=list)


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
    field_type_options: list[AdminFilterOption]


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


class AdminFormsSaveFormRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    request_kind: str
    title: str
    description: str | None = None
    fields: list[AdminFormsSaveFieldRequest] = Field(default_factory=list)


class AdminFormsSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    forms: list[AdminFormsSaveFormRequest] = Field(default_factory=list)


class AdminFormsSaveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: AdminFormsSummary
    forms: list[AdminFormsFormItem] = Field(default_factory=list)
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
