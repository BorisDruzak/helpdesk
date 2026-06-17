export type SupportBootstrapPayload = {
  workspace: string;
  features: string[];
  observer: {
    ticket_summary_endpoint: string;
    drawer_tab: string;
  };
};

export type SupportQueueScope = "all" | "mine";

export type SupportFilterOption = {
  value: string;
  label: string;
};

export type SupportCountItem = {
  value: string;
  label: string;
  count: number;
};

export type SupportQueueCountItem = {
  id: number | null;
  code: string | null;
  name: string | null;
  count: number;
};

export type SupportQueuePayload = {
  scope: SupportQueueScope;
  query: string;
  status_filter: string;
  smart_view: string;
  summary: {
    visible_count: number;
    selected_ticket_id: string | null;
    scope_counts: SupportCountItem[];
    status_counts: SupportCountItem[];
    smart_view_counts: SupportCountItem[];
    queue_counts: SupportQueueCountItem[];
  };
  filters: {
    scope_options: SupportFilterOption[];
    status_options: SupportFilterOption[];
    smart_view_options: SupportFilterOption[];
  };
  tickets: Array<{
    ticket_id: string;
    ticket_code: string | null;
    title: string;
    status: string;
    status_label: string;
    requester_status?: string;
    requester_status_label?: string;
    next_action_owner?: string | null;
    next_action_due_at?: string | null;
    first_response_at?: string | null;
    first_response_due_at?: string | null;
    resolution_due_at?: string | null;
    status_reason?: string | null;
    priority?: string | null;
    priority_class?: string | null;
    queue_code: string | null;
    assignee_id: string | null;
    assignee_display_name?: string | null;
    requester_display_name: string | null;
    requester_registration_status?: string | null;
    requester_account_session_id?: string | null;
    requester_account_mode?: string | null;
    requester_account_context?: Record<string, unknown> | null;
    ticket_context?: Record<string, unknown> | null;
    requester_account_warning?: string | null;
    device_id: string | null;
    updated_at: string | null;
    created_at: string | null;
    hidden_from_workspace?: boolean;
    hidden_at?: string | null;
    hidden_by?: string | null;
    hidden_reason?: string | null;
    archived_at?: string | null;
    archived_by?: string | null;
    archive_reason?: string | null;
    requires_operator_action: boolean;
    unread_user_messages: number;
  }>;
};

export type SupportWorkspaceSummaryPayload = {
  views: {
    needs_action: number;
    sla_risk: number;
    unassigned: number;
    requester_replied: number;
    [key: string]: number;
  };
  queues: Array<{
    id: string;
    code: string | null;
    name: string;
    count: number;
  }>;
  smart_view_counts: SupportCountItem[];
  smart_view_options: SupportFilterOption[];
};

export type SupportQueueMassAction = "assign_self" | "assign" | "change_queue" | "change_priority" | "internal_note" | "run_diagnostics" | "link_mass_problem";

export type SupportQueueMassActionRequest = {
  action: SupportQueueMassAction;
  ticket_ids: string[];
  reason?: string | null;
  comment?: string | null;
  assignee_id?: string | null;
  queue_id?: number | null;
  priority?: string | null;
  internal_note?: string | null;
  tool_name?: string | null;
  preset_id?: string | null;
  params?: Record<string, unknown>;
  mass_problem_key?: string | null;
};

export type SupportQueueMassActionResult = {
  action: SupportQueueMassAction;
  requested_count: number;
  success_count: number;
  skipped_count: number;
  error_count: number;
  results: Array<{
    ticket_id: string;
    ticket_code: string | null;
    status: "success" | "skipped" | "error";
    action: string;
    message: string;
    result?: unknown;
  }>;
};

export type SupportQueueSavedViewScope = "personal" | "queue" | "global";

export type SupportQueueSavedViewItem = {
  id: string;
  name: string;
  scope: SupportQueueSavedViewScope;
  owner_actor_id: string | null;
  queue_id: number | null;
  filters: Record<string, unknown>;
  columns: string[];
  sort: Array<Record<string, unknown>>;
  is_favorite: boolean;
  is_default: boolean;
  created_at: string | null;
  updated_at: string | null;
  created_by: string | null;
  updated_by: string | null;
};

export type SupportQueueSavedViewsPayload = {
  views: SupportQueueSavedViewItem[];
  default_view_id: string | null;
  default_columns: string[];
};

export type SupportQueueSavedViewUpsertRequest = {
  name: string;
  scope: SupportQueueSavedViewScope;
  queue_id?: number | null;
  filters: Record<string, unknown>;
  columns: string[];
  sort?: Array<Record<string, unknown>>;
  is_favorite?: boolean;
  is_default?: boolean;
};

export type SupportQueueSavedViewDeletePayload = {
  deleted: boolean;
  id: string;
};

export type CustomerHistoryEvent = {
  event_id?: string;
  source: string;
  group: string;
  event_type: string;
  title: string;
  summary?: string | null;
  occurred_at?: string | null;
  ticket_ref?: string | null;
  payload?: Record<string, unknown>;
  refs?: Record<string, unknown>;
};

export type CustomerHistoryPayload = {
  ticket_id?: string;
  ticket_ref?: string | null;
  person_id?: string | null;
  events: CustomerHistoryEvent[];
  count: number;
  redaction_report?: {
    removed_count?: number;
    role?: string;
  };
  sources?: string[];
};

export type CustomerHistoryContextPack = {
  mode: string;
  preview_only: boolean;
  llm_api_called: boolean;
  ticket_ref?: string | null;
  events: CustomerHistoryEvent[];
  redaction_report?: {
    removed_count?: number;
    role?: string;
  };
  sources?: string[];
};

