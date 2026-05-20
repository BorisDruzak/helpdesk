const COMMAND_CENTER_SMART_VIEW_ALIASES: Record<string, string> = {
  new_unassigned: "unassigned",
  operator_action: "my_action",
  requires_operator_action: "my_action",
  unread_user_messages: "requester_reply",
  pending_approval: "waiting_approval",
  sla_risk: "sla_risk",
  ola_risk: "ola_risk",
  unassigned: "unassigned",
  requester_reply: "requester_reply",
  waiting_approval: "waiting_approval",
  my_action: "my_action",
  all: "all",
};

export type TicketsWorkspaceUrlState = {
  smartView: string | null;
  search: string | null;
  similarGroup: string | null;
  shouldOpenQueue: boolean;
};

export function normalizeTicketsSmartViewParam(rawValue: string | null | undefined): string | null {
  const value = String(rawValue ?? "").trim();
  if (!value) {
    return null;
  }
  return COMMAND_CENTER_SMART_VIEW_ALIASES[value] ?? null;
}

export function getTicketsWorkspaceUrlState(searchParams: URLSearchParams): TicketsWorkspaceUrlState {
  const smartView = normalizeTicketsSmartViewParam(searchParams.get("smart_view"));
  const search = (searchParams.get("search") ?? searchParams.get("query") ?? "").trim() || null;
  const similarGroup = (searchParams.get("similar_group") ?? "").trim() || null;

  return {
    smartView,
    search,
    similarGroup,
    shouldOpenQueue: Boolean(smartView || search || similarGroup),
  };
}
