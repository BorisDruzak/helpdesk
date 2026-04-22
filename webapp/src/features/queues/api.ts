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

export type SupportQueuePayload = {
  scope: SupportQueueScope;
  query: string;
  status_filter: string;
  summary: {
    visible_count: number;
    selected_ticket_id: string | null;
    scope_counts: SupportCountItem[];
    status_counts: SupportCountItem[];
  };
  filters: {
    scope_options: SupportFilterOption[];
    status_options: SupportFilterOption[];
  };
  tickets: Array<{
    ticket_id: string;
    ticket_code: string | null;
    title: string;
    status: string;
    status_label: string;
    queue_code: string | null;
    assignee_id: string | null;
    requester_display_name: string | null;
    device_id: string | null;
    updated_at: string | null;
    created_at: string | null;
    requires_operator_action: boolean;
    unread_user_messages: number;
  }>;
};

export type SupportTicketDetailPayload = {
  ticket: {
    ticket_id: string;
    ticket_code: string | null;
    title: string;
    description: string | null;
    status: string;
    status_label: string;
    requester_display_name: string | null;
    device_id: string | null;
    queue: {
      id: number | null;
      code: string | null;
      name: string | null;
    };
    assignee_id: string | null;
    updated_at: string | null;
    created_at: string | null;
    queue_members: Array<{
      actor_id: string;
      role_in_queue: string | null;
    }>;
  };
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
    latest_operations: Array<{
      operation_id: string;
      kind: string;
      status: string;
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
    }>;
  }>;
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
  query: string;
};

function buildSupportQueueUrl(params: SupportQueueParams): string {
  const searchParams = new URLSearchParams();
  searchParams.set("scope", params.scope);
  if (params.statusFilter && params.statusFilter !== "all") {
    searchParams.set("status", params.statusFilter);
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
