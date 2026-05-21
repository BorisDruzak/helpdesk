export type ApprovalConsentScope = "my" | "team" | "all";
export type ApprovalConsentSeverity = "critical" | "warning" | "info";
export type ApprovalConsentStatus = "pending" | "approved" | "rejected" | "expired" | "canceled" | "unknown";
export type ApprovalConsentRisk = "low" | "medium" | "high" | "critical" | "unknown";

export type ApprovalConsentAction = {
  key:
    | "open_ticket"
    | "open_change"
    | "open_device_operations"
    | "open_operation"
    | "open_remote_assist"
    | "approve"
    | "reject"
    | "delegate"
    | "cancel"
    | "resend_request";
  label: string;
  href?: string | null;
  method?: "POST" | "PATCH" | null;
  endpoint?: string | null;
  enabled: boolean;
  disabled_reason?: string | null;
  requires_comment?: boolean;
  risk_warning?: string | null;
};

export type ApprovalConsentItem = {
  id: string;
  kind:
    | "ticket_approval"
    | "change_approval"
    | "risky_tool_consent"
    | "remote_assist_consent"
    | "closure_approval"
    | "policy_override";
  status: ApprovalConsentStatus;
  title: string;
  reason: string;
  object_type: "ticket" | "change" | "operation" | "remote_assist" | "policy" | "closure";
  object_id: string;
  ticket_id?: string | null;
  ticket_number?: string | null;
  change_id?: string | null;
  change_number?: string | null;
  operation_id?: string | null;
  remote_assist_session_id?: string | null;
  device_id?: string | null;
  requester_name?: string | null;
  requested_by?: string | null;
  approver?: string | null;
  approver_group?: string | null;
  risk: ApprovalConsentRisk;
  due_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  blocking: {
    blocks_ticket_progress?: boolean;
    blocks_sla?: boolean;
    blocks_operation?: boolean;
    blocks_remote_assist?: boolean;
    blocks_closure?: boolean;
    blocks_change?: boolean;
  };
  context: {
    queue?: string | null;
    assignee?: string | null;
    service_code?: string | null;
    offering_code?: string | null;
    device_hostname?: string | null;
    tool_name?: string | null;
    change_window?: string | null;
    closure_blocker?: string | null;
    policy_code?: string | null;
  };
  actions: ApprovalConsentAction[];
};

export type ApprovalConsentSection = {
  key:
    | "waiting_me"
    | "waiting_user"
    | "overdue"
    | "high_risk"
    | "ticket_approvals"
    | "change_approvals"
    | "risky_tool_consents"
    | "remote_assist_consents"
    | "closure_approvals"
    | "policy_overrides";
  title: string;
  description: string;
  count: number;
  severity: ApprovalConsentSeverity;
  href?: string | null;
};

export type ApprovalConsentCenterPayload = {
  generated_at: string;
  scope: ApprovalConsentScope;
  filters: {
    kind?: string | null;
    status?: string | null;
    risk?: string | null;
    object_type?: string | null;
    queue?: string | null;
    assignee?: string | null;
    due_window_hours?: number | null;
    limit: number;
    offset: number;
  };
  summary: {
    total_count: number;
    pending_count: number;
    overdue_count: number;
    high_risk_count: number;
    waiting_user_count: number;
    waiting_approver_count: number;
    blocking_sla_count: number;
    ticket_approvals_count: number;
    change_approvals_count: number;
    risky_tool_consents_count: number;
    remote_assist_consents_count: number;
    closure_approvals_count: number;
    policy_overrides_count: number;
  };
  sections: ApprovalConsentSection[];
  items: ApprovalConsentItem[];
};

export type FetchApprovalConsentCenterParams = {
  scope?: ApprovalConsentScope;
  kind?: string;
  status?: "pending" | "approved" | "rejected" | "expired" | "all";
  risk?: "low" | "medium" | "high" | "critical";
  object_type?: "ticket" | "change" | "operation" | "remote_assist" | "policy" | "closure";
  queue?: string;
  assignee?: string;
  due_window_hours?: number;
  limit?: number;
  offset?: number;
};
