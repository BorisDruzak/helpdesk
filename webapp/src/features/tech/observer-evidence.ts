import type { AdminObserverTraceItem } from "./api";
import type { ObserverDiagnosticsBundlePayload } from "./observer-workbench-api";

export type TraceEvidenceSource = {
  key: string;
  label: string;
  count: number;
};

export type BundleEvidenceStat = {
  key: string;
  label: string;
  value: number;
};

const SOURCE_LABELS: Record<string, string> = {
  operations: "Operations",
  ticket_events: "Ticket events",
  device_events: "Device events",
  agent_runtime_audit: "Runtime audit",
  agent_observer_events: "Agent telemetry",
  playbook_step_runs: "Playbook steps",
};

function toCount(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return Math.floor(value);
  }
  if (typeof value === "string") {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return 0;
}

function fallbackLabel(key: string): string {
  return key.replace(/_/g, " ");
}

export function buildTraceEvidenceSources(
  trace: Pick<AdminObserverTraceItem, "attrs_json"> | null | undefined
): TraceEvidenceSource[] {
  const sourceCounts = trace?.attrs_json?.source_counts;
  if (!sourceCounts || typeof sourceCounts !== "object" || Array.isArray(sourceCounts)) {
    return [];
  }
  return Object.entries(sourceCounts)
    .map(([key, rawCount]) => ({
      key,
      label: SOURCE_LABELS[key] ?? fallbackLabel(key),
      count: toCount(rawCount),
    }))
    .filter((item) => item.count > 0)
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

export function buildBundleEvidenceStats(
  bundle: Pick<ObserverDiagnosticsBundlePayload, "summary"> | null | undefined
): BundleEvidenceStat[] {
  const summary = bundle?.summary ?? {};
  return [
    { key: "agent_actions", label: "Agent actions", value: toCount(summary.agent_action_count) },
    { key: "agent_audit", label: "Runtime audit", value: toCount(summary.agent_audit_count) },
    { key: "recent_logs", label: "Recent logs", value: toCount(summary.recent_log_count) },
    { key: "related_traces", label: "Related traces", value: toCount(summary.related_trace_count) },
  ];
}
