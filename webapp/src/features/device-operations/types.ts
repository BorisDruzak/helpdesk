export type DeviceOperationsPayload = {
  generated_at: string;
  device: {
    device_id: string;
    hostname?: string | null;
    display_name?: string | null;
    platform?: string | null;
    os_name?: string | null;
    os_version?: string | null;
    arch?: string | null;
    first_seen_at?: string | null;
    last_seen_at?: string | null;
    source?: string | null;
    status?: string | null;
  };
  binding?: {
    responsible_person?: string | null;
    department?: string | null;
    building?: string | null;
    room?: string | null;
    inventory_number?: string | null;
    status?: string | null;
    tags?: string[];
    updated_at?: string | null;
    updated_by?: string | null;
  } | null;
  agent: {
    connection_state: string;
    last_seen_at?: string | null;
    version?: string | null;
    protocol?: string | null;
    capabilities_count?: number | null;
    toolset_hash?: string | null;
    desired_revision?: string | null;
    current_revision?: string | null;
    config_status?: string | null;
    update_status?: string | null;
    update_available?: boolean | null;
    pending_restart?: boolean | null;
  };
  provisioning?: {
    state?: string | null;
    auth_state?: string | null;
    last_error?: string | null;
    last_error_at?: string | null;
    token_status?: string | null;
    connection_request_id?: string | null;
    can_approve?: boolean;
    can_reject?: boolean;
  } | null;
  inventory: {
    latest_snapshot_id?: string | null;
    collected_at?: string | null;
    age_seconds?: number | null;
    freshness: "fresh" | "stale" | "missing" | "unknown" | string;
    summary?: Record<string, unknown> | string | null;
    presentation?: Record<string, unknown> | null;
    refresh_policy?: {
      enabled?: boolean | null;
      interval_minutes?: number | null;
      next_due_at?: string | null;
    } | null;
    latest_refresh_run?: {
      id?: string | null;
      status?: string | null;
      requested_at?: string | null;
      completed_at?: string | null;
      error_summary?: string | null;
    } | null;
    can_request_refresh: boolean;
  };
  modules: {
    reconcile_state?: string | null;
    module_count?: number | null;
    missing_count?: number | null;
    outdated_count?: number | null;
    failed_count?: number | null;
    items: Array<{
      module_id: string;
      name?: string | null;
      installed_version?: string | null;
      desired_version?: string | null;
      state?: string | null;
      last_error?: string | null;
      last_seen_at?: string | null;
    }>;
  };
  outbox: {
    pending_count: number;
    failed_count: number;
    last_ack_at?: string | null;
    items: Array<{
      id: string;
      command_type?: string | null;
      status?: string | null;
      created_at?: string | null;
      sent_at?: string | null;
      ack_at?: string | null;
      error_summary?: string | null;
      ticket_id?: string | null;
      operation_id?: string | null;
    }>;
  };
  operations: {
    recent_failed_count: number;
    recent_running_count: number;
    items: Array<{
      id: string;
      ticket_id?: string | null;
      tool_name?: string | null;
      status?: string | null;
      started_at?: string | null;
      finished_at?: string | null;
      duration_ms?: number | null;
      error_summary?: string | null;
      trace_id?: string | null;
    }>;
  };
  observer: {
    trace_count?: number | null;
    latest_trace_at?: string | null;
    items: Array<{
      trace_id: string;
      title?: string | null;
      status?: string | null;
      started_at?: string | null;
      finished_at?: string | null;
      ticket_id?: string | null;
      operation_id?: string | null;
      root_span?: string | null;
      error_summary?: string | null;
    }>;
    active_integrity_count?: number;
    critical_integrity_count?: number;
    integrity_events?: Array<{
      event_id: string;
      event_type: string;
      severity: string;
      status: string;
      last_seen_at?: string | null;
      operation_id?: string | null;
      ticket_id?: string | null;
      device_outbox_id?: number | null;
      expected?: string | null;
      actual?: string | null;
      runbook?: string | null;
    }>;
  };
  remote_assist: {
    availability: "available" | "unavailable" | "requires_consent" | "offline" | "unknown" | string;
    reason?: string | null;
    active_session_id?: string | null;
    pending_consent_id?: string | null;
    last_session_at?: string | null;
    can_request: boolean;
  };
  signals: {
    agent_offline: boolean;
    stale_inventory: boolean;
    missing_inventory: boolean;
    update_available: boolean;
    provisioning_error: boolean;
    auth_error: boolean;
    module_reconcile_failed: boolean;
    outbox_backlog: boolean;
    failed_recent_operation: boolean;
    observer_errors: boolean;
    remote_assist_unavailable: boolean;
  };
  links: {
    inventory?: string | null;
    device_card?: string | null;
    modules?: string | null;
    observer?: string | null;
    tickets?: string | null;
    remote_assist?: string | null;
  };
};

export type FetchDeviceOperationsParams = {
  include_traces?: boolean;
  include_outbox?: boolean;
  include_history?: boolean;
  trace_limit?: number;
  outbox_limit?: number;
  operation_limit?: number;
};