export type SupportTicketDetailPayload = {
  ticket: {
    ticket_id: string;
    ticket_code: string | null;
    title: string;
    description: string | null;
    status: string;
    status_label: string;
    requester_status?: string;
    requester_status_label?: string;
    next_action_owner?: string | null;
    next_action_due_at?: string | null;
    status_reason?: string | null;
    requester_display_name: string | null;
    requester_registration_status?: string | null;
    requester_account_session_id?: string | null;
    requester_account_mode?: string | null;
    requester_account_context?: Record<string, unknown> | null;
    ticket_context?: Record<string, unknown> | null;
    requester_account_warning?: string | null;
    device_id: string | null;
    ticket_type?: string | null;
    category_id?: number | null;
    service_id?: number | null;
    subcategory_id?: number | null;
    priority?: string | null;
    priority_class?: string | null;
    impact?: number | null;
    urgency?: number | null;
    importance?: number | null;
    priority_decision?: Record<string, unknown>;
    first_response_at?: string | null;
    first_response_due_at?: string | null;
    resolution_due_at?: string | null;
    queue: {
      id: number | null;
      code: string | null;
      name: string | null;
    };
    assignee_id: string | null;
    updated_at: string | null;
    created_at: string | null;
    hidden_from_workspace?: boolean;
    hidden_at?: string | null;
    hidden_by?: string | null;
    hidden_reason?: string | null;
    archived_at?: string | null;
    archived_by?: string | null;
    archive_reason?: string | null;
    resolution_code?: string | null;
    resolution_summary?: string | null;
    requester_resolution_summary?: string | null;
    evidence_required?: boolean;
    evidence_ref?: string | null;
    closure_feedback?: Record<string, unknown>;
    approval_summary?: {
      required: boolean;
      status: string;
      approval_mode: string;
      approver_source: string | null;
      current_action_owner: string | null;
      require_comment_on_reject: boolean;
      waiting_status: string | null;
      approved_transition: string | null;
      rejected_transition: string | null;
      due_in: string | null;
      reminder_after: string | null;
      escalate_after: string | null;
      pending_count: number;
      approved_count: number;
      rejected_count: number;
      timed_out_count: number;
      items: Array<{
        id: number;
        approval_type: string;
        approver_id: string | null;
        status: string;
        reason: string | null;
        requested_by: string | null;
        requested_at: string | null;
        decided_at: string | null;
        due_at: string | null;
        reminder_at: string | null;
        escalation_at: string | null;
        reminded_at: string | null;
        escalated_at: string | null;
        timed_out_at: string | null;
        current: boolean;
      }>;
    } | null;
    queue_members: Array<{
      actor_id: string;
      role_in_queue: string | null;
    }>;
  };
  request_form: {
    request_kind: string | null;
    form_key: string | null;
    form_title: string | null;
    rows: Array<{
      key: string;
      label: string;
      value: string;
    }>;
  } | null;
  observer: {
    ticket_summary_endpoint: string;
    summary: {
      ticket_id: string;
      root_trace_id?: string | null;
      root_trace_url?: string | null;
      root_trace_status?: string | null;
      root_kind?: string | null;
      trace_count: number;
      active_trace_count: number;
      error_trace_count: number;
      signature_count: number;
      latest_trace_at?: string | null;
      latest_error_at?: string | null;
      latest_error_label?: string | null;
      latest_error_stage?: string | null;
      top_signature?: {
        error_signature?: string | null;
        title?: string | null;
        severity?: string | null;
        ticket_occurrences_count: number;
        global_occurrences_count?: number | null;
        last_seen_at?: string | null;
      } | null;
      has_active_operation?: boolean;
      health_label?: string;
    };
    root_trace?: {
      trace_id: string;
      root_kind?: string | null;
      status?: string | null;
      title?: string | null;
      started_at?: string | null;
      finished_at?: string | null;
      error_count: number;
      operation_id?: string | null;
      tool_name?: string | null;
      playbook_id?: string | null;
      trace_url?: string | null;
    } | null;
    related_traces?: Array<{
      trace_id: string;
      root_kind?: string | null;
      status?: string | null;
      title?: string | null;
      started_at?: string | null;
      finished_at?: string | null;
      error_count: number;
      operation_id?: string | null;
      tool_name?: string | null;
      playbook_id?: string | null;
      trace_url?: string | null;
    }>;
    active_traces?: Array<{
      trace_id: string;
      root_kind?: string | null;
      status?: string | null;
      title?: string | null;
      started_at?: string | null;
      finished_at?: string | null;
      error_count: number;
      operation_id?: string | null;
      tool_name?: string | null;
      playbook_id?: string | null;
      trace_url?: string | null;
    }>;
    error_traces?: Array<{
      trace_id: string;
      root_kind?: string | null;
      status?: string | null;
      title?: string | null;
      started_at?: string | null;
      finished_at?: string | null;
      error_count: number;
      operation_id?: string | null;
      tool_name?: string | null;
      playbook_id?: string | null;
      trace_url?: string | null;
    }>;
    signatures?: Array<{
      error_signature?: string | null;
      title?: string | null;
      severity?: string | null;
      ticket_occurrences_count: number;
      global_occurrences_count?: number | null;
      last_seen_at?: string | null;
    }>;
    recent_occurrences?: Array<{
      error_signature?: string | null;
      message?: string | null;
      stage?: string | null;
      severity?: string | null;
      trace_id?: string | null;
      created_at?: string | null;
      trace_url?: string | null;
    }>;
  };
  timeline: Array<{
    message_id: string | null;
    event_id: number | null;
    event_type: string;
    event_category?: string | null;
    event_label?: string | null;
    event_details?: Record<string, unknown>;
    requester_timeline_text?: string | null;
    requester_timeline_kind?: string | null;
    requester_timeline_payload?: Record<string, unknown> | null;
    requester_timeline_icon?: string | null;
    requester_timeline_style?: string | null;
    from_role: string;
    sender_display_name?: string | null;
    text: string;
    ts: string | null;
    visibility: string;
    direction: string;
    attachments: Array<Record<string, unknown>>;
    reply_to: {
      parent_message_id?: string | null;
      preview?: string | null;
      sender_role?: string | null;
      sender_display_name?: string | null;
      ts?: string | null;
    } | null;
    tool_name?: string | null;
    tool_status?: string | null;
    result_summary?: string | null;
    result_preview?: string | null;
    result_payload?: unknown;
    result_presentation_schema?: Record<string, unknown> | null;
    result_presentation_schema_source?: string | null;
    operation_id?: string | null;
    trace_id?: string | null;
    duration_ms?: number | null;
    retry_count?: number | null;
    max_retries?: number | null;
    retryable?: boolean | null;
    can_retry?: boolean | null;
    can_cancel?: boolean | null;
    retry_url?: string | null;
    cancel_url?: string | null;
    retry_disabled_reason?: string | null;
    cancel_disabled_reason?: string | null;
    error_code?: string | null;
    error_category?: string | null;
    details_url?: string | null;
    operation_steps?: Array<{
      name: string;
      status: string;
      value: string;
      details?: string | null;
    }>;
  }>;
  snapshot: {
    last_event_id: number;
    notification_unread: number;
    presence: {
      requester_online: boolean;
      support_online: boolean;
      agent_online: boolean;
    };
    device: {
      device_id: string | null;
      hostname: string | null;
      os: string | null;
      agent_version: string | null;
      last_seen_at: string | null;
      online: boolean;
    };
    registry?: {
      person_id: string | null;
      person_display_name: string | null;
      person_phone?: string | null;
      person_email?: string | null;
      person_source?: string | null;
      department_id: string | null;
      department_name: string | null;
      location_id: string | null;
      location_display_name: string | null;
      building: string | null;
      floor?: string | null;
      room: string | null;
      asset_id: string | null;
      asset_name: string | null;
      asset_type: string | null;
      service_id: string | null;
      service_name: string | null;
      service_owner_queue_id?: number | null;
      service_owner_queue_name?: string | null;
      service_source?: string | null;
    } | null;
    latest_operations: Array<{
      operation_id: string;
      kind: string;
      status: string;
      display_status?: string | null;
      display_label?: string | null;
      scope?: "ticket" | "playbook" | "device" | string;
      tool_name: string | null;
      command_name: string | null;
      queued_at: string | null;
      started_at?: string | null;
      finished_at: string | null;
      duration_ms?: number | null;
      trace_id?: string | null;
      retry_count?: number;
      max_retries?: number;
      retryable?: boolean;
      can_retry?: boolean;
      can_cancel?: boolean;
      retry_url?: string | null;
      cancel_url?: string | null;
      retry_disabled_reason?: string | null;
      cancel_disabled_reason?: string | null;
      policy_labels?: string[];
      error_code?: string | null;
      error_category?: string | null;
      details_url?: string | null;
      result_summary: string | null;
      error_message: string | null;
      trace_relation?: string | null;
      root_trace_id?: string | null;
      root_trace_url?: string | null;
      trace_url?: string | null;
      retry_of_operation_id?: string | null;
      retry_source_trace_id?: string | null;
    }>;
  };
  actions: {
    status_options: Array<{
      value: string;
      label: string;
    }>;
    can_send_internal_note: boolean;
    can_hide_from_workspace?: boolean;
    can_unhide_from_workspace?: boolean;
    can_archive_ticket?: boolean;
    can_unarchive_ticket?: boolean;
    closure_requirements?: Array<{
      key: string;
      label: string;
      met: boolean;
      detail: string;
      fact_key?: string | null;
      severity?: string | null;
      recommended_actions?: string[];
      candidate_count?: number;
      source_candidates?: Array<Record<string, unknown>>;
      stale_reasons?: string[];
      current_source_counts?: Record<string, number>;
    }>;
    approval?: {
      waiting_status?: string | null;
      approved_transition?: string | null;
      rejected_transition?: string | null;
      reject_requires_comment?: boolean;
      current_action_owner?: string | null;
      pending_count?: number;
    } | null;
  };
  quality?: {
    latest_feedback?: {
      feedback_id: string;
      rating: number;
      sentiment?: string | null;
      problem_resolved?: boolean | null;
      resolution_confirmed?: boolean | null;
      reason_codes?: string[];
      comment?: string | null;
      source_surface?: string | null;
      submitted_at?: string | null;
    } | null;
    reopen_events: Array<{
      reopen_id: string;
      reason_code: string;
      reason_comment?: string | null;
      previous_status?: string | null;
      new_status?: string | null;
      created_at?: string | null;
    }>;
    reviews: Array<{
      review_id: string;
      review_type: string;
      severity: string;
      status: string;
      assigned_to_actor_id?: string | null;
      score?: number | null;
      due_at?: string | null;
      created_at?: string | null;
      closed_at?: string | null;
    }>;
    improvement_actions: Array<{
      action_id: string;
      source_kind: string;
      action_type: string;
      title: string;
      status: string;
      priority: string;
      owner_actor_id?: string | null;
      due_at?: string | null;
      created_at?: string | null;
      closed_at?: string | null;
    }>;
    indicators: string[];
  } | null;
  customer_history?: CustomerHistoryPayload | null;
  llm_context_preview?: CustomerHistoryContextPack | null;
};

