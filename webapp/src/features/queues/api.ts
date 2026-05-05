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
    status_reason?: string | null;
    priority?: string | null;
    priority_class?: string | null;
    queue_code: string | null;
    assignee_id: string | null;
    assignee_display_name?: string | null;
    requester_display_name: string | null;
    device_id: string | null;
    updated_at: string | null;
    created_at: string | null;
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
      trace_count: number;
      active_trace_count: number;
      error_trace_count: number;
      signature_count: number;
      latest_trace_at?: string | null;
    };
  };
  timeline: Array<{
    message_id: string | null;
    event_id: number | null;
    event_type: string;
    event_category?: string | null;
    event_label?: string | null;
    event_details?: Record<string, unknown>;
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
    operation_steps?: Array<{
      name: string;
      status: string;
      value: string;
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
      department_id: string | null;
      department_name: string | null;
      location_id: string | null;
      location_display_name: string | null;
      building: string | null;
      room: string | null;
      asset_id: string | null;
      asset_name: string | null;
      asset_type: string | null;
      service_id: string | null;
      service_name: string | null;
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
      finished_at: string | null;
      result_summary: string | null;
      error_message: string | null;
    }>;
  };
  actions: {
    status_options: Array<{
      value: string;
      label: string;
    }>;
    can_send_internal_note: boolean;
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
};

export type SupportMessageActionResult = {
  ticket_id: string;
  message: SupportTicketDetailPayload["timeline"][number];
};

export type SupportStatusActionResult = {
  ticket_id: string;
  status: string;
  status_label: string;
};

export type SupportTicketMutationActionResult = {
  ticket_id: string;
  action: "assign" | "queue" | "priority" | "reroute";
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
};

export type SupportTicketToolsPayload = {
  ticket_id: string;
  device_id: string | null;
  tools: Array<{
    tool_name: string;
    module_name: string | null;
    description: string | null;
    risk_level: string;
    requires_consent: boolean;
    install_required: boolean;
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
};

export type SupportTicketKnowledgeSuggestionsPayload = {
  ticket_id: string;
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

export type SupportTicketWorkspacePayload = {
  detail: SupportTicketDetailPayload;
  tools: SupportTicketToolsPayload;
  playbooks: SupportTicketPlaybooksPayload;
  passport: SupportTicketPassportPayload;
  knowledge: SupportTicketKnowledgeSuggestionsPayload;
  sla_ola: SupportTicketSlaOlaPayload;
  passport_readiness: SupportTicketPassportReadinessPayload;
};

export type SupportToolActionResult = {
  ticket_id: string;
  device_id: string;
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
  playbook_version_id: number;
  playbook_run_id: number;
  status: string;
  first_operation_id: string | null;
  observer_url: string;
  message: string;
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

export async function postSupportTicketMessage(
  ticketId: string,
  text: string,
  visibility: "internal" | "public" = "public"
): Promise<SupportMessageActionResult> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/messages`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      text,
      visibility
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

export async function postSupportTicketStatus(ticketId: string, toStatus: string): Promise<SupportStatusActionResult> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/status`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      to_status: toStatus
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
