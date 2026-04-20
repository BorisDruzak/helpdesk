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


class AdminFilterOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


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


class AdminDevicesSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible_count: int
    online_count: int
    rollout_targets: int


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