export type SupportTicketTimelineFilter = "all" | "messages" | "internal" | "diagnostics" | "history";

export type SupportTicketTimelinePayload = {
  ticket_id: string;
  filter: SupportTicketTimelineFilter;
  items: SupportTicketDetailPayload["timeline"];
  total: number;
  limit: number;
};

export type SupportMessageActionResult = {
  ticket_id: string;
  message: SupportTicketDetailPayload["timeline"][number];
};

export type SupportTicketReadPayload = {
  ticket_id?: string;
  read_scope?: string;
  last_read_event_id: number | null;
  no_op?: boolean;
};

export type SupportStatusActionResult = {
  ticket_id: string;
  status: string;
  status_label: string;
};

export type SupportTicketMutationActionResult = {
  ticket_id: string;
  action: "assign" | "queue" | "priority" | "reroute" | "hide" | "unhide" | "archive" | "unarchive";
  status: string;
  status_label: string;
  queue: {
    id: number | null;
    code: string | null;
    name: string | null;
  };
  assignee_id: string | null;
  priority: string | null;
  priority_class: string | null;
  auto_assigned: boolean;
  hidden_from_workspace?: boolean;
  hidden_at?: string | null;
  hidden_by?: string | null;
  hidden_reason?: string | null;
  archived_at?: string | null;
  archived_by?: string | null;
  archive_reason?: string | null;
};

