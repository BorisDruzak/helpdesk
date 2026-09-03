from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DeviceOperationsDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    hostname: str | None = None
    display_name: str | None = None
    platform: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    arch: str | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    source: str | None = None
    status: str | None = None


class DeviceOperationsBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    responsible_person: str | None = None
    department: str | None = None
    building: str | None = None
    room: str | None = None
    inventory_number: str | None = None
    status: str | None = None
    tags: list[str] = Field(default_factory=list)
    updated_at: str | None = None
    updated_by: str | None = None


class DeviceOperationsAgent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connection_state: str
    last_seen_at: str | None = None
    version: str | None = None
    protocol: str | None = None
    capabilities_count: int | None = None
    toolset_hash: str | None = None
    desired_revision: str | None = None
    current_revision: str | None = None
    config_status: str | None = None
    update_status: str | None = None
    update_available: bool | None = None
    pending_restart: bool | None = None


class DeviceOperationsProvisioning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str | None = None
    auth_state: str | None = None
    last_error: str | None = None
    last_error_at: str | None = None
    token_status: str | None = None
    connection_request_id: str | None = None
    can_approve: bool = False
    can_reject: bool = False


class DeviceOperationsRefreshPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    interval_minutes: int | None = None
    next_due_at: str | None = None


class DeviceOperationsRefreshRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    status: str | None = None
    requested_at: str | None = None
    completed_at: str | None = None
    error_summary: str | None = None


class DeviceOperationsInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latest_snapshot_id: str | None = None
    collected_at: str | None = None
    age_seconds: int | None = None
    freshness: Literal["fresh", "stale", "missing", "unknown"] | str
    summary: dict[str, Any] | str | None = None
    presentation: dict[str, Any] | None = None
    refresh_policy: DeviceOperationsRefreshPolicy | None = None
    latest_refresh_run: DeviceOperationsRefreshRun | None = None
    can_request_refresh: bool


class DeviceOperationsModuleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_id: str
    name: str | None = None
    installed_version: str | None = None
    desired_version: str | None = None
    state: str | None = None
    last_error: str | None = None
    last_seen_at: str | None = None


class DeviceOperationsModules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reconcile_state: str | None = None
    module_count: int | None = None
    missing_count: int | None = None
    outdated_count: int | None = None
    failed_count: int | None = None
    items: list[DeviceOperationsModuleItem] = Field(default_factory=list)


class DeviceOperationsOutboxItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    command_type: str | None = None
    status: str | None = None
    created_at: str | None = None
    sent_at: str | None = None
    ack_at: str | None = None
    error_summary: str | None = None
    ticket_id: str | None = None
    operation_id: str | None = None


class DeviceOperationsOutbox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending_count: int
    failed_count: int
    last_ack_at: str | None = None
    items: list[DeviceOperationsOutboxItem] = Field(default_factory=list)


class DeviceOperationsOperationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ticket_id: str | None = None
    tool_name: str | None = None
    status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    error_summary: str | None = None
    trace_id: str | None = None


class DeviceOperationsOperations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recent_failed_count: int
    recent_running_count: int
    items: list[DeviceOperationsOperationItem] = Field(default_factory=list)


class DeviceOperationsObserverItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    title: str | None = None
    status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    ticket_id: str | None = None
    operation_id: str | None = None
    root_span: str | None = None
    error_summary: str | None = None


class DeviceOperationsIntegrityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    severity: str
    status: str
    last_seen_at: str | None = None
    operation_id: str | None = None
    ticket_id: str | None = None
    device_outbox_id: int | None = None
    expected: str | None = None
    actual: str | None = None
    runbook: str | None = None


class DeviceOperationsObserver(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_count: int | None = None
    latest_trace_at: str | None = None
    items: list[DeviceOperationsObserverItem] = Field(default_factory=list)
    active_integrity_count: int = 0
    critical_integrity_count: int = 0
    integrity_events: list[DeviceOperationsIntegrityEvent] = Field(default_factory=list)


class DeviceOperationsSignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_offline: bool
    stale_inventory: bool
    missing_inventory: bool
    update_available: bool
    provisioning_error: bool
    auth_error: bool
    module_reconcile_failed: bool
    outbox_backlog: bool
    failed_recent_operation: bool
    observer_errors: bool


class DeviceOperationsLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory: str | None = None
    device_card: str | None = None
    modules: str | None = None
    observer: str | None = None
    tickets: str | None = None


class DeviceOperationsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str
    device: DeviceOperationsDevice
    binding: DeviceOperationsBinding | None = None
    agent: DeviceOperationsAgent
    provisioning: DeviceOperationsProvisioning | None = None
    inventory: DeviceOperationsInventory
    modules: DeviceOperationsModules
    outbox: DeviceOperationsOutbox
    operations: DeviceOperationsOperations
    observer: DeviceOperationsObserver
    signals: DeviceOperationsSignals
    links: DeviceOperationsLinks
