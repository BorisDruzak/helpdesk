import type { SupportWorkspaceToolItem } from "../../features/queues/support-workspace-model";

export type ToolAvailabilitySummary = {
  available: SupportWorkspaceToolItem[];
  unavailable: SupportWorkspaceToolItem[];
  offlineUnavailableCount: number;
  dominantOfflineReason: string | null;
  unavailableCount: number;
  allUnavailable: boolean;
};

function isOfflineReason(reason: string | null | undefined): boolean {
  const value = String(reason ?? "").toLowerCase();
  return value.includes("offline") || value.includes("офлайн") || value.includes("нет связи");
}

export function summarizeToolAvailability(items: SupportWorkspaceToolItem[]): ToolAvailabilitySummary {
  const available = items.filter((item) => item.enabled);
  const unavailable = items.filter((item) => !item.enabled);
  const offlineItems = unavailable.filter((item) => isOfflineReason(item.disabledReason));
  const dominantOfflineReason = offlineItems[0]?.disabledReason ?? null;

  return {
    available,
    unavailable,
    offlineUnavailableCount: offlineItems.length,
    dominantOfflineReason,
    unavailableCount: unavailable.length,
    allUnavailable: items.length > 0 && available.length === 0,
  };
}