export type SupportWorkspaceCleanupResult = {
  action: "cleanup_noise";
  matched_count: number;
  hidden_count: number;
  hidden_ticket_ids: string[];
  skipped_ticket_ids: string[];
};

export type SupportDiagnosticTarget = {
  target_device_id?: string | null;
  legacy_ticket_device_id?: string | null;
  source?: string | null;
  agent_status?: string | null;
  reason_code?: string | null;
  created_on_behalf?: boolean;
  creator_person_id?: string | null;
  affected_person_id?: string | null;
  affected_display_name?: string | null;
};

export type SupportTicketToolsPayload = {
  ticket_id: string;
  device_id: string | null;
  diagnostic_target?: SupportDiagnosticTarget | null;
  tools: Array<{
    tool_name: string;
    module_name: string | null;
    description: string | null;
    domain?: string | null;
    tool_kind?: string | null;
    risk_level: string;
    requires_consent: boolean;
    install_required: boolean;
    required_permission?: string | null;
    allowed_roles?: string[];
    policy_labels?: string[];
    source: string;
    params_schema: Array<{
      name: string;
      label: string | null;
      description: string | null;
      type: string;
      required: boolean;
      default: unknown;
    }>;
    presets: Array<{
      preset_id: string;
      label: string;
      description: string | null;
      params: Record<string, unknown>;
    }>;
  }>;
};

export type SupportTicketPlaybooksPayload = {
  ticket_id: string;
  device_id: string | null;
  diagnostic_target?: SupportDiagnosticTarget | null;
  diagnostic_policy?: {
    suggested_playbooks: string[];
    auto_run_enabled: boolean;
    auto_run_priorities: string[];
    requester_consent_required: boolean;
    high_risk_consent_required: boolean;
    attach_to_timeline: boolean;
    attach_to_passport: boolean;
    attach_as_evidence: boolean;
    reroute_by_result: Record<string, string>;
  } | null;
  playbooks: Array<{
    playbook_version_id: number;
    key: string;
    name: string;
    domain: string | null;
    version: string | null;
    status: string;
    blocks_count: number;
    required_tools: string[];
    missing_tools?: string[];
    missing_params?: string[];
    can_run: boolean;
    readiness_label: string;
    updated_at: string | null;
  }>;
  recent_runs?: Array<{
    playbook_run_id: number;
    playbook_version_id: number;
    playbook_key: string | null;
    playbook_name: string | null;
    status: string;
    error_code: string | null;
    error_message: string | null;
    trigger_type: string | null;
    started_at: string | null;
    finished_at: string | null;
    step_errors: Array<{
      step_key: string | null;
      tool_name: string | null;
      error_code: string | null;
      error_message: string;
      stage: string | null;
    }>;
  }>;
};

export type SupportTicketPassportPayload = {
  ticket_id: string;
  status: string;
  passport: {
    passport_id: number;
    ticket_id: string;
    version: number;
    status: string;
    summary_source: string;
    generated_at: string | null;
    generated_by: string | null;
    updated_at: string | null;
    updated_by: string | null;
    sections: Record<string, string>;
    source_event_ids: number[];
    source_operation_ids: string[];
    source_payload: Record<string, unknown>;
    stale: boolean;
  } | null;
  requirements?: {
    required_sections: string[];
    require_official_passport: boolean;
    missing_facts: Array<{
      required_fact: string;
      section_key?: string | null;
      source: string;
      current_value: string | null;
      requester_visible_label: string;
      severity: string;
      accepted_evidence_types?: string[];
      candidate_count?: number;
      recommended_actions?: string[];
      blocking_for_closure?: boolean;
      satisfied_by_evidence_ids?: number[];
      source_candidates?: Array<Record<string, unknown>>;
    }>;
    missing_count: number;
    blocking_missing_count: number;
    export_preview: {
      visible_sections?: string[];
      hidden_sections?: string[];
    };
    knowledge_draft_hints: Record<string, unknown>;
  };
  evidence: Array<{
    id: number;
    ticket_id: string;
    passport_id: number | null;
    evidence_type: string;
    source_ref: string | null;
    source_kind?: string | null;
    source_id?: string | null;
    required_fact?: string | null;
    section_key?: string | null;
    artifact_id?: string | null;
    title: string;
    summary: string | null;
    visibility: string;
    verification_status?: string;
    verified_by?: string | null;
    verified_at?: string | null;
    captured_at?: string | null;
    public_summary?: string | null;
    internal_summary?: string | null;
    metadata_json?: Record<string, unknown>;
    export_visibility?: string;
    created_by: string | null;
    created_at: string | null;
  }>;
  actions: Array<{
    id: number;
    ticket_id: string;
    passport_id: number | null;
    action_type: string;
    actor_id: string | null;
    source_event_id: number | null;
    operation_id: string | null;
    title: string;
    summary: string | null;
    started_at: string | null;
    finished_at: string | null;
    created_at: string | null;
  }>;
  approvals: Array<{
    id: number;
    ticket_id: string;
    passport_id: number | null;
    approval_type: string;
    approver_id: string | null;
    status: string;
    reason: string | null;
    requested_by: string | null;
    requested_at: string | null;
    decided_at: string | null;
  }>;
  related_objects: Array<{
    id: number;
    ticket_id: string;
    passport_id: number | null;
    object_type: string;
    object_ref: string;
    display_name: string | null;
    relation_type: string;
    source: string;
    created_at: string | null;
  }>;
};

