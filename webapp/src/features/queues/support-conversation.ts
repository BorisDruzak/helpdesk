import type { SupportTicketDetailPayload } from "./api";
import type { SupportWorkspaceTimelineItem } from "./support-workspace-model";

// These are the human sender roles accepted by the canonical ticket chat projection.
const humanRoles = new Set(["user", "requester", "agent", "device", "client", "support", "admin", "staff", "operator"]);

export function isSupportConversationEntry(entry: SupportTicketDetailPayload["timeline"][number]): boolean {
  return entry.event_type === "chat_message"
    && humanRoles.has(entry.from_role.trim().toLowerCase())
    && entry.visibility !== "system"
    && entry.direction !== "system"
    && entry.requester_timeline_kind !== "system_event"
    && entry.requester_timeline_kind !== "diagnostic_result";
}

export function partitionSupportTimeline(items: readonly SupportWorkspaceTimelineItem[]): {
  conversation: SupportWorkspaceTimelineItem[];
  context: SupportWorkspaceTimelineItem[];
} {
  const conversation: SupportWorkspaceTimelineItem[] = [], context: SupportWorkspaceTimelineItem[] = [];
  for (const item of items) (item.kind === "message" || item.kind === "internal" ? conversation : context).push(item);
  return { conversation, context };
}