export type SupportTicketEvidenceCandidatePayload = {
  candidate_id: string;
  source_kind: string;
  source_id: string;
  source_ref: string;
  source_quality: string;
  evidence_type: string;
  required_fact: string;
  section_key: string;
  artifact_id?: string | null;
  title: string;
  summary: string | null;
  visibility: string;
  captured_at?: string | null;
  metadata_json?: Record<string, unknown>;
  existing_evidence_id?: number | null;
};

export type SupportTicketEvidenceCandidatesPayload = {
  ticket_id: string;
  candidates: SupportTicketEvidenceCandidatePayload[];
};

export type SupportTicketPassportEvidenceCreatePayload = {
  evidence_type: string;
  source_ref?: string | null;
  source_kind?: string | null;
  source_id?: string | null;
  required_fact?: string | null;
  section_key?: string | null;
  artifact_id?: string | null;
  title: string;
  summary?: string | null;
  visibility?: string;
  verification_status?: string;
  captured_at?: string | null;
  public_summary?: string | null;
  internal_summary?: string | null;
  metadata_json?: Record<string, unknown>;
  export_visibility?: string;
};

export type SupportTicketWorklogPayload = {
  worklog_id: number;
  actor_id: string | null;
  spent_minutes: number;
  note: string | null;
};

export type SupportOperationCancelPayload = {
  status: string;
  target_operation_id: string;
  cancel_operation_id?: string | null;
  message?: string | null;
  reason?: string | null;
};

export type SupportOperationRetryPayload = {
  status: string;
  operation_id: string;
  retry_of_operation_id: string;
  ticket_id: string;
  device_id: string;
  tool_name: string;
  poll_url?: string | null;
  trace_id?: string | null;
  retry_requires_consent?: boolean | null;
  consent_state?: string | null;
  consent_action_url?: string | null;
};

export type SupportTicketPassportSectionPatchPayload = {
  operator_check_summary?: string | null;
  changes_made_summary?: string | null;
  repeat_guidance?: string | null;
  user_result_summary?: string | null;
  internal_result_summary?: string | null;
};

export type SupportTicketKnowledgeDraftPayload = {
  title: string;
  problem: string;
  resolution: string;
  repeat_guidance: string;
  source_passport_id: number;
  item_id?: string | null;
  version_id?: string | null;
  status?: string | null;
  item_type?: string | null;
  edit_url?: string | null;
  warnings?: string[];
  bindings?: Array<Record<string, unknown>>;
};

export type SupportTicketKnowledgeSuggestionsPayload = {
  ticket_id: string;
  requester_attempts?: Array<{
    item_id: string;
    version_id?: string | null;
    result: string;
    surface: string;
    visibility_scope?: string;
    audience_scope?: string;
    occurred_at: string;
  }>;
  similar_tickets: Array<{
    id: string;
    number: string | null;
    subject: string;
    resolution_summary: string | null;
  }>;
  articles: Array<{
    id: string;
    title: string;
    url: string | null;
  }>;
  ai_summary: {
    text: string | null;
    sources: string[];
    confidence?: string;
    source_count?: number;
  };
  diagnostics?: {
    provider: string;
    provider_version: string;
    provider_status?: string;
    external_provider_status?: string;
    fallback_reason?: string | null;
    catalog_entry_count?: number;
    query_tokens?: string[];
    source_counts: Record<string, number>;
    query_signals: string[];
    article_matches: Record<string, {
      source_type: string;
      score: number | null;
      match_reasons: string[];
    }>;
    similar_ticket_matches: Record<string, {
      source_type: string;
      score: number | null;
      match_reasons: string[];
    }>;
  };
};

export type SupportTicketSlaOlaTimerPayload = {
  due_at: string | null;
  remaining_seconds: number | null;
  target_seconds: number | null;
  status: "ok" | "at_risk" | "breached" | "paused" | "unknown" | string;
};

export type SupportTicketSlaOlaPayload = {
  first_response: SupportTicketSlaOlaTimerPayload;
  resolution: SupportTicketSlaOlaTimerPayload;
  ola_ack: SupportTicketSlaOlaTimerPayload;
  ola_processing: SupportTicketSlaOlaTimerPayload;
};

export type SupportTicketPassportReadinessPayload = {
  ticket_id: string;
  status: string;
  done: number;
  total: number;
  items: Array<{
    key: string;
    label: string;
    status: "done" | "pending" | string;
  }>;
};

export type SupportTicketClosurePlanPayload = {
  ticket_id: string;
  ready_for_resolution: boolean;
  missing_count: number;
  total: number;
  evidence_candidate_count: number;
  recommended_next_action: string | null;
  blockers: Array<{
    key: string;
    label: string;
    met: boolean;
    detail: string;
    source: string;
    action_kind: string;
    action_label: string;
    severity: string | null;
    candidate_count: number;
    fact_key: string | null;
    blocking_for_closure: boolean;
  }>;
};

export type SupportTicketInventoryContext = {
  device_id: string | null;
  hostname?: string | null;
  display_name?: string | null;
  agent?: {
    connection_state?: "online" | "offline" | "unknown" | string;
    last_seen_at?: string | null;
    version?: string | null;
    update_status?: string | null;
    update_available?: boolean | null;
  } | null;
  inventory?: {
    latest_snapshot_id?: string | null;
    collected_at?: string | null;
    age_seconds?: number | null;
    freshness?: "fresh" | "stale" | "missing" | "unknown" | string;
    source?: string | null;
    summary?: Record<string, unknown> | null;
  } | null;
  binding?: {
    responsible_person?: string | null;
    department?: string | null;
    building?: string | null;
    room?: string | null;
    status?: string | null;
    tags?: string[];
  } | null;
  refresh?: {
    policy_enabled?: boolean | null;
    last_run_id?: string | null;
    last_run_status?: string | null;
    last_run_at?: string | null;
    next_due_at?: string | null;
    can_request_refresh?: boolean;
  } | null;
  signals?: {
    stale_inventory?: boolean;
    missing_inventory?: boolean;
    agent_offline?: boolean;
    failed_recent_refresh?: boolean;
    failed_recent_operation?: boolean;
  } | null;
};

export type SupportTicketWorkspacePayload = {
  detail: SupportTicketDetailPayload;
  tools: SupportTicketToolsPayload;
  playbooks: SupportTicketPlaybooksPayload;
  passport: SupportTicketPassportPayload;
  knowledge: SupportTicketKnowledgeSuggestionsPayload;
  sla_ola: SupportTicketSlaOlaPayload;
  passport_readiness: SupportTicketPassportReadinessPayload;
  closure_plan: SupportTicketClosurePlanPayload;
  inventory_context?: SupportTicketInventoryContext | null;
};

export type SupportToolActionResult = {
  ticket_id: string;
  device_id: string;
  diagnostic_target?: SupportDiagnosticTarget | null;
  tool_name: string;
  dispatch_status: string;
  operation_id: string;
  poll_url: string;
  trace_id: string | null;
  message: string;
};

export type SupportPlaybookRunActionResult = {
  ticket_id: string;
  device_id: string;
  diagnostic_target?: SupportDiagnosticTarget | null;
  playbook_version_id: number;
  playbook_run_id: number;
  status: string;
  first_operation_id: string | null;
  observer_url: string;
  message: string;
};

export type SupportTicketAttachmentUpload = {
  artifact_id: string;
  filename: string;
  url: string;
  size: number;
  sha256: string;
  mime_type: string;
  kind: string;
  name?: string;
};

type SuccessResponse<T> = {
  status: "success";
  data: T;
};

type ErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

export class SupportBootstrapApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "SupportBootstrapApiError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function readJson<T>(response: Response): Promise<T | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  return (await response.json()) as T;
}

export async function fetchSupportBootstrap(): Promise<SupportBootstrapPayload> {
  const response = await fetch("/api/web/support/bootstrap", {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportBootstrapPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось загрузить рабочее место поддержки",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

type SupportQueueParams = {
  scope: SupportQueueScope;
  statusFilter: string;
  smartView?: string;
  query: string;
  includeArchived?: boolean;
  includeHidden?: boolean;
};

function buildSupportQueueUrl(params: SupportQueueParams): string {
  const searchParams = new URLSearchParams();
  searchParams.set("scope", params.scope);
  if (params.statusFilter && params.statusFilter !== "all") {
    searchParams.set("status", params.statusFilter);
  }
  if (params.smartView && params.smartView !== "all") {
    searchParams.set("smart_view", params.smartView);
  }
  if (params.query.trim()) {
    searchParams.set("query", params.query.trim());
  }
  if (params.includeArchived) {
    searchParams.set("include_archived", "1");
  }
  if (params.includeHidden) {
    searchParams.set("include_hidden", "1");
  }
  return `/api/web/support/queue?${searchParams.toString()}`;
}

export async function fetchSupportQueue(params: SupportQueueParams): Promise<SupportQueuePayload> {
  const response = await fetch(buildSupportQueueUrl(params), {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportQueuePayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось загрузить очередь поддержки",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function postSupportQueueMassAction(request: SupportQueueMassActionRequest): Promise<SupportQueueMassActionResult> {
  const response = await fetch("/api/web/support/queue/mass-action", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });
  const payload = await readJson<SuccessResponse<SupportQueueMassActionResult> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось выполнить массовое действие",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function fetchSupportQueueSavedViews(): Promise<SupportQueueSavedViewsPayload> {
  const response = await fetch("/api/web/support/queue/saved-views", {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportQueueSavedViewsPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Failed to load saved queue views",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function createSupportQueueSavedView(request: SupportQueueSavedViewUpsertRequest): Promise<SupportQueueSavedViewItem> {
  const response = await fetch("/api/web/support/queue/saved-views", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });
  const payload = await readJson<SuccessResponse<SupportQueueSavedViewItem> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Failed to save queue view",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function updateSupportQueueSavedView(viewId: string, request: SupportQueueSavedViewUpsertRequest): Promise<SupportQueueSavedViewItem> {
  const response = await fetch(`/api/web/support/queue/saved-views/${encodeURIComponent(viewId)}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });
  const payload = await readJson<SuccessResponse<SupportQueueSavedViewItem> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Failed to update queue view",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function deleteSupportQueueSavedView(viewId: string): Promise<SupportQueueSavedViewDeletePayload> {
  const response = await fetch(`/api/web/support/queue/saved-views/${encodeURIComponent(viewId)}`, {
    method: "DELETE",
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportQueueSavedViewDeletePayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Failed to delete queue view",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function fetchSupportWorkspaceSummary(limit?: number): Promise<SupportWorkspaceSummaryPayload> {
  const searchParams = new URLSearchParams();
  if (limit && Number.isFinite(limit)) {
    searchParams.set("limit", String(Math.max(1, Math.floor(limit))));
  }
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  const response = await fetch(`/api/web/support/workspace/summary${suffix}`, {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportWorkspaceSummaryPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось загрузить сводку рабочего пространства поддержки",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function fetchSupportTicketDetail(ticketId: string): Promise<SupportTicketDetailPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}`, {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportTicketDetailPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось загрузить карточку тикета",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function fetchSupportTicketWorkspace(ticketId: string): Promise<SupportTicketWorkspacePayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/workspace`, {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportTicketWorkspacePayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось загрузить рабочее пространство тикета",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function fetchSupportTicketKnowledgeSuggestions(ticketId: string): Promise<SupportTicketKnowledgeSuggestionsPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/knowledge-suggestions`, {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportTicketKnowledgeSuggestionsPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось загрузить подсказки базы знаний",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function fetchSupportTicketTimeline(
  ticketId: string,
  filter: SupportTicketTimelineFilter = "all"
): Promise<SupportTicketTimelinePayload> {
  const searchParams = new URLSearchParams();
  searchParams.set("filter", filter);
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/timeline?${searchParams.toString()}`, {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportTicketTimelinePayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ timeline С‚РёРєРµС‚Р°",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function postSupportTicketMessage(
  ticketId: string,
  text: string,
  visibility: "internal" | "public" = "public",
  attachmentRefs: string[] = []
): Promise<SupportMessageActionResult> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/messages`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      text,
      visibility,
      attachment_refs: attachmentRefs
    })
  });
  const payload = await readJson<SuccessResponse<SupportMessageActionResult> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось отправить сообщение из поддержки",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function uploadSupportTicketAttachment(ticketId: string, file: File): Promise<SupportTicketAttachmentUpload> {
  const formData = new FormData();
  formData.append("file", file, file.name || "attachment.bin");
  formData.append("ticket_id", ticketId);
  formData.append("kind", file.type.startsWith("image/") ? "screenshot" : file.type.startsWith("video/") ? "screen_recording" : "file");

  const response = await fetch("/api/upload", {
    method: "POST",
    credentials: "same-origin",
    body: formData
  });
  const payload = await readJson<(SupportTicketAttachmentUpload & { status: "success" }) | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось прикрепить файл",
      response.status,
      errorPayload?.error_code
    );
  }

  return {
    artifact_id: payload.artifact_id,
    filename: payload.filename,
    url: payload.url,
    size: payload.size,
    sha256: payload.sha256,
    mime_type: payload.mime_type,
    kind: payload.kind,
    name: file.name || payload.filename
  };
}

export async function postSupportTicketRead(ticketId: string, lastReadEventId: number): Promise<SupportTicketReadPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/read`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      last_read_event_id: lastReadEventId
    })
  });
  const payload = await readJson<SupportTicketReadPayload | ErrorResponse>(response);

  if (!response.ok || !payload || ("status" in payload && payload.status === "error")) {
    const errorPayload = payload && "status" in payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось отметить сообщения как прочитанные",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload as SupportTicketReadPayload;
}

export async function postSupportTicketWorklog(
  ticketId: string,
  worklog: { spentMinutes: number; note?: string | null }
): Promise<SupportTicketWorklogPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/worklogs`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      spent_minutes: worklog.spentMinutes,
      note: worklog.note ?? null
    })
  });
  const payload = await readJson<({ status: "success"; worklog: SupportTicketWorklogPayload } & Record<string, unknown>) | ErrorResponse>(
    response
  );

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось добавить worklog",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.worklog;
}

export async function postSupportOperationCancel(
  operationId: string,
  options: { reason?: string | null } = {}
): Promise<SupportOperationCancelPayload> {
  const response = await fetch(`/api/web/support/operations/${encodeURIComponent(operationId)}/cancel`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      reason: options.reason ?? null
    })
  });
  const payload = await readJson<SupportOperationCancelPayload | ErrorResponse>(response);

  if (!response.ok || !payload || ("error" in payload && payload.status === "error")) {
    const errorPayload = payload && "error" in payload ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось отменить операцию",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload as SupportOperationCancelPayload;
}

export async function postSupportOperationRetry(
  operationId: string,
  options: { reason?: string | null } = {}
): Promise<SupportOperationRetryPayload> {
  const response = await fetch(`/api/operations/${encodeURIComponent(operationId)}/retry`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      reason: options.reason ?? null
    })
  });
  const payload = await readJson<SupportOperationRetryPayload | ErrorResponse>(response);

  if (!response.ok || !payload || ("error" in payload && payload.status === "error")) {
    const errorPayload = payload && "error" in payload ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось повторить операцию",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload as SupportOperationRetryPayload;
}

export async function postSupportTicketStatus(
  ticketId: string,
  toStatus: string,
  options: {
    reason?: string;
    publicComment?: string;
    internalComment?: string;
    resolutionCode?: string;
    resolutionSummary?: string;
    requesterResolutionSummary?: string;
  } = {}
): Promise<SupportStatusActionResult> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/status`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      to_status: toStatus,
      reason: options.reason,
      public_comment: options.publicComment,
      internal_comment: options.internalComment,
      resolution_code: options.resolutionCode,
      resolution_summary: options.resolutionSummary,
      requester_resolution_summary: options.requesterResolutionSummary
    })
  });
  const payload = await readJson<SuccessResponse<SupportStatusActionResult> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось обновить статус тикета",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

async function postSupportTicketMutationAlias(
  ticketId: string,
  action: SupportTicketMutationActionResult["action"],
  body: Record<string, unknown>
): Promise<SupportTicketMutationActionResult> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/${action}`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });
  const payload = await readJson<SuccessResponse<SupportTicketMutationActionResult> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось выполнить действие с тикетом",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export function postSupportTicketAssign(
  ticketId: string,
  payload: {
    assigneeId?: string | null;
    autoAssign?: boolean;
    reason?: string;
    comment?: string;
  }
): Promise<SupportTicketMutationActionResult> {
  return postSupportTicketMutationAlias(ticketId, "assign", {
    assignee_id: payload.assigneeId,
    auto_assign: payload.autoAssign,
    reason: payload.reason,
    comment: payload.comment
  });
}

export function postSupportTicketQueue(
  ticketId: string,
  payload: {
    queueId: number;
    reason?: string;
  }
): Promise<SupportTicketMutationActionResult> {
  return postSupportTicketMutationAlias(ticketId, "queue", {
    queue_id: payload.queueId,
    reason: payload.reason
  });
}

export function postSupportTicketPriority(
  ticketId: string,
  payload: {
    priority: "P0" | "P1" | "P2" | "P3";
    reason?: string;
  }
): Promise<SupportTicketMutationActionResult> {
  return postSupportTicketMutationAlias(ticketId, "priority", payload);
}

export function postSupportTicketReroute(
  ticketId: string,
  payload: {
    reason?: string;
  } = {}
): Promise<SupportTicketMutationActionResult> {
  return postSupportTicketMutationAlias(ticketId, "reroute", payload);
}

export function postSupportTicketHide(ticketId: string, payload: { reason?: string } = {}): Promise<SupportTicketMutationActionResult> {
  return postSupportTicketMutationAlias(ticketId, "hide", payload);
}

export function postSupportTicketUnhide(ticketId: string, payload: { reason?: string } = {}): Promise<SupportTicketMutationActionResult> {
  return postSupportTicketMutationAlias(ticketId, "unhide", payload);
}

export function postSupportTicketArchive(ticketId: string, payload: { reason?: string } = {}): Promise<SupportTicketMutationActionResult> {
  return postSupportTicketMutationAlias(ticketId, "archive", payload);
}

export function postSupportTicketUnarchive(ticketId: string, payload: { reason?: string } = {}): Promise<SupportTicketMutationActionResult> {
  return postSupportTicketMutationAlias(ticketId, "unarchive", payload);
}

export async function postSupportWorkspaceCleanupNoise(reason = "manual live/stage/test cleanup"): Promise<SupportWorkspaceCleanupResult> {
  const response = await fetch("/api/web/support/workspace/cleanup-noise", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ reason })
  });
  const payload = await readJson<SuccessResponse<SupportWorkspaceCleanupResult> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось скрыть live/test тикеты",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function fetchSupportTicketTools(ticketId: string): Promise<SupportTicketToolsPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/tools`, {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportTicketToolsPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось загрузить список инструментов",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function fetchSupportTicketPlaybooks(ticketId: string): Promise<SupportTicketPlaybooksPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/playbooks`, {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportTicketPlaybooksPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось загрузить плейбуки тикета",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function fetchSupportTicketPassport(ticketId: string): Promise<SupportTicketPassportPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/passport`, {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportTicketPassportPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось загрузить паспорт решения",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function generateSupportTicketPassport(
  ticketId: string,
  mode: "create" | "refresh"
): Promise<SupportTicketPassportPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/passport/generate`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ mode })
  });
  const payload = await readJson<SuccessResponse<SupportTicketPassportPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось собрать паспорт решения",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function patchSupportTicketPassport(
  ticketId: string,
  patch: SupportTicketPassportSectionPatchPayload
): Promise<SupportTicketPassportPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/passport`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(patch)
  });
  const payload = await readJson<SuccessResponse<SupportTicketPassportPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось обновить разделы паспорта",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function fetchSupportTicketPassportEvidenceCandidates(
  ticketId: string
): Promise<SupportTicketEvidenceCandidatesPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/passport/evidence-candidates`, {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportTicketEvidenceCandidatesPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось загрузить кандидатов доказательств",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function linkSupportTicketPassportEvidence(
  ticketId: string,
  link: {
    source_kind: string;
    source_id: string;
    required_fact?: string | null;
    visibility?: string;
  }
): Promise<SupportTicketPassportPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/passport/evidence/link`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(link)
  });
  const payload = await readJson<SuccessResponse<SupportTicketPassportPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось привязать кандидата как доказательство",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function createSupportTicketPassportEvidence(
  ticketId: string,
  evidence: SupportTicketPassportEvidenceCreatePayload
): Promise<SupportTicketPassportPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/passport/evidence`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(evidence)
  });
  const payload = await readJson<SuccessResponse<SupportTicketPassportPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось добавить доказательство",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function createSupportTicketKnowledgeDraft(ticketId: string): Promise<SupportTicketKnowledgeDraftPayload> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/passport/knowledge-draft`, {
    method: "POST",
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<SupportTicketKnowledgeDraftPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось подготовить черновик знания",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function postSupportTicketToolRun(
  ticketId: string,
  payload: {
    toolName: string;
    presetId: string | null;
    params: Record<string, unknown>;
  }
): Promise<SupportToolActionResult> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/tools/run`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      tool_name: payload.toolName,
      preset_id: payload.presetId,
      params: payload.params
    })
  });
  const result = await readJson<SuccessResponse<SupportToolActionResult> | ErrorResponse>(response);

  if (!response.ok || !result || result.status !== "success") {
    const errorPayload = result && result.status === "error" ? result : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось запустить инструмент",
      response.status,
      errorPayload?.error_code
    );
  }

  return result.data;
}

export async function postSupportTicketPlaybookRun(
  ticketId: string,
  payload: {
    playbookVersionId: number;
  }
): Promise<SupportPlaybookRunActionResult> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/playbooks/run`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      playbook_version_id: payload.playbookVersionId
    })
  });
  const result = await readJson<SuccessResponse<SupportPlaybookRunActionResult> | ErrorResponse>(response);

  if (!response.ok || !result || result.status !== "success") {
    const errorPayload = result && result.status === "error" ? result : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Не удалось запустить плейбук",
      response.status,
      errorPayload?.error_code
    );
  }

  return result.data;
}
